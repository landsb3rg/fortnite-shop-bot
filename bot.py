import asyncio
import requests
import pytz
import os
import sqlite3
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
ADMIN_ID = int(os.getenv("ADMIN_ID"))

SHOP_URL = "https://www.fortnite.com/item-shop"
API_URL = "https://fortnite-api.com/v2/shop"

moscow_tz = pytz.timezone("Europe/Moscow")

# ==========================
# DATABASE
# ==========================

conn = sqlite3.connect("bot.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS chats (
    chat_id INTEGER PRIMARY KEY
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS watchlist (
    user_id INTEGER,
    skin_name TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS shop_cache (
    id INTEGER PRIMARY KEY,
    hash TEXT
)
""")

conn.commit()

# ==========================
# API
# ==========================

def get_shop():
    try:
        r = requests.get(API_URL, timeout=10)
        data = r.json()["data"]
        return data
    except:
        return None

# ==========================
# WATCH CHECK
# ==========================

async def check_watchlist(items):
    bot = Bot(token=TOKEN)
    cursor.execute("SELECT user_id, skin_name FROM watchlist")
    rows = cursor.fetchall()

    for user_id, skin in rows:
        for item in items:
            if skin.lower() in item["name"].lower():
                await bot.send_message(
                    user_id,
                    f"🚨 Скин {item['name']} появился в магазине!"
                )

# ==========================
# SEND SHOP
# ==========================

async def send_shop(force=False):
    bot = Bot(token=TOKEN)
    data = get_shop()
    if not data:
        return

    shop_hash = data["hash"]
    image_url = data["image"]

    cursor.execute("SELECT hash FROM shop_cache WHERE id=1")
    row = cursor.fetchone()

    if row and row[0] == shop_hash and not force:
        return

    cursor.execute("DELETE FROM shop_cache")
    cursor.execute("INSERT INTO shop_cache (id, hash) VALUES (1, ?)", (shop_hash,))
    conn.commit()

    items = []
    for entry in data["entries"][:8]:
        item = entry["items"][0]
        items.append({
            "name": item["name"],
            "price": entry["finalPrice"],
            "rarity": item["rarity"]["displayValue"]
        })

    text = "\n".join(
        [f"{i['name']} — {i['price']} V-Bucks ({i['rarity']})"
         for i in items]
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Открыть магазин", url=SHOP_URL)]
    ])

    cursor.execute("SELECT chat_id FROM chats")
    chats = cursor.fetchall()

    for chat_id in chats:
        await bot.send_photo(
            chat_id=chat_id[0],
            photo=image_url,
            caption=f"🛒 Магазин обновился!\n\n{text}"[:1024],
            reply_markup=keyboard
        )

    await check_watchlist(items)

# ==========================
# COMMANDS
# ==========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    cursor.execute("INSERT OR IGNORE INTO chats VALUES (?)", (chat_id,))
    conn.commit()
    await update.message.reply_text("✅ Чат подключён к обновлениям!")

async def shop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_shop(force=True)

async def watch_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Пример: /watch Travis Scott")
        return

    skin_name = " ".join(context.args)
    user_id = update.effective_user.id

    cursor.execute(
        "INSERT INTO watchlist VALUES (?, ?)",
        (user_id, skin_name)
    )
    conn.commit()

    await update.message.reply_text(f"👀 Теперь отслеживаем: {skin_name}")

# ==========================
# MAIN
# ==========================

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("shop", shop_cmd))
    app.add_handler(CommandHandler("watch", watch_cmd))

    scheduler = AsyncIOScheduler(timezone=moscow_tz)
    scheduler.add_job(
        lambda: asyncio.create_task(send_shop()),
        "cron",
        hour=3,
        minute=0
    )
    scheduler.start()

    print("PRO MAX BOT STARTED")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
