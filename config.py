# config.py
import os, re
from datetime import timedelta
from dotenv import load_dotenv
load_dotenv()

def _normalize_db_url(url: str) -> str:
    # Render часто даёт postgres://, SQLAlchemy любит postgresql+psycopg2://
    if not url: 
        return ""
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql+psycopg2://" + url[len("postgres://"):]
    return url

class Config:
    BOT_ID = os.getenv("BOT_ID", "").strip()
    TG_PUBLIC_KEY_HEX = os.getenv("TG_PUBLIC_KEY_HEX", "").strip()
    AUTH_TTL = int(os.getenv("AUTH_TTL", "86400"))

    SECRET_KEY = os.getenv("FLASK_SECRET", "dev-secret")
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)

    # Главное: берём DATABASE_URL (Postgres), иначе — локальный SQLite
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(
        os.getenv("DATABASE_URL", "")
    ) or os.getenv("DB_URL", "sqlite:///mini_farm.db")

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG_AUTH = False

    @staticmethod
    def validate():
        if not Config.BOT_ID.isdigit():
            raise RuntimeError("BOT_ID должен состоять из цифр.")
        key = (Config.TG_PUBLIC_KEY_HEX or "").strip()
        key = key[2:] if key.lower().startswith("0x") else key
        if not re.fullmatch(r"[0-9a-fA-F]{64}", key or ""):
            raise RuntimeError("TG_PUBLIC_KEY_HEX: нужен ровно 64-символьный hex без пробелов.")
