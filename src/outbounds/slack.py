import requests
from src.outbounds import BaseOutbound, DispatchResult, register_outbound

COLORS = {"info": "#3498db", "warning": "#f39c12", "critical": "#e74c3c"}

@register_outbound
class SlackOutbound(BaseOutbound):
    channel_type = "slack"
    name = "Slack"
    config_schema = {
        "webhook_url": {"type": "string", "label": "Slack Incoming Webhook URL", "required": True},
        "channel": {"type": "string", "label": "Channel override (optional)", "required": False},
    }

    def send(self, title: str, message: str, severity: str, source_name: str = "",
             item_url: str = "") -> DispatchResult:
        url = self.config.get("webhook_url", "")
        if not url:
            return DispatchResult(success=False, message="No webhook URL")

        color = COLORS.get(severity, "#95a5a6")
        payload = {
            "attachments": [{
                "color": color,
                "title": title,
                "title_link": item_url or "",
                "text": message[:3000],
                "fields": [
                    {"title": "Source", "value": source_name, "short": True},
                    {"title": "Severity", "value": severity.upper(), "short": True},
                ],
                "ts": __import__("datetime").datetime.utcnow().timestamp(),
            }]
        }
        channel = self.config.get("channel", "")
        if channel:
            payload["channel"] = channel

        try:
            resp = requests.post(url, json=payload, timeout=15)
            return DispatchResult(success=resp.status_code == 200, message=f"HTTP {resp.status_code}")
        except Exception as e:
            return DispatchResult(success=False, message=str(e))
