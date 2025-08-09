import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()
BOT_TOKEN  = os.getenv("BOT_TOKEN", "").strip()
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()

if not BOT_TOKEN or not WEBAPP_URL:
    raise RuntimeError("BOT_TOKEN и/или WEBAPP_URL не заданы в .env")

# Текст приветствия
WELCOME = (
    "Привет! 👋\n"
    "Это мини-ферма. Открой её внутри Telegram WebApp.\n\n"
    "Нажми кнопку ниже — «Открыть ферму»."
)

def webapp_keyboard_inline():
    # Инлайн-кнопка над сообщением
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton(text="🌾 Открыть ферму", web_app=WebAppInfo(url=WEBAPP_URL))]
    ])
    return kb

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        WELCOME,
        reply_markup=webapp_keyboard_inline()
    )

def main():
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", cmd_start))
    print("Bot polling started. Press Ctrl+C to stop.")
    application.run_polling()

if __name__ == "__main__":
    main()
