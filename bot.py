import asyncio
import requests
import pytz
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os

TOKEN = os.environ.get("TOKEN")
CHAT_ID = int(os.environ.get("CHAT_ID"))

SHOP_URL = "https://www.fortnite.com/item-shop"
API_URL = "https://fortnite-api.com/v2/shop"

moscow_tz = pytz.timezone("Europe/Moscow")

async def send_shop_update():
    bot = Bot(token=TOKEN)

    try:
        response = requests.get(API_URL)
        data = response.json()
        image_url = data["data"]["image"]

        caption = "🛒 Обновление магазина Fortnite!\n\nНовый магазин уже доступен 👇"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Открыть магазин", url=SHOP_URL)]
        ])

        await bot.send_photo(
            chat_id=CHAT_ID,
            photo=image_url,
            caption=caption,
            reply_markup=keyboard
        )

    except Exception:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=f"🛒 Магазин обновился!\n{SHOP_URL}"
        )

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    scheduler = AsyncIOScheduler(timezone=moscow_tz)
    scheduler.add_job(send_shop_update, "cron", hour=3, minute=0)
    scheduler.start()

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
