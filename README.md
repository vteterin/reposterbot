# reposterbot

Reposter bot for a wife's pet project in Telegram — crossposts from a private wholesale channel to a public retail channel:

- Reposts photos, videos and albums (media groups) unchanged
- Rewrites the caption: recalculates the `X $` wholesale price into rubles via
  formula (with brand-specific overrides), appends a retail footer with inline links

Built for a specific two-channel setup — configured via `.env`, not generic.

## Formula

Wholesale price is `X` USD. Retail is computed as:

```
default:   X * 2 * rate * 1.1  +  (X * 0.2) * rate * 1.1
brands ONE MONE / GVR / VANN:   X * 2 * rate * 1.1
```

`rate` is USD/RUB from `cbr-xml-daily.ru`, cached for one hour.

## Retail suffix

Appended to every crossposted caption:

```
Подробнее о нас и условиях работы ⬅️   → https://t.me/kshop_cloth/6049
Цена указана уже с учетом доставки 🤩
Сделать заказ или задать вопрос ⬅️      → http://t.me/kshop_administrator

Дарим подарки за каждый заказ!
```

## Setup

1. Create the bot in `@BotFather`, get the token
2. Add the bot as **admin** in both channels:
   - source (wholesale) — needs read access
   - destination (retail) — needs "Post Messages"
3. Copy `.env.example` to `.env` and fill in the values
4. Find channel numeric IDs — with the bot running, forward any post from a channel to the bot in a DM; the bot replies with the channel's `chat_id`. Put those into `.env`

```bash
cp .env.example .env
# edit .env

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python3 -m src.bot
```

## Deploy as systemd service

```bash
sudo scripts/install-systemd.sh
sudo systemctl status reposterbot
sudo journalctl -u reposterbot -f
```

## Admin commands (in DM with the bot)

- `/status` — configured channels, admin allowlist, current USD/RUB
- `/rate` — force refresh USD/RUB
- `/testpost <text>` — dry-run transform (no post sent to channel)
- Forward any message from a channel to see its numeric `chat_id`

## Layout

```
src/
  bot.py                 aiogram entrypoint
  config.py              env loading, constants
  db.py                  sqlite for rate cache + message map
  rate.py                CBR USD/RUB with hourly cache
  transform.py           price parser + formula + retail suffix
  handlers/
    channel_post.py      crosspost logic, media-group buffering
    admin.py             DM commands for admins
```
