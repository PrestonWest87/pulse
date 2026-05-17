import requests
from src.outbounds import BaseOutbound, DispatchResult, register_outbound

COLORS = {"info": 3447003, "warning": 15105570, "critical": 15548997}

@register_outbound
class DiscordOutbound(BaseOutbound):
    channel_type = "discord"
    name = "Discord"
    config_schema = {
        "webhook_url": {"type": "string", "label": "Discord Webhook URL", "required": True},
    }

    def send(self, title: str, message: str, severity: str, source_name: str = "",
             item_url: str = "") -> DispatchResult:
        url = self.config.get("webhook_url", "")
        if not url:
            return DispatchResult(success=False, message="No webhook URL")

        embed = {
            "title": title[:256],
            "url": item_url or "",
            "description": message[:2048],
            "color": COLORS.get(severity, 7506394),
            "fields": [
                {"name": "Source", "value": source_name or "Unknown", "inline": True},
                {"name": "Severity", "value": severity.upper(), "inline": True},
            ],
            "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        }
        payload = {"embeds": [embed]}

        try:
            resp = requests.post(url, json=payload, timeout=15)
            return DispatchResult(success=resp.status_code in (200, 204), message=f"HTTP {resp.status_code}")
        except Exception as e:
            return DispatchResult(success=False, message=str(e))
