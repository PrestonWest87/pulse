import requests
import json
from src.notifiers import BaseNotifier, NotificationResult, register_notifier


COLORS = {
    "info": "#3498db", "warning": "#f39c12", "critical": "#e74c3c",
    "up": "#2ecc71", "down": "#e74c3c", "degraded": "#f39c12"
}


@register_notifier
class SlackNotifier(BaseNotifier):
    channel_type = "slack"
    name = "Slack"
    config_schema = {
        "webhook_url": {"type": "string", "label": "Slack Incoming Webhook URL", "required": True},
        "channel": {"type": "string", "label": "Channel override (optional, e.g. #alerts)", "required": False},
    }

    def send(self, title: str, message: str, severity: str, monitor_name: str = "",
             check_details: dict = None) -> NotificationResult:
        url = self.config.get("webhook_url", "")
        if not url:
            return NotificationResult(success=False, message="No webhook URL configured")

        color = COLORS.get(severity, "#95a5a6")

        fields = []
        if monitor_name:
            fields.append({"title": "Monitor", "value": monitor_name, "short": True})
        fields.append({"title": "Severity", "value": severity.upper(), "short": True})
        if check_details:
            for k, v in check_details.items():
                if v and k not in ("monitor_name",):
                    fields.append({"title": k.replace("_", " ").title(), "value": str(v)[:200], "short": True})

        payload = {
            "attachments": [{
                "color": color,
                "title": title,
                "text": message[:3000],
                "fields": fields,
                "ts": __import__("datetime").datetime.utcnow().timestamp(),
            }]
        }

        channel = self.config.get("channel", "")
        if channel:
            payload["channel"] = channel

        try:
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code == 200:
                return NotificationResult(success=True, message="Slack notification sent")
            return NotificationResult(success=False, message=f"Slack error: HTTP {resp.status_code}")
        except Exception as e:
            return NotificationResult(success=False, message=f"Slack error: {e}")
