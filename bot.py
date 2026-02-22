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

TOKEN = os.getenv("TOKEN")
CHAT_ID = int(os.getenv("CHAT_ID"))
ADMIN_ID = int(os.getenv("ADMIN_ID"))

SHOP_URL = "https://www.fortnite.com/item-shop"
API_URL = "https://fortnite-api.com/v2/shop"
CACHE_FILE = "shop_cache.json"

moscow_tz = pytz.timezone("Europe/Moscow")


# =====================
# Safe request
# =====================

def safe_request(url):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


# =====================
# Cache
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
# Shop data
# =====================

def get_shop_data():
    data = safe_request(API_URL)
    if not data:
        return None, None, []

    data = data["data"]

    shop_hash = data["hash"]
    image_url = data["image"]

    items = []
    for entry in data["entries"]:
        name = entry["items"][0]["name"]
        rarity = entry["items"][0]["rarity"]["displayValue"]
        price = entry["finalPrice"]
        items.append({
            "name": name,
            "rarity": rarity,
            "price": price
        })

    return shop_hash, image_url, items


# =====================
# Send shop
# =====================

async def send_shop(chat_id, force=False):
    bot = Bot(token=TOKEN)
    shop_hash, image_url, items = get_shop_data()

    if not shop_hash:
        await bot.send_message(ADMIN_ID, "❌ Ошибка получения магазина")
        return

    cache = load_cache()

    if cache.get("last_hash") == shop_hash and not force:
        return

    save_cache({"last_hash": shop_hash})

    top_items = items[:8]
    text_items = "\n".join(
        [f"{i['name']} — {i['price']} V-Bucks ({i['rarity']})"
         for i in top_items]
    )

    caption = f"""🛒 Магазин обновился!

🔥 Топ предметы:
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

    await bot.send_message(ADMIN_ID, "✅ Магазин опубликован")


# =====================
# Commands
# =====================

async def shop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_shop(update.effective_chat.id, force=True)

async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _, _, items = get_shop_data()
    text = "\n".join(
        [f"{i['name']} — {i['price']} ({i['rarity']})"
         for i in items[:10]]
    )
    await update.message.reply_text("🔥 Текущие предметы:\n\n" + text)

async def rarity_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Пример: /rarity Epic")
        return

    rarity_filter = context.args[0].lower()
    _, _, items = get_shop_data()

    filtered = [
        i for i in items
        if i["rarity"].lower() == rarity_filter
    ]

    if not filtered:
        await update.message.reply_text("Нет предметов этой редкости.")
        return

    text = "\n".join(
        [f"{i['name']} — {i['price']} V-Bucks"
         for i in filtered]
    )

    await update.message.reply_text(f"🎯 {rarity_filter.upper()} предметы:\n\n{text}")


# =====================
# Main
# =====================

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("shop", shop_command))
    app.add_handler(CommandHandler("new", new_command))
    app.add_handler(CommandHandler("rarity", rarity_command))

    scheduler = AsyncIOScheduler(timezone=moscow_tz)
    scheduler.add_job(
        lambda: asyncio.create_task(send_shop(CHAT_ID)),
        "cron",
        hour=3,
        minute=0
    )
    scheduler.start()

    print("MEGA BOT STARTED")
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
