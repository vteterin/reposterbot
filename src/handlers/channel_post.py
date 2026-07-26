"""Handle new posts arriving in the source channel and crosspost them to destination."""
import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field

from aiogram import Bot, Router
from aiogram.enums import ParseMode
from aiogram.types import (
    InputMediaPhoto, InputMediaVideo, Message,
)

from .. import config, db, rate, transform

log = logging.getLogger(__name__)

router = Router(name="channel_post")

_MEDIA_GROUP_DEBOUNCE_SEC = 2.5


@dataclass
class _MediaGroupBuffer:
    messages: list[Message] = field(default_factory=list)
    flush_task: asyncio.Task | None = None


_buffers: dict[str, _MediaGroupBuffer] = defaultdict(_MediaGroupBuffer)
_buffers_lock = asyncio.Lock()


@router.channel_post()
async def on_source_channel_post(message: Message, bot: Bot) -> None:
    if message.chat.id != config.SOURCE_CHANNEL_ID:
        log.debug("Ignoring channel post from chat_id=%s", message.chat.id)
        return

    if message.media_group_id:
        await _handle_media_group_item(message, bot)
    else:
        await _handle_single(message, bot)


async def _handle_media_group_item(message: Message, bot: Bot) -> None:
    key = f"{message.chat.id}:{message.media_group_id}"
    async with _buffers_lock:
        buf = _buffers[key]
        buf.messages.append(message)
        if buf.flush_task and not buf.flush_task.done():
            buf.flush_task.cancel()
        buf.flush_task = asyncio.create_task(_flush_after_delay(key, bot))


async def _flush_after_delay(key: str, bot: Bot) -> None:
    try:
        await asyncio.sleep(_MEDIA_GROUP_DEBOUNCE_SEC)
    except asyncio.CancelledError:
        return
    async with _buffers_lock:
        buf = _buffers.pop(key, None)
    if not buf or not buf.messages:
        return
    await _send_media_group(buf.messages, bot)


async def _send_media_group(messages: list[Message], bot: Bot) -> None:
    # Preserve original order — Telegram assigns increasing message_id within a group
    messages.sort(key=lambda m: m.message_id)
    caption_source = next((m for m in messages if m.caption), None)
    # html_text preserves entities (bold, strikethrough, links) as HTML tags
    original_caption = caption_source.html_text if caption_source else ""

    retail_html = await _build_retail_caption(original_caption)

    media: list[InputMediaPhoto | InputMediaVideo] = []
    for i, m in enumerate(messages):
        cap = retail_html if i == 0 else None
        parse_mode = ParseMode.HTML if cap else None
        if m.photo:
            media.append(InputMediaPhoto(
                media=m.photo[-1].file_id, caption=cap, parse_mode=parse_mode,
            ))
        elif m.video:
            media.append(InputMediaVideo(
                media=m.video.file_id, caption=cap, parse_mode=parse_mode,
            ))
        else:
            log.warning("Unsupported media type in group at msg %s", m.message_id)
    if not media:
        return
    try:
        sent = await bot.send_media_group(
            chat_id=config.DEST_CHANNEL_ID, media=media,
        )
    except Exception:
        log.exception("send_media_group failed")
        return
    # Persist mapping (source anchor = first message id, dest anchor = first returned)
    if sent:
        db.record_message_map(
            source_chat=messages[0].chat.id,
            source_message_id=messages[0].message_id,
            dest_chat=sent[0].chat.id,
            dest_message_id=sent[0].message_id,
        )
    log.info(
        "Crossposted media group: source=%s dest=%s items=%d",
        messages[0].message_id, sent[0].message_id if sent else "?", len(media),
    )


async def _handle_single(message: Message, bot: Bot) -> None:
    # html_text picks either message.text or message.caption and preserves entities as HTML tags
    text = message.html_text if (message.text or message.caption) else ""
    retail_html = await _build_retail_caption(text)

    try:
        if message.photo:
            sent = await bot.send_photo(
                chat_id=config.DEST_CHANNEL_ID, photo=message.photo[-1].file_id,
                caption=retail_html, parse_mode=ParseMode.HTML,
            )
        elif message.video:
            sent = await bot.send_video(
                chat_id=config.DEST_CHANNEL_ID, video=message.video.file_id,
                caption=retail_html, parse_mode=ParseMode.HTML,
            )
        elif message.document:
            sent = await bot.send_document(
                chat_id=config.DEST_CHANNEL_ID, document=message.document.file_id,
                caption=retail_html, parse_mode=ParseMode.HTML,
            )
        elif message.text:
            sent = await bot.send_message(
                chat_id=config.DEST_CHANNEL_ID, text=retail_html,
                parse_mode=ParseMode.HTML, disable_web_page_preview=True,
            )
        else:
            log.info("Skipping unsupported source message type at %s", message.message_id)
            return
    except Exception:
        log.exception("Crosspost failed for msg %s", message.message_id)
        return

    db.record_message_map(
        source_chat=message.chat.id, source_message_id=message.message_id,
        dest_chat=sent.chat.id, dest_message_id=sent.message_id,
    )
    log.info("Crossposted: source=%s dest=%s", message.message_id, sent.message_id)


async def _build_retail_caption(source_text: str) -> str:
    usd_rub = await rate.get_usd_rub()
    html, meta = transform.transform_text(source_text, usd_rub)
    log.info(
        "Transformed: brand=%r usd=%s rub=%s exception=%s rate=%.4f",
        meta.get("brand"), meta.get("usd_prices"), meta.get("rub_prices"),
        meta.get("exception"), usd_rub,
    )
    return html
