from datetime import datetime, timedelta
from src.database import SessionLocal, Alert, NotificationChannel, NotificationRule, Monitor
from src.notifiers import get_notifier
import logging

logger = logging.getLogger("alert_engine")

ALERT_STATUS_TRIGGERED = "triggered"
ALERT_STATUS_ACKNOWLEDGED = "acknowledged"
ALERT_STATUS_RESOLVED = "resolved"
ALERT_STATUS_SUPPRESSED = "suppressed"

SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}


def meets_min_severity(alert_sev: str, rule_sev: str) -> bool:
    return SEVERITY_ORDER.get(alert_sev, 0) >= SEVERITY_ORDER.get(rule_sev, 0)


def check_dedup(monitor_id: int, title: str, cooldown_minutes: int, exclude_alert_id: int = None) -> bool:
    with SessionLocal() as db:
        cutoff = datetime.utcnow() - timedelta(minutes=cooldown_minutes)
        q = db.query(Alert).filter(
            Alert.monitor_id == monitor_id,
            Alert.title == title,
            Alert.created_at >= cutoff,
            Alert.status == ALERT_STATUS_TRIGGERED
        )
        if exclude_alert_id:
            q = q.filter(Alert.id != exclude_alert_id)
        return q.first() is not None


def evaluate_and_alert(monitor, check, result):
    if not monitor.enabled:
        return

    alert_on = monitor.alert_on or ["down", "error"]
    if check.status not in alert_on:
        return

    severity = monitor.severity or "warning"
    title = f"{monitor.name} is {check.status}"
    message = check.error or check.response_summary or f"Status: {check.status}"

    with SessionLocal() as db:
        # Find matching rules
        rules = db.query(NotificationRule).filter(
            NotificationRule.enabled == True,
            NotificationRule.monitor_id == monitor.id,
        ).all()
        global_rules = db.query(NotificationRule).filter(
            NotificationRule.enabled == True,
            NotificationRule.monitor_id.is_(None),
        ).all()
        rules = rules + global_rules

        # Collect channels that need to be notified
        channels_to_notify = []
        for rule in rules:
            if not meets_min_severity(severity, rule.min_severity or "warning"):
                continue
            channel = db.query(NotificationChannel).filter_by(id=rule.channel_id).first()
            if channel and channel.enabled:
                channels_to_notify.append((rule, channel))

        # Save alert regardless (for history)
        alert = Alert(
            monitor_id=monitor.id, monitor_name=monitor.name,
            severity=severity, status=ALERT_STATUS_TRIGGERED,
            title=title, message=message, check_id=check.id,
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        alert_id = alert.id

        logger.info(f"Alert #{alert_id} created: {title} [{severity}]")

        # Dispatch to channels with dedup check
        for rule, channel in channels_to_notify:
            if check_dedup(monitor.id, title, rule.cooldown_minutes or 5, exclude_alert_id=alert_id):
                logger.info(f"Dedup: skipping {title} for rule '{rule.name}' (cooldown {rule.cooldown_minutes}m)")
                continue

            try:
                notifier_cls = get_notifier(channel.channel_type)
                notifier = notifier_cls(channel.config)
                check_details = {
                    "status": check.status,
                    "response_time_ms": check.response_time_ms,
                    "status_code": check.status_code,
                    "error": check.error,
                }
                nr = notifier.send(
                    title=title, message=message, severity=severity,
                    monitor_name=monitor.name, check_details=check_details,
                )
                logger.info(f"Sent via '{channel.name}': {nr.message}")
            except Exception as e:
                logger.error(f"Failed to send via '{channel.name}': {e}")

    return alert_id
