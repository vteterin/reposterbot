"""Admin commands in DM with the bot."""
import logging

from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from .. import config, rate, transform

log = logging.getLogger(__name__)

router = Router(name="admin")


def _is_admin(message: Message) -> bool:
    return bool(message.from_user and message.from_user.id in config.ADMIN_USER_IDS)


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("Sorry, you are not authorized to use this bot.")
        return
    await message.answer(
        "Reposterbot online.\n\n"
        "Commands:\n"
        "  /status — show configured channels, admins, current rate\n"
        "  /rate — refresh and show USD/RUB rate\n"
        "  /testpost <text> — dry-run a text through the transformer\n"
        "  /chatid — reply forwarded post from a channel to reveal its numeric ID"
    )


@router.message(Command("status"))
async def cmd_status(message: Message) -> None:
    if not _is_admin(message):
        return
    usd_rub = await rate.get_usd_rub()
    lines = [
        f"<b>Reposterbot status</b>",
        f"Source chat id: <code>{config.SOURCE_CHANNEL_ID}</code>",
        f"Dest chat id: <code>{config.DEST_CHANNEL_ID}</code>",
        f"Admins: <code>{sorted(config.ADMIN_USER_IDS)}</code>",
        f"USD/RUB: <b>{usd_rub:.4f}</b>",
        f"Exception brands: <code>{sorted(config.EXCEPTION_BRANDS)}</code>",
    ]
    await message.answer("\n".join(lines), parse_mode=ParseMode.HTML)


@router.message(Command("rate"))
async def cmd_rate(message: Message) -> None:
    if not _is_admin(message):
        return
    usd_rub = await rate.get_usd_rub()
    await message.answer(f"USD/RUB (CBR): <b>{usd_rub:.4f}</b>", parse_mode=ParseMode.HTML)


@router.message(Command("testpost"))
async def cmd_testpost(message: Message, command: CommandObject) -> None:
    if not _is_admin(message):
        return
    payload = command.args or ""
    if not payload.strip():
        await message.answer(
            "Usage: send /testpost as caption of a text sample, e.g.\n"
            "/testpost ONE BY TWO\\nкомбинезон\\n\\nSALE❗️\\n40 $"
        )
        return
    usd_rub = await rate.get_usd_rub()
    html, meta = transform.transform_text(payload, usd_rub)
    diag = (
        f"brand={meta['brand']!r} usd={meta['usd_price']} "
        f"rub={meta['rub_price']} exception={meta['exception']}"
    )
    await message.answer(f"<pre>{diag}</pre>\n\n{html}", parse_mode=ParseMode.HTML)


@router.channel_post(Command("chatid"))
async def channel_chatid(message: Message) -> None:
    # Admin-only reveal of a channel's numeric ID by /chatid inside the channel
    await message.reply(f"chat_id: <code>{message.chat.id}</code>", parse_mode=ParseMode.HTML)


@router.message()
async def catchall(message: Message) -> None:
    if not _is_admin(message):
        return
    if message.forward_from_chat:
        await message.reply(
            f"Forwarded from chat_id: <code>{message.forward_from_chat.id}</code>",
            parse_mode=ParseMode.HTML,
        )
