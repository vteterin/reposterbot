"""Runtime config loaded from .env."""
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
SOURCE_CHANNEL_ID = int(os.environ["SOURCE_CHANNEL_ID"]) if os.environ.get("SOURCE_CHANNEL_ID") else None
DEST_CHANNEL_ID = int(os.environ["DEST_CHANNEL_ID"]) if os.environ.get("DEST_CHANNEL_ID") else None
ADMIN_USER_IDS = {int(x.strip()) for x in os.environ.get("ADMIN_USER_IDS", "").split(",") if x.strip()}
DB_PATH = os.environ.get("DB_PATH", "data/bot.db")
CBR_RATE_URL = os.environ.get("CBR_RATE_URL", "https://www.cbr-xml-daily.ru/daily_json.js")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

# Brands that skip the +20% override component
EXCEPTION_BRANDS = {"ONE MONE", "GVR", "VANN"}

# Retail suffix — appended to every crossposted message
RETAIL_SUFFIX_LINES = [
    ("Подробнее о нас и условиях работы ⬅️", "https://t.me/kshop_cloth/6049"),
    ("Цена указана уже с учетом доставки \U0001f929", None),
    ("Сделать заказ или задать вопрос ⬅️", "http://t.me/kshop_administrator"),
]
RETAIL_SUFFIX_FOOTER = "Дарим подарки за каждый заказ!"
