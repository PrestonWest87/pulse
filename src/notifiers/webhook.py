import requests
import json
from src.notifiers import BaseNotifier, NotificationResult, register_notifier


@register_notifier
class WebhookNotifier(BaseNotifier):
    channel_type = "webhook"
    name = "Outbound Webhook"
    config_schema = {
        "url": {"type": "string", "label": "Webhook URL", "required": True},
        "method": {"type": "string", "label": "HTTP Method", "default": "POST", "required": False},
        "headers": {"type": "string", "label": "Custom headers (JSON)", "required": False},
        "payload_template": {"type": "string", "label": "JSON payload template (leave blank for auto)", "required": False},
    }

    def send(self, title: str, message: str, severity: str, monitor_name: str = "",
             check_details: dict = None) -> NotificationResult:
        url = self.config.get("url", "")
        method = self.config.get("method", "POST").upper()
        headers = {"Content-Type": "application/json"}
        hdr_raw = self.config.get("headers", "")
        if hdr_raw:
            try:
                headers.update(json.loads(hdr_raw))
            except json.JSONDecodeError:
                pass

        payload_tpl = self.config.get("payload_template", "")
        if payload_tpl:
            try:
                payload = json.loads(payload_tpl.format(
                    title=title, message=message, severity=severity,
                    monitor_name=monitor_name, **({} if not check_details else check_details)
                ))
            except (json.JSONDecodeError, KeyError) as e:
                payload = {"title": title, "message": message, "severity": severity, "monitor": monitor_name}
        else:
            payload = {
                "event": "alert",
                "title": title,
                "message": message,
                "severity": severity,
                "monitor": monitor_name,
                "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
            }
            if check_details:
                payload["details"] = check_details

        try:
            resp = requests.request(method, url, json=payload, headers=headers, timeout=15)
            if resp.status_code < 400:
                return NotificationResult(success=True, message=f"Webhook sent (HTTP {resp.status_code})")
            else:
                return NotificationResult(success=False, message=f"Webhook failed: HTTP {resp.status_code}")
        except Exception as e:
            return NotificationResult(success=False, message=f"Webhook error: {e}")
