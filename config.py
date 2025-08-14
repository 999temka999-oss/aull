"""Конфигурация приложения фермерской игры."""

import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    """
    Класс конфигурации приложения.
    
    Содержит настройки базы данных, аутентификации,
    игровой механики и магазина.
    """
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key")
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    BOT_ID = os.getenv("BOT_ID", "")
    TG_SIGNATURE_PUBLIC_KEY_HEX = os.getenv("TG_SIGNATURE_PUBLIC_KEY_HEX", "")
    AUTH_TTL = int(os.getenv("AUTH_TTL", "300"))

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    FIELD_MAX = int(os.getenv("FIELD_MAX", "16"))
    FIELD_COST = int(os.getenv("FIELD_COST", "5"))

    # Цены семян (прогрессия x2)
    SHOP_WHEAT_PRICE = int(os.getenv("SHOP_WHEAT_PRICE", "5"))
    SHOP_CARROT_PRICE = int(os.getenv("SHOP_CARROT_PRICE", "10"))
    SHOP_WATERMELON_PRICE = int(os.getenv("SHOP_WATERMELON_PRICE", "20"))
    SHOP_PUMPKIN_PRICE = int(os.getenv("SHOP_PUMPKIN_PRICE", "40"))
    SHOP_ONION_PRICE = int(os.getenv("SHOP_ONION_PRICE", "80"))
    
    SHOP_ITEMS = {
        "seed_wheat": {"title": "Семена пшеницы", "price": SHOP_WHEAT_PRICE},
        "seed_carrot": {"title": "Семена моркови", "price": SHOP_CARROT_PRICE},
        "seed_watermelon": {"title": "Семена арбуза", "price": SHOP_WATERMELON_PRICE},
        "seed_pumpkin": {"title": "Семена тыквы", "price": SHOP_PUMPKIN_PRICE},
        "seed_onion": {"title": "Семена лука", "price": SHOP_ONION_PRICE},
    }

    SELL_PRICES = {
        "crop_wheat": 10,      # базовая цена
        "crop_carrot": 20,     # x2 от пшеницы
        "crop_watermelon": 40, # x2 от моркови
        "crop_pumpkin": 80,    # x2 от арбуза
        "crop_onion": 160,     # x2 от тыквы
    }

    # Время роста культур в миллисекундах (прогрессия x1.2)
    WHEAT_GROW_MS = int(os.getenv("WHEAT_GROW_MS", "120000"))      # 2 минуты
    CARROT_GROW_MS = int(os.getenv("CARROT_GROW_MS", "144000"))    # 2.4 минуты
    WATERMELON_GROW_MS = int(os.getenv("WATERMELON_GROW_MS", "172800")) # 2.88 минуты
    PUMPKIN_GROW_MS = int(os.getenv("PUMPKIN_GROW_MS", "207360"))  # 3.456 минуты
    ONION_GROW_MS = int(os.getenv("ONION_GROW_MS", "248832"))      # 4.147 минуты
    
    CROP_GROWTH_TIME = {
        "wheat": WHEAT_GROW_MS,
        "carrot": CARROT_GROW_MS,
        "watermelon": WATERMELON_GROW_MS,
        "pumpkin": PUMPKIN_GROW_MS,
        "onion": ONION_GROW_MS,
    }

    # Рост пшеницы (для обратной совместимости)
    WHEAT_STAGE_SPROUT = int(os.getenv("WHEAT_STAGE_SPROUT", "30"))
    WHEAT_STAGE_YOUNG  = int(os.getenv("WHEAT_STAGE_YOUNG",  "90"))
    WHEAT_STAGE_MATURE = int(os.getenv("WHEAT_STAGE_MATURE", "120"))
