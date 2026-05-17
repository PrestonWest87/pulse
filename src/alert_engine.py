from datetime import datetime, timedelta
from src.database import SessionLocal, Alert, NotificationChannel, NotificationRule, Source, CollectedItem
from src.outbounds import get_outbound
import logging

logger = logging.getLogger("alert_engine")

SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}


def _keyword_matches(text: str, keywords: list[str]) -> list[str]:
    if not keywords or not text:
        return []
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def evaluate_items(source, items: list):
    keywords = source.alert_on_keywords or []
    if not keywords:
        return

    with SessionLocal() as db:
        for item in items:
            matched = _keyword_matches(item.title + " " + (item.content or ""), keywords)
            if not matched:
                continue

            severity = source.alert_severity or "info"
            title = f"Keyword match: {', '.join(matched[:3])}"
            message = f"Found in '{item.title}' from {source.name}"

            alert = Alert(
                source_id=source.id, source_name=source.name,
                item_id=item.id, item_title=item.title,
                severity=severity, title=title, message=message,
            )
            db.add(alert)
            db.commit()
            db.refresh(alert)

            logger.info(f"Alert #{alert.id}: {title} ({severity})")

            rules = db.query(NotificationRule).filter(
                NotificationRule.enabled == True,
                (NotificationRule.source_id == source.id) | (NotificationRule.source_id.is_(None))
            ).all()

            for rule in rules:
                if SEVERITY_ORDER.get(severity, 0) < SEVERITY_ORDER.get(rule.min_severity or "info", 0):
                    continue

                cutoff = datetime.utcnow() - timedelta(minutes=rule.cooldown_minutes or 5)
                recent = db.query(Alert).filter(
                    Alert.source_id == source.id, Alert.title == title,
                    Alert.created_at >= cutoff
                ).first()
                if recent and recent.id != alert.id:
                    continue

                channel = db.query(NotificationChannel).filter_by(id=rule.channel_id).first()
                if not channel or not channel.enabled:
                    continue

                try:
                    ob_cls = get_outbound(channel.channel_type)
                    ob = ob_cls(channel.config)
                    dr = ob.send(
                        title=title, message=f"{message}\n\n{item.content[:500] if item.content else ''}",
                        severity=severity, source_name=source.name, item_url=item.url or "",
                    )
                    logger.info(f"Sent via '{channel.name}': {dr.message}")
                except Exception as e:
                    logger.error(f"Failed via '{channel.name}': {e}")
