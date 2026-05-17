import requests
import json
from src.outbounds import BaseOutbound, DispatchResult, register_outbound


@register_outbound
class WebhookOutbound(BaseOutbound):
    channel_type = "webhook"
    name = "Outbound Webhook"
    config_schema = {
        "url": {"type": "string", "label": "Webhook URL", "required": True},
        "method": {"type": "string", "label": "HTTP Method", "default": "POST"},
        "headers": {"type": "string", "label": "Custom headers (JSON)", "required": False},
    }

    def send(self, title: str, message: str, severity: str, source_name: str = "",
             item_url: str = "") -> DispatchResult:
        url = self.config.get("url", "")
        method = self.config.get("method", "POST").upper()
        headers = {"Content-Type": "application/json"}
        hdr_raw = self.config.get("headers", "")
        if hdr_raw:
            try:
                headers.update(json.loads(hdr_raw))
            except json.JSONDecodeError:
                pass

        payload = {
            "event": "pulse_collected",
            "title": title,
            "message": message[:2000],
            "severity": severity,
            "source": source_name,
            "url": item_url,
            "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
        }

        try:
            resp = requests.request(method, url, json=payload, headers=headers, timeout=15)
            if resp.status_code < 400:
                return DispatchResult(success=True, message=f"Sent (HTTP {resp.status_code})")
            return DispatchResult(success=False, message=f"HTTP {resp.status_code}")
        except Exception as e:
            return DispatchResult(success=False, message=str(e))
