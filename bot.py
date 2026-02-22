import os
import logging
import datetime
import asyncio
import sqlite3
import requests
import pytz

from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

SHOP_URL = "https://www.fortnite.com/item-shop"
API_URL = "https://fortnite-api.com/v2/shop"

moscow_tz = pytz.timezone("Europe/Moscow")

# ================= DATABASE =================
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS chats (chat_id INTEGER PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS watchlist (user_id INTEGER, skin TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS cache (id INTEGER PRIMARY KEY, hash TEXT)")
conn.commit()

# ================= API =================
def get_shop():
    try:
        r = requests.get(API_URL, timeout=10)
        return r.json()["data"]
    except:
        return None

# ================= SEND SHOP =================
async def send_shop(app):
    bot = Bot(TOKEN)
    data = get_shop()
    if not data:
        await bot.send_message(ADMIN_ID, "❌ Ошибка API")
        return

    shop_hash = data.get("hash", "")
    image = data.get("image", "")

    cursor.execute("SELECT hash FROM cache WHERE id=1")
    row = cursor.fetchone()

    if row and row[0] == shop_hash:
        return

    cursor.execute("DELETE FROM cache")
    cursor.execute("INSERT INTO cache VALUES (1, ?)", (shop_hash,))
    conn.commit()

    items = []
    for e in data.get("entries", [])[:6]:
        item = e["items"][0]
        items.append(f"{item['name']} — {e['finalPrice']} V-Bucks")

    text = "\n".join(items)

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Открыть магазин", url=SHOP_URL)]])

    cursor.execute("SELECT chat_id FROM chats")
    chats = cursor.fetchall()
    for chat in chats:
        await bot.send_photo(
            chat_id=chat[0],
            photo=image,
            caption=f"🛒 Магазин обновился!\n\n{text}"[:1024],
            reply_markup=keyboard
        )

    # Отслеживание скинов
    cursor.execute("SELECT user_id, skin FROM watchlist")
    watch = cursor.fetchall()
    for user_id, skin in watch:
        for i in items:
            if skin.lower() in i.lower():
                await bot.send_message(user_id, f"🚨 {skin} появился в магазине!")

# ================= COMMANDS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cursor.execute("INSERT OR IGNORE INTO chats VALUES (?)", (update.effective_chat.id,))
    conn.commit()
    await update.message.reply_text("✅ Чат подключён!")

async def shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_shop(context.application)

async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    skin = " ".join(context.args)
    cursor.execute("INSERT INTO watchlist VALUES (?, ?)", (update.effective_user.id, skin))
    conn.commit()
    await update.message.reply_text(f"👀 Отслеживаем {skin}")

async def unwatch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    skin = " ".join(context.args)
    cursor.execute("DELETE FROM watchlist WHERE user_id=? AND skin=?", (update.effective_user.id, skin))
    conn.commit()
    await update.message.reply_text(f"❌ Больше не отслеживаем {skin}")

async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Ваш Chat ID: {update.effective_chat.id}")

# ================= SCHEDULER =================
async def scheduler(app):
    while True:
        now = datetime.datetime.now(moscow_tz)
        target = now.replace(hour=3, minute=0, second=0, microsecond=0)
        if now > target:
            target += datetime.timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        logging.info(f"Следующий магазин через {int(wait_seconds)} секунд")
        await asyncio.sleep(wait_seconds)
        await send_shop(app)

# ================= MAIN =================
def main():
    app = Application.builder().token(TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("shop", shop))
    app.add_handler(CommandHandler("watch", watch))
    app.add_handler(CommandHandler("unwatch", unwatch))
    app.add_handler(CommandHandler("id", get_chat_id))

    async def run_all():
        asyncio.create_task(scheduler(app))
        await app.run_polling()

    asyncio.run(run_all())

if __name__ == "__main__":
    main()
