import os
import bcrypt
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, Boolean, JSON, event, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
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
# AUTH
# ==========================================

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String, default="admin", index=True)
    session_token = Column(String, nullable=True, index=True)
    full_name = Column(String, nullable=True)


# ==========================================
# DATA SOURCES (what we collect from)
# ==========================================

COLLECTOR_TYPES = ["rss", "web_page", "release_tracker", "http_endpoint", "steam", "reddit", "price_tracker", "git_commits"]

class Source(Base):
    __tablename__ = "sources"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text, default="")
    collector_type = Column(String, index=True)
    config = Column(JSON, default=dict)
    interval_seconds = Column(Integer, default=900)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_run_at = Column(DateTime, nullable=True)
    last_status = Column(String, default="never")
    last_error = Column(Text, nullable=True)
    alert_on_keywords = Column(JSON, default=list)
    alert_severity = Column(String, default="info")

    runs = relationship("CollectionRun", back_populates="source", cascade="all, delete-orphan",
                        order_by="CollectionRun.run_at.desc()")
    items = relationship("CollectedItem", back_populates="source", cascade="all, delete-orphan",
                         order_by="CollectedItem.published_at.desc()")


class CollectionRun(Base):
    __tablename__ = "collection_runs"
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), index=True)
    status = Column(String)
    items_found = Column(Integer, default=0)
    items_new = Column(Integer, default=0)
    response_summary = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    duration_ms = Column(Float, nullable=True)
    run_at = Column(DateTime, default=datetime.utcnow)

    source = relationship("Source", back_populates="runs")


class CollectedItem(Base):
    __tablename__ = "collected_items"
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), index=True)
    source_name = Column(String, index=True)
    source_type = Column(String, index=True)

    title = Column(String, index=True)
    content = Column(Text, nullable=True)
    url = Column(String, nullable=True)
    author = Column(String, nullable=True)

    published_at = Column(DateTime, nullable=True, index=True)
    collected_at = Column(DateTime, default=datetime.utcnow, index=True)

    content_hash = Column(String, nullable=True, index=True)
    raw_data = Column(JSON, nullable=True)

    is_read = Column(Boolean, default=False)
    is_flagged = Column(Boolean, default=False)

    source = relationship("Source", back_populates="items")


# ==========================================
# ALERTS & NOTIFICATIONS
# ==========================================

ALERT_STATUSES = ["triggered", "acknowledged", "resolved"]

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("sources.id"), index=True, nullable=True)
    source_name = Column(String, nullable=True)
    item_id = Column(Integer, nullable=True)
    item_title = Column(String, nullable=True)
    severity = Column(String, default="info")
    status = Column(String, default="triggered")
    title = Column(String)
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)


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
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=True)
    channel_id = Column(Integer, ForeignKey("notification_channels.id"))
    min_severity = Column(String, default="info")
    cooldown_minutes = Column(Integer, default=5)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ==========================================
# MAINTENANCE WINDOWS (silence rules)
# ==========================================

class MaintenanceWindow(Base):
    __tablename__ = "maintenance_windows"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    source_id = Column(Integer, ForeignKey("sources.id"), nullable=True, index=True)
    start_time = Column(String)  # "HH:MM"
    end_time = Column(String)    # "HH:MM"
    days_of_week = Column(JSON, default=list)  # 0=Mon..6=Sun
    timezone = Column(String, default="UTC")
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ==========================================
# ESCALATION POLICIES
# ==========================================

class EscalationPolicy(Base):
    __tablename__ = "escalation_policies"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    rule_id = Column(Integer, ForeignKey("notification_rules.id"), nullable=True, index=True)
    delay_minutes = Column(Integer, default=15)
    target_channel_id = Column(Integer, ForeignKey("notification_channels.id"))
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ==========================================
# DIGEST CONFIG (LLM summaries)
# ==========================================

class DigestConfig(Base):
    __tablename__ = "digest_configs"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, default="Daily Digest")
    enabled = Column(Boolean, default=False)
    interval_minutes = Column(Integer, default=1440)
    max_items = Column(Integer, default=50)
    source_ids = Column(JSON, default=list)
    last_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ==========================================
# SYSTEM CONFIG
# ==========================================

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


# ==========================================
# LEGACY (kept for backward compat)
# ==========================================

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

    # Migrate old NOC-era schema if detected
    from sqlalchemy import text
    with engine.connect() as conn:
        # Rename/migrate notification_rules columns
        try:
            pragma = conn.execute(text("PRAGMA table_info(notification_rules)")).fetchall()
            old_cols = {r[1] for r in pragma}
            if "monitor_id" in old_cols and "source_id" not in old_cols:
                conn.execute(text("ALTER TABLE notification_rules RENAME COLUMN monitor_id TO source_id"))
                conn.commit()
        except Exception:
            pass

        # Migrate alerts table (old NOC schema had monitor_name, check_id, etc.)
        try:
            pragma = conn.execute(text("PRAGMA table_info(alerts)")).fetchall()
            old_cols = {r[1]: r[2] for r in pragma}
            migrations_alerts = [
                ("monitor_name", "source_name", "VARCHAR"),
                ("monitor_id", "source_id", "INTEGER"),
            ]
            for old_c, new_c, ctype in migrations_alerts:
                if old_c in old_cols and new_c not in old_cols:
                    conn.execute(text(f"ALTER TABLE alerts RENAME COLUMN {old_c} TO {new_c}"))
                    conn.commit()
            # Add columns that never existed in old schema
            for col_name, ctype in [("item_id", "INTEGER"), ("item_title", "VARCHAR")]:
                if col_name not in old_cols:
                    conn.execute(text(f"ALTER TABLE alerts ADD COLUMN {col_name} {ctype}"))
                    conn.commit()
        except Exception:
            pass

    with SessionLocal() as session:
        existing = session.query(User).filter_by(username="admin").first()
        if not existing:
            hashed = bcrypt.hashpw("admin123".encode(), bcrypt.gensalt()).decode()
            session.add(User(username="admin", password_hash=hashed, role="admin", full_name="Administrator"))
            session.commit()
