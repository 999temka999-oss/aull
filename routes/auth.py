import base64, binascii, time, json, hashlib, secrets
from urllib.parse import parse_qsl
from flask import Blueprint, request, jsonify, session, render_template
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
from sqlalchemy.exc import IntegrityError

from config import Config
from models import db, Player, ReplayStamp
from . import log_action

bp_auth = Blueprint("auth", __name__)

_verify_key = VerifyKey(bytes.fromhex(Config.TG_PUBLIC_KEY_HEX))

class ReplayError(Exception):
    pass

def _sorted_pairs_string(items: dict) -> str:
    return "\n".join(f"{k}={items[k]}" for k in sorted(items.keys()))

def verify_init_data_ed25519(init_data: str) -> dict:
    if not init_data:
        raise ValueError("initData missing")

    items = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=False))
    signature_b64 = items.pop("signature", None)
    items.pop("hash", None)

    if Config.DEBUG_AUTH:
        print("\n=== AUTH DEBUG / PARSE ===")
        print("BOT_ID(last4):", Config.BOT_ID[-4:])
        print("PUBKEY_HEX(prefix8):", Config.TG_PUBLIC_KEY_HEX[:8], "…")
        print("FIELDS:", sorted(items.keys()))
        print("SIGNATURE(b64,len):", (len(signature_b64) if signature_b64 else 0))
        print("initData(first 160):", init_data[:160])

    if not signature_b64:
        raise ValueError("signature missing")

    try:
        auth_date = int(items.get("auth_date", "0"))
    except ValueError:
        auth_date = 0
    age = time.time() - auth_date

    if Config.DEBUG_AUTH:
        print("AUTH_DATE:", auth_date, "| AGE(s):", int(age), "| TTL:", Config.AUTH_TTL)

    if auth_date <= 0 or age > Config.AUTH_TTL:
        raise ValueError("auth expired")

    stamp_src = f"{signature_b64}:{auth_date}".encode("utf-8")
    stamp_hash = hashlib.sha256(stamp_src).hexdigest()

    dcs = _sorted_pairs_string(items)
    message = f"{Config.BOT_ID}:WebAppData\n{dcs}".encode("utf-8")

    pad = "=" * ((4 - len(signature_b64) % 4) % 4)
    try:
        signature = base64.urlsafe_b64decode((signature_b64 + pad).encode("utf-8"))
    except binascii.Error:
        raise ValueError("invalid signature encoding")

    try:
        _verify_key.verify(message, signature)
    except BadSignatureError:
        raise ValueError("invalid signature")

    try:
        db.session.add(ReplayStamp(stamp_hash=stamp_hash, auth_date=auth_date))
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        if Config.DEBUG_AUTH: print("ANTI-REPLAY: duplicate → replay detected")
        raise ReplayError("replay detected")

    user_raw = items.get("user")
    if not user_raw:
        raise ValueError("user payload missing")

    if Config.DEBUG_AUTH: print("=== AUTH DEBUG / OK ===\n")
    return json.loads(user_raw)

@bp_auth.get("/")
def index():
    return render_template("index.html", authed=("uid" in session))

@bp_auth.post("/auth/verify")
def auth_verify():
    payload = request.get_json(silent=True) or {}
    init_data = payload.get("initData")

    if Config.DEBUG_AUTH:
        ua = request.headers.get("User-Agent","")
        print("REQ /auth/verify  UA:", ua[:100])
        print("initData present?:", isinstance(init_data, str), "| len:", (len(init_data) if isinstance(init_data,str) else 0))
        print("TG platform/version:", payload.get("platform"), payload.get("version"))

    if not init_data:
        return ("initData required", 400)

    try:
        user = verify_init_data_ed25519(init_data)
    except ReplayError:
        return ("Повторная авторизация обнаружена. Пожалуйста, перезайдите в Mini App.", 401)
    except Exception as e:
        return (f"verification failed: {e}", 401)

    uid = int(user["id"])
    name = user.get("first_name") or user.get("username") or "Игрок"

    player = Player.query.get(uid)
    if not player:
        player = Player(user_id=uid, name=name)
        db.session.add(player)
    else:
        player.name = name
    db.session.commit()

    session.permanent = True
    session["uid"] = uid
    session["name"] = player.name
    session["act"] = secrets.token_hex(16)  # action-token для POST

    log_action(uid, "login")
    return jsonify({"ok": True, "name": player.name})

@bp_auth.post("/auth/logout")
def auth_logout():
    uid = session.get("uid")
    session.clear()
    if uid:
        log_action(int(uid), "logout")
    return jsonify({"ok": True})

@bp_auth.get("/api/me")
def api_me():
    if "uid" not in session:
        return jsonify({"ok": False, "reason": "unauthorized"}), 401
    return jsonify({"ok": True, "name": session.get("name", "Игрок")})
