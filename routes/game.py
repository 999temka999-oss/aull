import time
from datetime import datetime
from flask import Blueprint, jsonify, session, request
from models import db, Player
from . import login_required_api, log_action

bp_game = Blueprint("game", __name__)

PRICE_OPEN_SOIL = 10
MAX_SOILS = 16
RATE_LIMIT_SEC = 0.7   # 700 мс между действиями

def _check_action_token():
    token = request.headers.get("X-Action-Token", "")
    return token and token == session.get("act")

@bp_game.get("/api/state")
@login_required_api
def api_state():
    player = Player.query.get(session["uid"])
    return jsonify({
        "ok": True,
        "user_id": player.user_id,
        "name": player.name,
        "soils_count": player.soils_count,
        "balance": player.balance,
        "action_token": session.get("act")
    })

@bp_game.post("/api/open_soil")
@login_required_api
def api_open_soil():
    # 1) Action-token
    if not _check_action_token():
        return jsonify({"ok": False, "error": "forbidden"}), 403

    # 2) Rate limit
    now = time.time()
    last = session.get("last_open_ts", 0.0)
    if now - last < RATE_LIMIT_SEC:
        return jsonify({"ok": False, "error": "too_fast"}), 429
    session["last_open_ts"] = now

    player = Player.query.get(session["uid"])

    if player.soils_count >= MAX_SOILS:
        return jsonify({"ok": False, "error": "max_reached"})

    if player.balance < PRICE_OPEN_SOIL:
        log_action(
            player.user_id, "open_soil_denied",
            amount=-PRICE_OPEN_SOIL,
            old_balance=player.balance, new_balance=player.balance,
            soils_before=player.soils_count, soils_after=player.soils_count
        )
        return jsonify({"ok": False, "error": "not_enough_money"})

    old_balance = player.balance
    old_soils   = player.soils_count

    player.balance -= PRICE_OPEN_SOIL
    player.soils_count += 1
    player.updated_at = datetime.utcnow()
    db.session.commit()

    log_action(
        player.user_id, "open_soil",
        amount=-PRICE_OPEN_SOIL,
        old_balance=old_balance, new_balance=player.balance,
        soils_before=old_soils, soils_after=player.soils_count
    )

    return jsonify({
        "ok": True,
        "soils_count": player.soils_count,
        "balance": player.balance
    })
