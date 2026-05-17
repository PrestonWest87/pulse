import requests
from src.notifiers import BaseNotifier, NotificationResult, register_notifier


COLORS = {
    "info": 3447003, "warning": 15105570, "critical": 15548997,
    "up": 3066993, "down": 15548997, "degraded": 15105570
}


@register_notifier
class DiscordNotifier(BaseNotifier):
    channel_type = "discord"
    name = "Discord"
    config_schema = {
        "webhook_url": {"type": "string", "label": "Discord Webhook URL", "required": True},
        "username": {"type": "string", "label": "Bot username override (optional)", "required": False},
    }

    def send(self, title: str, message: str, severity: str, monitor_name: str = "",
             check_details: dict = None) -> NotificationResult:
        url = self.config.get("webhook_url", "")
        if not url:
            return NotificationResult(success=False, message="No webhook URL configured")

        color = COLORS.get(severity, 7506394)

        fields = []
        if monitor_name:
            fields.append({"name": "Monitor", "value": monitor_name, "inline": True})
        fields.append({"name": "Severity", "value": severity.upper(), "inline": True})
        if check_details:
            for k, v in check_details.items():
                if v and k not in ("monitor_name",):
                    fields.append({"name": k.replace("_", " ").title(), "value": str(v)[:200], "inline": True})

        embed = {
            "title": title[:256],
            "description": message[:2048],
            "color": color,
            "fields": fields[:25],
            "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        }

        payload = {"embeds": [embed]}
        username = self.config.get("username", "")
        if username:
            payload["username"] = username

        try:
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code in (200, 204):
                return NotificationResult(success=True, message="Discord notification sent")
            return NotificationResult(success=False, message=f"Discord error: HTTP {resp.status_code}")
        except Exception as e:
            return NotificationResult(success=False, message=f"Discord error: {e}")
