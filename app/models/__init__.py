"""Модели базы данных для фермерской игры.

Содержит модели для игроков, инвентаря, грядок и аутентификации.
"""

from __future__ import annotations
from datetime import datetime, timedelta
import secrets

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Integer, String, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

db = SQLAlchemy()

class Player(db.Model):
    """
    Модель игрока.
    
    Хранит данные об игроке: профиль Telegram,
    баланс, уровень, опыт и ресурсы.
    """
    __tablename__ = "players"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    display_name: Mapped[str] = mapped_column(String(64), default="Игрок")

    balance: Mapped[int] = mapped_column(Integer, default=100)
    fields_owned: Mapped[int] = mapped_column(Integer, default=2)

    level: Mapped[int] = mapped_column(Integer, default=1)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    gold: Mapped[int] = mapped_column(Integer, default=0)
    wood: Mapped[int] = mapped_column(Integer, default=0)
    stone: Mapped[int] = mapped_column(Integer, default=0)
    
    is_blocked: Mapped[bool] = mapped_column(Integer, default=False)
    blocked_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def touch(self) -> None:
        """Обновляет время последнего обновления."""
        self.updated_at = datetime.utcnow()

    def to_public_dict(self) -> dict:
        """Преобразует модель в словарь для API."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "display_name": self.display_name,
            "balance": self.balance,
            "fields_owned": self.fields_owned,
            "level": self.level,
            "xp": self.xp,
            "gold": self.gold,
            "wood": self.wood,
            "stone": self.stone,
            "is_blocked": bool(self.is_blocked),
            "blocked_reason": self.blocked_reason,
            "updated_at": self.updated_at.isoformat(),
        }

class ActionNonce(db.Model):
    """
    Модель для защиты от CSRF-атак.
    
    Сохраняет уникальные одноразовые токены для каждого игрока.
    """
    __tablename__ = "action_nonces"
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    @staticmethod
    def issue_for(user_id: int, ttl_sec: int = 60) -> "ActionNonce":
        now = datetime.utcnow()
        nonce = secrets.token_hex(16)
        obj: ActionNonce | None = db.session.get(ActionNonce, user_id)
        if obj is None:
            obj = ActionNonce(user_id=user_id, value=nonce, expires_at=now + timedelta(seconds=ttl_sec))
            db.session.add(obj)
        else:
            obj.value = nonce
            obj.expires_at = now + timedelta(seconds=ttl_sec)
        return obj

    def verify_and_rotate(self, ttl_sec: int = 60, presented: str | None = None) -> bool:
        if not presented or presented != self.value:
            return False
        if datetime.utcnow() > self.expires_at:
            return False
        self.value = secrets.token_hex(16)
        self.expires_at = datetime.utcnow() + timedelta(seconds=ttl_sec)
        return True

class ActionLog(db.Model):
    """
    Модель для логирования действий игроков.
    
    Используется для rate limiting и анти-чит защиты.
    """
    __tablename__ = "action_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (UniqueConstraint("id", name="uq_action_logs_id"),)

def check_rate_limit(user_id: int, action: str, max_per_window: int = 10, window_sec: int = 5) -> bool:
    cutoff = datetime.utcnow() - timedelta(seconds=window_sec)
    cnt = db.session.query(ActionLog).filter(
        ActionLog.user_id == user_id,
        ActionLog.created_at >= cutoff,
    ).count()
    return cnt < max_per_window

class Inventory(db.Model):
    """
    Модель инвентаря игрока.
    
    Хранит количество предметов (семена, урожай) у игрока.
    """
    __tablename__ = "inventories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    item_key: Mapped[str] = mapped_column(String(64), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint("user_id", "item_key", name="uq_inventory_user_item"),)

def add_inventory(user_id: int, item_key: str, delta: int):
    row: Inventory | None = db.session.query(Inventory).filter_by(user_id=user_id, item_key=item_key).one_or_none()
    if row is None:
        row = Inventory(user_id=user_id, item_key=item_key, qty=max(0, delta))
        db.session.add(row)
    else:
        row.qty = max(0, row.qty + delta)
    return row

class Plot(db.Model):
    """
    Модель грядки на ферме.
    
    Хранит состояние каждой грядки: что посажено и когда.
    """
    __tablename__ = "plots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    idx: Mapped[int] = mapped_column(Integer, nullable=False)  # 0..15
    crop_key: Mapped[str | None] = mapped_column(String(64), nullable=True)  # "wheat"
    planted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (UniqueConstraint("user_id", "idx", name="uq_plot_user_idx"),)
