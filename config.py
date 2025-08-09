import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_ID = os.getenv("BOT_ID", "").strip()
    TG_PUBLIC_KEY_HEX = os.getenv("TG_PUBLIC_KEY_HEX", "").strip()
    AUTH_TTL = int(os.getenv("AUTH_TTL", "86400"))

    SECRET_KEY = os.getenv("FLASK_SECRET", "dev-secret")
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)

    SQLALCHEMY_DATABASE_URI = os.getenv("DB_URL", "sqlite:///mini_farm.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DEBUG_AUTH = False  # временно можно True для диагностики

    @staticmethod
    def validate():
        if not Config.BOT_ID.isdigit() or not Config.TG_PUBLIC_KEY_HEX:
            raise RuntimeError("BOT_ID / TG_PUBLIC_KEY_HEX не заданы корректно в .env")
