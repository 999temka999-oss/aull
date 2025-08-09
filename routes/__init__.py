from functools import wraps
from flask import Blueprint, session, jsonify, request
from models import db, ActionLog

bp = Blueprint("root", __name__)  # базовый блупринт (пустой)

def login_required_api(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "uid" not in session:
            return jsonify({"ok": False, "reason": "unauthorized"}), 401
        return fn(*args, **kwargs)
    return wrapper

def log_action(user_id: int, action: str, **extra):
    log = ActionLog(
        user_id=user_id,
        action=action,
        amount=extra.get("amount", 0),
        old_balance=extra.get("old_balance"),
        new_balance=extra.get("new_balance"),
        soils_before=extra.get("soils_before"),
        soils_after=extra.get("soils_after"),
        ip=request.headers.get("X-Forwarded-For", request.remote_addr),
        ua=request.headers.get("User-Agent", ""),
    )
    db.session.add(log)
    db.session.commit()
