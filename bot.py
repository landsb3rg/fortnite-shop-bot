import asyncio
import requests
import pytz
import os
import json
from telegram import (
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

TOKEN = os.environ.get("TOKEN")
CHAT_ID = int(os.environ.get("CHAT_ID"))
ADMIN_ID = int(os.environ.get("ADMIN_ID"))

SHOP_URL = "https://www.fortnite.com/item-shop"
API_URL = "https://fortnite-api.com/v2/shop"
CACHE_FILE = "shop_cache.json"

moscow_tz = pytz.timezone("Europe/Moscow")


# =====================
# Работа с кэшем
# =====================

def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    with open(CACHE_FILE, "r") as f:
        return json.load(f)

def save_cache(data):
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)


# =====================
# Получение магазина
# =====================

def get_shop_data():
    response = requests.get(API_URL)
    data = response.json()["data"]

    shop_hash = data["hash"]
    image_url = data["image"]

    items = []
    for entry in data["entries"][:10]:
        name = entry["items"][0]["name"]
        rarity = entry["items"][0]["rarity"]["displayValue"]
        price = entry["finalPrice"]
        items.append(f"{name} — {price} V-Bucks ({rarity})")

    return shop_hash, image_url, items


# =====================
# Отправка магазина
# =====================

async def send_shop(chat_id, force=False):
    bot = Bot(token=TOKEN)
    shop_hash, image_url, items = get_shop_data()
    cache = load_cache()

    if cache.get("last_hash") == shop_hash and not force:
        return

    save_cache({"last_hash": shop_hash})

    text_items = "\n".join(items)

    caption = f"""🛒 Магазин Fortnite обновился!

🔥 Новые предметы:
{text_items}
"""

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Открыть магазин", url=SHOP_URL)]
    ])

    await bot.send_photo(
        chat_id=chat_id,
        photo=image_url,
        caption=caption[:1024],
        reply_markup=keyboard
    )

    await bot.send_message(ADMIN_ID, "✅ Магазин успешно опубликован")


# =====================
# Команды
# =====================

async def manual_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_shop(update.effective_chat.id, force=True)

async def new_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _, _, items = get_shop_data()
    await update.message.reply_text("🔥 Новые предметы:\n\n" + "\n".join(items))


# =====================
# Запуск
# =====================

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("shop", manual_shop))
    app.add_handler(CommandHandler("new", new_items))

    scheduler = AsyncIOScheduler(timezone=moscow_tz)
    scheduler.add_job(lambda: asyncio.create_task(send_shop(CHAT_ID)),
                      "cron", hour=3, minute=0)
    scheduler.start()

    print("ULTRA бот запущен")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
