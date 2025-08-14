from __future__ import annotations
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify, session, current_app
from sqlalchemy import select

from app.models import (
    db, Player, ActionNonce, ActionLog,
    check_rate_limit, Plot, add_inventory, Inventory
)
from app.logic.crops import wheat_stage_info, crop_stage_info

bp_actions = Blueprint("actions", __name__)

# --- helpers ---------------------------------------------------------

def _need_auth():
    uid = session.get("uid")
    if not uid:
        return None, (jsonify(ok=False, error="unauthorized"), 401)
    
    # Проверяем блокировку пользователя
    player = db.session.get(Player, uid)
    if player and player.is_blocked:
        return None, (jsonify(ok=False, error="user_blocked", blocked_reason=player.blocked_reason or "Аккаунт заблокирован"), 403)
    
    return uid, None

def _verify_nonce(uid: int, req) -> bool:
    presented = req.headers.get("X-Action-Nonce")
    nonce = db.session.get(ActionNonce, uid)
    if not nonce:
        return False
    ok = nonce.verify_and_rotate(ttl_sec=60, presented=presented)
    if ok:
        db.session.commit()
    return ok

def _server_now():
    return datetime.now(timezone.utc)

def _as_utc(dt: datetime | None) -> datetime | None:
    """Приводим datetime из БД к offset‑aware UTC (если naive — считаем, что это UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def _plots_payload(uid: int):
    rows = db.session.execute(select(Plot).where(Plot.user_id == uid)).scalars().all()
    out = []
    for r in rows:
        planted_utc = _as_utc(r.planted_at)
        info = {}
        if r.crop_key and planted_utc:
            try:
                info = crop_stage_info(r.crop_key, planted_utc) or {}
            except Exception:
                info = {}
        out.append({
            "idx": r.idx,
            "crop_key": r.crop_key or None,
            "stage": info.get("stage"),
            "ready_at": info.get("ready_at"),
            "ready_at_unix_ms": info.get("ready_at_unix_ms"),
            "remaining_ms": info.get("remaining_ms"),
            "planted_at_iso": planted_utc.isoformat() if planted_utc else None,
            "planted_at_unix_ms": int(planted_utc.timestamp() * 1000) if planted_utc else None,
        })
    return out

def _state_payload(player: Player, now_ms: int):
    nonce = db.session.get(ActionNonce, player.user_id)
    st = player.to_public_dict()
    st["action_nonce"] = nonce.value
    st["nonce_expiry"] = nonce.expires_at.isoformat()
    st["server_time_unix_ms"] = now_ms
    return st

# --- actions ---------------------------------------------------------

@bp_actions.post("/action/buy_field")
def buy_field():
    uid, err = _need_auth()
    if err:
        return err
    if not _verify_nonce(uid, request):
        return jsonify(ok=False, error="bad_or_expired_nonce"), 409
    if not check_rate_limit(uid, "buy_field", max_per_window=6, window_sec=5):
        return jsonify(ok=False, error="rate_limited"), 429

    cost = current_app.config.get("FIELD_COST", 5)
    max_fields = current_app.config.get("FIELD_MAX", 16)

    try:
        player = db.session.execute(
            select(Player).where(Player.user_id == uid).with_for_update()
        ).scalar_one_or_none()
        if not player:
            return jsonify(ok=False, error="player_not_found"), 404
        if player.fields_owned >= max_fields:
            return jsonify(ok=False, error="max_fields"), 400
        if player.balance < cost:
            return jsonify(ok=False, error="not_enough_money"), 400

        player.balance -= cost
        player.fields_owned += 1
        db.session.add(ActionLog(user_id=uid, action="buy_field"))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    now_ms = int(_server_now().timestamp() * 1000)
    st = _state_payload(player, now_ms)
    st["plots"] = _plots_payload(uid)
    return jsonify(ok=True, state=st, bought_index=player.fields_owned - 1)

@bp_actions.post("/action/shop/buy")
def shop_buy():
    uid, err = _need_auth()
    if err:
        return err
    if not _verify_nonce(uid, request):
        return jsonify(ok=False, error="bad_or_expired_nonce"), 409
    if not check_rate_limit(uid, "shop_buy", max_per_window=8, window_sec=5):
        return jsonify(ok=False, error="rate_limited"), 429

    data = request.get_json(silent=True) or {}
    item_key = data.get("item_key")
    catalog = current_app.config["SHOP_ITEMS"]
    if item_key not in catalog:
        return jsonify(ok=False, error="unknown_item"), 400

    price = int(catalog[item_key]["price"])

    try:
        player = db.session.execute(
            select(Player).where(Player.user_id == uid).with_for_update()
        ).scalar_one_or_none()
        if not player:
            return jsonify(ok=False, error="player_not_found"), 404
        if player.balance < price:
            return jsonify(ok=False, error="not_enough_money"), 400

        player.balance -= price
        add_inventory(uid, item_key, +1)
        db.session.add(ActionLog(user_id=uid, action=f"shop_buy:{item_key}"))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    now_ms = int(_server_now().timestamp() * 1000)
    st = _state_payload(player, now_ms)
    return jsonify(ok=True, state=st, bought={"item_key": item_key, "title": catalog[item_key]["title"], "qty": 1})

@bp_actions.post("/action/plant")
def plant():
    uid, err = _need_auth()
    if err:
        return err
    if not _verify_nonce(uid, request):
        return jsonify(ok=False, error="bad_or_expired_nonce"), 409
    if not check_rate_limit(uid, "plant", max_per_window=8, window_sec=5):
        return jsonify(ok=False, error="rate_limited"), 429

    data = request.get_json(silent=True) or {}
    try:
        idx = int(data.get("idx"))
    except (TypeError, ValueError):
        return jsonify(ok=False, error="bad_index"), 400

    item_key = data.get("item_key")
    # Проверяем, что это семена и они есть в магазине
    if not item_key or not item_key.startswith("seed_"):
        return jsonify(ok=False, error="unknown_seed"), 400
    
    catalog = current_app.config["SHOP_ITEMS"]
    if item_key not in catalog:
        return jsonify(ok=False, error="unknown_seed"), 400
    
    # Определяем тип культуры из названия семян
    crop_type = item_key.replace("seed_", "")

    now = _server_now()

    try:
        player = db.session.execute(
            select(Player).where(Player.user_id == uid).with_for_update()
        ).scalar_one_or_none()
        if not player:
            return jsonify(ok=False, error="player_not_found"), 404

        max_idx = min(player.fields_owned, current_app.config.get("FIELD_MAX", 16))
        if idx < 0 or idx >= max_idx:
            return jsonify(ok=False, error="no_field_access"), 403

        inv_row = db.session.execute(
            select(Inventory).where(Inventory.user_id == uid, Inventory.item_key == item_key).with_for_update()
        ).scalar_one_or_none()
        if not inv_row or inv_row.qty <= 0:
            return jsonify(ok=False, error="no_seeds"), 400

        plot = db.session.execute(
            select(Plot).where(Plot.user_id == uid, Plot.idx == idx).with_for_update()
        ).scalar_one_or_none()
        if plot and plot.crop_key:
            return jsonify(ok=False, error="plot_busy"), 400

        inv_row.qty -= 1
        if plot is None:
            plot = Plot(user_id=uid, idx=idx, crop_key=crop_type, planted_at=now)  # aware UTC
            db.session.add(plot)
        else:
            plot.crop_key = crop_type
            plot.planted_at = now  # aware UTC

        db.session.add(ActionLog(user_id=uid, action=f"plant:{crop_type}"))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    now_ms = int(now.timestamp() * 1000)
    player = db.session.get(Player, uid)
    st = _state_payload(player, now_ms)
    st["plots"] = _plots_payload(uid)

    return jsonify(ok=True, state=st, planted={"idx": idx, "crop_key": crop_type})

@bp_actions.post("/action/harvest")
def harvest():
    uid, err = _need_auth()
    if err:
        return err
    if not _verify_nonce(uid, request):
        return jsonify(ok=False, error="bad_or_expired_nonce"), 409
    if not check_rate_limit(uid, "harvest", max_per_window=10, window_sec=5):
        return jsonify(ok=False, error="rate_limited"), 429

    data = request.get_json(silent=True) or {}
    try:
        idx = int(data.get("idx"))
    except (TypeError, ValueError):
        return jsonify(ok=False, error="bad_index"), 400

    now = _server_now()

    try:
        player = db.session.execute(
            select(Player).where(Player.user_id == uid).with_for_update()
        ).scalar_one_or_none()
        if not player:
            return jsonify(ok=False, error="player_not_found"), 404

        max_idx = min(player.fields_owned, current_app.config.get("FIELD_MAX", 16))
        if idx < 0 or idx >= max_idx:
            return jsonify(ok=False, error="no_field_access"), 403

        plot = db.session.execute(
            select(Plot).where(Plot.user_id == uid, Plot.idx == idx).with_for_update()
        ).scalar_one_or_none()
        if not plot or not plot.crop_key:
            return jsonify(ok=False, error="nothing_to_harvest"), 400

        planted_utc = _as_utc(plot.planted_at)
        if not planted_utc:
            return jsonify(ok=False, error="nothing_to_harvest"), 400

        # Проверяем готовность через crop_stage_info
        crop_info = crop_stage_info(plot.crop_key, planted_utc)
        if crop_info.get("stage") != "ready":
            return jsonify(ok=False, error="not_ready"), 400

        # Добавляем урожай в инвентарь
        crop_item_key = f"crop_{plot.crop_key}"
        add_inventory(uid, crop_item_key, +1)
        
        # Очищаем грядку
        harvested_crop = plot.crop_key
        plot.crop_key = None
        plot.planted_at = None
        db.session.add(ActionLog(user_id=uid, action=f"harvest:{harvested_crop}"))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    now_ms = int(now.timestamp() * 1000)
    player = db.session.get(Player, uid)
    st = _state_payload(player, now_ms)
    st["plots"] = _plots_payload(uid)
    return jsonify(ok=True, state=st, harvested={"idx": idx, "item_key": f"crop_{harvested_crop}", "qty": 1})

@bp_actions.post("/action/sell")
def sell():
    uid, err = _need_auth()
    if err:
        return err
    if not _verify_nonce(uid, request):
        return jsonify(ok=False, error="bad_or_expired_nonce"), 409
    if not check_rate_limit(uid, "sell", max_per_window=8, window_sec=5):
        return jsonify(ok=False, error="rate_limited"), 429

    data = request.get_json(silent=True) or {}
    item_key = data.get("item_key")
    sell_prices = current_app.config["SELL_PRICES"]
    if item_key not in sell_prices:
        return jsonify(ok=False, error="cannot_sell_item"), 400

    price = int(sell_prices[item_key])

    try:
        player = db.session.execute(
            select(Player).where(Player.user_id == uid).with_for_update()
        ).scalar_one_or_none()
        if not player:
            return jsonify(ok=False, error="player_not_found"), 404

        inv_row = db.session.execute(
            select(Inventory).where(Inventory.user_id == uid, Inventory.item_key == item_key).with_for_update()
        ).scalar_one_or_none()
        if not inv_row or inv_row.qty <= 0:
            return jsonify(ok=False, error="no_items"), 400

        inv_row.qty -= 1
        player.balance += price
        db.session.add(ActionLog(user_id=uid, action=f"sell:{item_key}"))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    now_ms = int(_server_now().timestamp() * 1000)
    st = _state_payload(player, now_ms)
    return jsonify(ok=True, state=st, sold={"item_key": item_key, "price": price, "qty": 1})

@bp_actions.post("/action/dev/add_wheat")
def dev_add_wheat():
    """Добавляет пшеницу для тестирования (только для разработки)"""
    data = request.get_json(silent=True) or {}
    quantity = int(data.get("quantity", 100))
    user_id = int(data.get("user_id", 1))  # По умолчанию первый игрок
    
    try:
        player = db.session.get(Player, user_id)
        if not player:
            # Создаем тестового игрока если не существует
            player = Player(
                user_id=user_id,
                username="test_player",
                display_name="Тестовый игрок",
                balance=1000
            )
            db.session.add(player)
            
        add_inventory(user_id, "crop_wheat", quantity)
        db.session.commit()
        
        return jsonify(ok=True, message=f"Добавлено {quantity} пшеницы игроку {player.display_name}")
    except Exception as e:
        db.session.rollback()
        return jsonify(ok=False, error=str(e)), 500

@bp_actions.get("/dev/players")
def dev_get_players():
    """Получает список всех игроков для админ панели"""
    try:
        players = db.session.query(Player).all()
        players_data = []
        
        for player in players:
            # Получаем инвентарь игрока
            inventory = db.session.query(Inventory).filter_by(user_id=player.user_id).all()
            inventory_data = {}
            for item in inventory:
                item_name = {
                    "seed_wheat": "Семена",
                    "crop_wheat": "Пшеница"
                }.get(item.item_key, item.item_key)
                inventory_data[item_name] = item.qty
            
            players_data.append({
                "user_id": player.user_id,
                "display_name": player.display_name,
                "username": player.username,
                "balance": player.balance,
                "fields_owned": player.fields_owned,
                "level": player.level,
                "inventory": inventory_data,
                "is_blocked": bool(player.is_blocked),
                "blocked_reason": player.blocked_reason,
                "created_at": player.created_at.strftime("%d.%m.%Y %H:%M") if player.created_at else "Неизвестно"
            })
        
        return jsonify(ok=True, players=players_data)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500

@bp_actions.post("/dev/block_user")
def dev_block_user():
    """Блокирует пользователя"""
    data = request.get_json(silent=True) or {}
    user_id = int(data.get("user_id"))
    reason = data.get("reason", "Заблокирован администратором")
    
    try:
        player = db.session.get(Player, user_id)
        if not player:
            return jsonify(ok=False, error="Игрок не найден"), 404
            
        player.is_blocked = True
        player.blocked_reason = reason
        player.touch()
        db.session.commit()
        
        return jsonify(ok=True, message=f"Игрок {player.display_name} заблокирован")
    except Exception as e:
        db.session.rollback()
        return jsonify(ok=False, error=str(e)), 500

@bp_actions.post("/dev/unblock_user")
def dev_unblock_user():
    """Разблокирует пользователя"""
    data = request.get_json(silent=True) or {}
    user_id = int(data.get("user_id"))
    
    try:
        player = db.session.get(Player, user_id)
        if not player:
            return jsonify(ok=False, error="Игрок не найден"), 404
            
        player.is_blocked = False
        player.blocked_reason = None
        player.touch()
        db.session.commit()
        
        return jsonify(ok=True, message=f"Игрок {player.display_name} разблокирован")
    except Exception as e:
        db.session.rollback()
        return jsonify(ok=False, error=str(e)), 500
