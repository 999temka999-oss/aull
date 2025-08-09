# app.py
from flask import Flask
from config import Config
from models import db
from routes import bp as bp_root
from routes.auth import bp_auth
from routes.game import bp_game
import os

def create_app() -> Flask:
    Config.validate()
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    app.register_blueprint(bp_root)
    app.register_blueprint(bp_auth)
    app.register_blueprint(bp_game)

    @app.after_request
    def security_headers(resp):
        resp.headers["X-Frame-Options"] = "SAMEORIGIN"
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return resp

    with app.app_context():
        db.create_all()
    return app

# <<< ВАЖНО: экспортируем объект для gunicorn app:app
app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
