from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Player(db.Model):
    __tablename__ = "players"
    user_id     = db.Column(db.BigInteger, primary_key=True)
    name        = db.Column(db.String(100))
    soils_count = db.Column(db.Integer, default=2, nullable=False)
    balance     = db.Column(db.Integer, default=100, nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class ReplayStamp(db.Model):
    __tablename__ = "replay_stamps"
    id         = db.Column(db.Integer, primary_key=True)
    stamp_hash = db.Column(db.String(64), nullable=False, unique=True)
    auth_date  = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint("stamp_hash", name="uq_stamp_hash"),)

class ActionLog(db.Model):
    __tablename__ = "action_logs"
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.BigInteger, index=True, nullable=False)
    action       = db.Column(db.String(64), nullable=False)
    amount       = db.Column(db.Integer, default=0, nullable=False)
    old_balance  = db.Column(db.Integer)
    new_balance  = db.Column(db.Integer)
    soils_before = db.Column(db.Integer)
    soils_after  = db.Column(db.Integer)
    ip           = db.Column(db.String(64))
    ua           = db.Column(db.Text)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
