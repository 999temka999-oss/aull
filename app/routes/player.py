# app/routes/player.py
from __future__ import annotations
from datetime import datetime, timezone
from flask import Blueprint, jsonify, session

from app.models import db, Player, ActionNonce, Plot, Inventory
from app.logic.crops import wheat_stage_info, crop_stage_info

bp_player = Blueprint("player", __name__)

def _utc_now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)

def _as_utc(dt):
    """Приводим datetime из БД к offset‑aware UTC (если naive — считаем, что это UTC)."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)

@bp_player.get("/state")
def state():
    uid = session.get("uid")
    if not uid:
        return jsonify(ok=False, error="unauthorized"), 401

    player = db.session.get(Player, uid)
    if not player:
        return jsonify(ok=False, error="player_not_found"), 404

    # выдаём/обновляем nonce
    nonce = ActionNonce.issue_for(uid, ttl_sec=60)

    # собираем грядки с таймерами
    rows = db.session.query(Plot).filter_by(user_id=uid).all()
    plots = []
    for r in rows:
        planted_utc = _as_utc(r.planted_at)
        info = {}
        if r.crop_key and planted_utc:
            info = crop_stage_info(r.crop_key, planted_utc)

        plots.append({
            "idx": r.idx,
            "crop_key": r.crop_key or None,
            "stage": info.get("stage"),
            "ready_at": info.get("ready_at"),
            "ready_at_unix_ms": info.get("ready_at_unix_ms"),
            "remaining_ms": info.get("remaining_ms"),
            "planted_at_iso": planted_utc.isoformat() if planted_utc else None,
            "planted_at_unix_ms": int(planted_utc.timestamp() * 1000) if planted_utc else None,
        })

    # фиксируем потенциальные изменения от issue_for
    db.session.commit()

    st = player.to_public_dict()
    st["action_nonce"] = nonce.value
    st["nonce_expiry"] = nonce.expires_at.isoformat()
    st["server_time_unix_ms"] = _utc_now_ms()
    st["plots"] = plots

    return jsonify(ok=True, state=st)

@bp_player.get("/inventory")
def inventory():
    uid = session.get("uid")
    if not uid:
        return jsonify(ok=False, error="unauthorized"), 401

    rows = db.session.query(Inventory).filter_by(user_id=uid).all()
    items = [{"item_key": r.item_key, "qty": r.qty} for r in rows]
    return jsonify(ok=True, inventory=items)
