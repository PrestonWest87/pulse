import os
import bcrypt
import time
import random
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, Boolean, JSON, event, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy import text
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////app/data/pulse.db").strip().strip('"').strip("'")
if not DATABASE_URL.startswith("sqlite"):
    DATABASE_URL = "sqlite:////app/data/pulse.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30}
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-16000")
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.execute("PRAGMA mmap_size=268435456")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ==========================================
# AUTH & SYSTEM
# ==========================================

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String, default="admin", index=True)
    session_token = Column(String, nullable=True, index=True)
    full_name = Column(String, nullable=True)

class SystemConfig(Base):
    __tablename__ = "system_config"
    id = Column(Integer, primary_key=True, index=True)
    smtp_enabled = Column(Boolean, default=False)
    smtp_server = Column(String, nullable=True)
    smtp_port = Column(Integer, default=587)
    smtp_sender = Column(String, nullable=True)
    smtp_username = Column(String, nullable=True)
    smtp_password = Column(String, nullable=True)
    smtp_recipient = Column(String, nullable=True)
    llm_endpoint = Column(String, nullable=True)
    llm_api_key = Column(String, nullable=True)
    llm_model_name = Column(String, default="gpt-3.5-turbo")
    last_risk_alert_time = Column(DateTime, nullable=True)
    last_risk_level = Column(String, default="GREEN")


# ==========================================
# MONITOR SYSTEM
# ==========================================

MONITOR_TYPES = [
    "rss", "http_status", "http_json", "web_scrape",
    "tcp_ping", "script", "webhook_in"
]

ALERT_SEVERITIES = ["info", "warning", "critical"]
ALERT_STATUSES = ["triggered", "acknowledged", "resolved", "suppressed"]

class Monitor(Base):
    __tablename__ = "monitors"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text, default="")
    monitor_type = Column(String, index=True)
    config = Column(JSON, default=dict)
    interval_seconds = Column(Integer, default=300)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_check_at = Column(DateTime, nullable=True)
    last_status = Column(String, default="never")
    last_response_time_ms = Column(Float, nullable=True)
    last_error = Column(Text, nullable=True)
    last_response_summary = Column(Text, nullable=True)
    alert_on = Column(JSON, default=lambda: ["down", "error"])
    severity = Column(String, default="warning")

    checks = relationship("MonitorCheck", back_populates="monitor", cascade="all, delete-orphan",
                          order_by="MonitorCheck.checked_at.desc()")

class MonitorCheck(Base):
    __tablename__ = "monitor_checks"
    id = Column(Integer, primary_key=True, index=True)
    monitor_id = Column(Integer, ForeignKey("monitors.id"), index=True)
    status = Column(String)
    status_code = Column(Integer, nullable=True)
    response_time_ms = Column(Float, nullable=True)
    response_summary = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    raw_data = Column(JSON, nullable=True)
    checked_at = Column(DateTime, default=datetime.utcnow, index=True)

    monitor = relationship("Monitor", back_populates="checks")


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, index=True)
    monitor_id = Column(Integer, ForeignKey("monitors.id"), index=True, nullable=True)
    monitor_name = Column(String, nullable=True)
    severity = Column(String, default="warning")
    status = Column(String, default="triggered")
    title = Column(String)
    message = Column(Text)
    check_id = Column(Integer, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class NotificationChannel(Base):
    __tablename__ = "notification_channels"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    channel_type = Column(String)
    config = Column(JSON, default=dict)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class NotificationRule(Base):
    __tablename__ = "notification_rules"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    monitor_id = Column(Integer, ForeignKey("monitors.id"), nullable=True)
    channel_id = Column(Integer, ForeignKey("notification_channels.id"))
    min_severity = Column(String, default="warning")
    cooldown_minutes = Column(Integer, default=5)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ==========================================
# LEGACY (adapted from NOC)
# ==========================================

class FeedSource(Base):
    __tablename__ = "feed_sources"
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, index=True)
    name = Column(String)
    is_active = Column(Boolean, default=True)

class Keyword(Base):
    __tablename__ = "keywords"
    id = Column(Integer, primary_key=True, index=True)
    word = Column(String, unique=True, index=True)
    weight = Column(Integer, default=10)


# ==========================================
# INIT
# ==========================================

def init_db():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        existing = session.query(User).filter_by(username="admin").first()
        if not existing:
            hashed = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
            session.add(User(username="admin", password_hash=hashed, role="admin", full_name="Administrator"))
            session.commit()
