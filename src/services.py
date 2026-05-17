import bcrypt
import uuid
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import streamlit as st

from src.database import (
    SessionLocal, User, SystemConfig, Monitor, MonitorCheck,
    Alert, NotificationChannel, NotificationRule, Keyword
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


def central_now():
    return datetime.now(LOCAL_TZ)


def utc_now():
    return datetime.utcnow()


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
# MONITORS
# ==========================================

def get_monitors():
    with SessionLocal() as db:
        return to_dotdict_list(db.query(Monitor).order_by(Monitor.name).all())


def get_monitor_by_id(monitor_id):
    with SessionLocal() as db:
        return to_dotdict(db.query(Monitor).filter_by(id=monitor_id).first())


def create_monitor(name, monitor_type, config, interval_seconds, severity, alert_on, description=""):
    with SessionLocal() as db:
        mon = Monitor(
            name=name, monitor_type=monitor_type, config=config,
            interval_seconds=interval_seconds, severity=severity or "warning",
            alert_on=alert_on or ["down", "error"], description=description,
        )
        db.add(mon)
        db.commit()
        return mon.id


def update_monitor(monitor_id, **kwargs):
    with SessionLocal() as db:
        mon = db.query(Monitor).filter_by(id=monitor_id).first()
        if not mon:
            return False
        for k, v in kwargs.items():
            if hasattr(mon, k) and v is not None:
                setattr(mon, k, v)
        db.commit()
        return True


def delete_monitor(monitor_id):
    with SessionLocal() as db:
        mon = db.query(Monitor).filter_by(id=monitor_id).first()
        if mon:
            db.delete(mon)
            db.commit()
            return True
    return False


def toggle_monitor(monitor_id):
    with SessionLocal() as db:
        mon = db.query(Monitor).filter_by(id=monitor_id).first()
        if mon:
            mon.enabled = not mon.enabled
            db.commit()
            return mon.enabled
    return False


def get_monitor_checks(monitor_id, limit=50):
    with SessionLocal() as db:
        return to_dotdict_list(
            db.query(MonitorCheck)
            .filter_by(monitor_id=monitor_id)
            .order_by(MonitorCheck.checked_at.desc())
            .limit(limit)
            .all()
        )


# ==========================================
# ALERTS
# ==========================================

def get_alerts(limit=100, status=None, severity=None, monitor_id=None):
    with SessionLocal() as db:
        q = db.query(Alert)
        if status:
            q = q.filter(Alert.status == status)
        if severity:
            q = q.filter(Alert.severity == severity)
        if monitor_id:
            q = q.filter(Alert.monitor_id == monitor_id)
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


def create_rule(name, monitor_id, channel_id, min_severity="warning", cooldown_minutes=5):
    with SessionLocal() as db:
        rule = NotificationRule(
            name=name, monitor_id=monitor_id, channel_id=channel_id,
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


# ==========================================
# KEYWORDS (for content filtering legacy)
# ==========================================

def get_keywords():
    with SessionLocal() as db:
        return to_dotdict_list(db.query(Keyword).order_by(Keyword.word).all())
