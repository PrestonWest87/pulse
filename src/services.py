import bcrypt
import uuid
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import streamlit as st

from src.database import (
    SessionLocal, User, SystemConfig, Source, CollectionRun,
    CollectedItem, Alert, NotificationChannel, NotificationRule
)

LOCAL_TZ = ZoneInfo("America/Chicago")


class DotDict(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


def to_dotdict(obj):
    if not obj: return None
    return DotDict({c.name: getattr(obj, c.name) for c in obj.__table__.columns})


def to_dotdict_list(objs):
    return [to_dotdict(obj) for obj in objs]


def format_central(dt):
    if dt is None:
        return "Unknown"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(LOCAL_TZ).strftime('%Y-%m-%d %H:%M:%S')


# ==========================================
# AUTH
# ==========================================

def authenticate(username, password):
    with SessionLocal() as db:
        user = db.query(User).filter_by(username=username).first()
        if user and bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            token = str(uuid.uuid4())
            user.session_token = token
            db.commit()
            return to_dotdict(user)
    return None


def get_user_by_token(token):
    with SessionLocal() as db:
        user = db.query(User).filter_by(session_token=token).first()
        return to_dotdict(user) if user else None


def update_user_password(user_id, new_password):
    with SessionLocal() as db:
        user = db.query(User).filter_by(id=user_id).first()
        if user:
            hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
            user.password_hash = hashed
            db.commit()
            return True
    return False


# ==========================================
# SOURCES (data sources to collect from)
# ==========================================

def get_sources():
    with SessionLocal() as db:
        return to_dotdict_list(db.query(Source).order_by(Source.name).all())


def get_source_by_id(source_id):
    with SessionLocal() as db:
        return to_dotdict(db.query(Source).filter_by(id=source_id).first())


def create_source(name, collector_type, config, interval_seconds, alert_severity="info", alert_on_keywords=None, description=""):
    with SessionLocal() as db:
        src = Source(
            name=name, collector_type=collector_type, config=config,
            interval_seconds=interval_seconds, alert_severity=alert_severity or "info",
            alert_on_keywords=alert_on_keywords or [], description=description,
        )
        db.add(src)
        db.commit()
        db.refresh(src)
        return src.id


def delete_source(source_id):
    with SessionLocal() as db:
        src = db.query(Source).filter_by(id=source_id).first()
        if src:
            db.delete(src)
            db.commit()
            return True
    return False


def toggle_source(source_id):
    with SessionLocal() as db:
        src = db.query(Source).filter_by(id=source_id).first()
        if src:
            src.enabled = not src.enabled
            db.commit()
            return src.enabled
    return False


# ==========================================
# COLLECTED ITEMS (search, browse)
# ==========================================

def get_recent_items(limit=100, source_id=None, search=None):
    with SessionLocal() as db:
        q = db.query(CollectedItem)
        if source_id:
            q = q.filter(CollectedItem.source_id == source_id)
        if search:
            like = f"%{search}%"
            q = q.filter(
                CollectedItem.title.ilike(like) |
                CollectedItem.content.ilike(like) |
                CollectedItem.url.ilike(like)
            )
        return to_dotdict_list(q.order_by(CollectedItem.published_at.desc()).limit(limit).all())


def get_item_by_id(item_id):
    with SessionLocal() as db:
        return to_dotdict(db.query(CollectedItem).filter_by(id=item_id).first())


def get_item_count():
    with SessionLocal() as db:
        return db.query(CollectedItem).count()


def get_source_item_counts():
    with SessionLocal() as db:
        from sqlalchemy import func
        results = db.query(CollectedItem.source_id, CollectedItem.source_name, func.count(CollectedItem.id)).group_by(CollectedItem.source_id).all()
        return [(r[0], r[1], r[2]) for r in results]


# ==========================================
# ALERTS
# ==========================================

def get_alerts(limit=100, status=None, severity=None, source_id=None):
    with SessionLocal() as db:
        q = db.query(Alert)
        if status:
            q = q.filter(Alert.status == status)
        if severity:
            q = q.filter(Alert.severity == severity)
        if source_id:
            q = q.filter(Alert.source_id == source_id)
        return to_dotdict_list(q.order_by(Alert.created_at.desc()).limit(limit).all())


def acknowledge_alert(alert_id):
    with SessionLocal() as db:
        alert = db.query(Alert).filter_by(id=alert_id).first()
        if alert and alert.status == "triggered":
            alert.status = "acknowledged"
            alert.acknowledged_at = datetime.utcnow()
            db.commit()
            return True
    return False


def resolve_alert(alert_id):
    with SessionLocal() as db:
        alert = db.query(Alert).filter_by(id=alert_id).first()
        if alert and alert.status in ("triggered", "acknowledged"):
            alert.status = "resolved"
            alert.resolved_at = datetime.utcnow()
            db.commit()
            return True
    return False


# ==========================================
# NOTIFICATION CHANNELS
# ==========================================

def get_channels():
    with SessionLocal() as db:
        return to_dotdict_list(db.query(NotificationChannel).order_by(NotificationChannel.name).all())


def create_channel(name, channel_type, config):
    with SessionLocal() as db:
        ch = NotificationChannel(name=name, channel_type=channel_type, config=config)
        db.add(ch)
        db.commit()
        return ch.id


def update_channel(channel_id, **kwargs):
    with SessionLocal() as db:
        ch = db.query(NotificationChannel).filter_by(id=channel_id).first()
        if not ch:
            return False
        for k, v in kwargs.items():
            if hasattr(ch, k) and v is not None:
                setattr(ch, k, v)
        db.commit()
        return True


def delete_channel(channel_id):
    with SessionLocal() as db:
        ch = db.query(NotificationChannel).filter_by(id=channel_id).first()
        if ch:
            db.delete(ch)
            db.commit()
            return True
    return False


# ==========================================
# NOTIFICATION RULES
# ==========================================

def get_rules():
    with SessionLocal() as db:
        return to_dotdict_list(db.query(NotificationRule).order_by(NotificationRule.name).all())


def create_rule(name, source_id, channel_id, min_severity="info", cooldown_minutes=5):
    with SessionLocal() as db:
        rule = NotificationRule(
            name=name, source_id=source_id, channel_id=channel_id,
            min_severity=min_severity, cooldown_minutes=cooldown_minutes,
        )
        db.add(rule)
        db.commit()
        return rule.id


def delete_rule(rule_id):
    with SessionLocal() as db:
        rule = db.query(NotificationRule).filter_by(id=rule_id).first()
        if rule:
            db.delete(rule)
            db.commit()
            return True
    return False


# ==========================================
# SYSTEM CONFIG
# ==========================================

@st.cache_data(ttl=300)
def get_cached_config():
    with SessionLocal() as db:
        config = db.query(SystemConfig).first()
        if not config:
            config = SystemConfig()
            db.add(config)
            db.commit()
            db.refresh(config)
        return to_dotdict(config)


def update_config(**kwargs):
    with SessionLocal() as db:
        config = db.query(SystemConfig).first()
        if not config:
            config = SystemConfig()
            db.add(config)
        for k, v in kwargs.items():
            if hasattr(config, k):
                setattr(config, k, v)
        db.commit()
    st.cache_data.clear()
