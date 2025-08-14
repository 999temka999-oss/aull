"""Главный модуль фермерской игры.

Содержит фактори приложения Flask с настройкой
базы данных и маршрутов.
"""

import time
from flask import Flask
from config import Config
from app.models import db

def create_app():
    """
    Фабрика приложения Flask.
    
    Создает и настраивает приложение Flask,
    инициализирует базу данных и регистрирует маршруты.
    
    Returns:
        Flask: Настроенное приложение Flask
    """
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(Config)

    app.config["START_TIME"] = str(int(time.time()))
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    @app.after_request
    def no_cache(resp):
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp

    db.init_app(app)
    with app.app_context():
        db.create_all()

    from .routes.main import bp_main
    from .routes.auth import bp_auth
    from .routes.player import bp_player
    from .routes.actions import bp_actions

    app.register_blueprint(bp_main)
    app.register_blueprint(bp_auth, url_prefix="/auth")
    app.register_blueprint(bp_player, url_prefix="/api")
    app.register_blueprint(bp_actions, url_prefix="/api")

    return app
