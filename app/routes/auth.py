from flask import Blueprint, request, jsonify, session, current_app
from app.utils.tg_auth import verify_init_data_ed25519, TgAuthError
from app.models import db, Player

bp_auth = Blueprint("auth", __name__)

@bp_auth.post("/validate")
def validate():
    payload = request.get_json(silent=True) or {}
    init_data = payload.get("initData")
    if not init_data:
        return jsonify(ok=False, error="initData required"), 400

    try:
        res = verify_init_data_ed25519(
            init_data_raw=init_data,
            bot_id=current_app.config.get("BOT_ID", ""),
            public_key_hex=current_app.config.get("TG_SIGNATURE_PUBLIC_KEY_HEX", ""),
            ttl=current_app.config.get("AUTH_TTL", 300),
        )
    except TgAuthError as e:
        return jsonify(ok=False, error=str(e)), 401

    u = res["user"]
    uid = int(u["id"])
    display_name = u.get("first_name") or u.get("username") or "Игрок"

    player = db.session.get(Player, uid)
    if player is None:
        player = Player(
            user_id=uid,
            username=u.get("username"),
            first_name=u.get("first_name"),
            last_name=u.get("last_name"),
            display_name=display_name,
            balance=100,
            fields_owned=2,
        )
        db.session.add(player)
    else:
        player.username = u.get("username")
        player.first_name = u.get("first_name")
        player.last_name = u.get("last_name")
        player.display_name = display_name
        player.touch()
    db.session.commit()

    # Проверяем, не заблокирован ли игрок
    if player.is_blocked:
        return jsonify(ok=False, error="user_blocked", blocked_reason=player.blocked_reason or "Аккаунт заблокирован"), 403

    session.clear()
    session.permanent = True
    session["uid"] = uid

    return jsonify(ok=True, player=player.to_public_dict())
