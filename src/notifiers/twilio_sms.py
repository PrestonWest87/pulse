import requests
from src.notifiers import BaseNotifier, NotificationResult, register_notifier
from requests.auth import HTTPBasicAuth


@register_notifier
class TwilioSmsNotifier(BaseNotifier):
    channel_type = "twilio_sms"
    name = "SMS (Twilio)"
    config_schema = {
        "account_sid": {"type": "string", "label": "Twilio Account SID", "required": True},
        "auth_token": {"type": "string", "label": "Twilio Auth Token", "required": True},
        "from_number": {"type": "string", "label": "Twilio Phone Number (e.g. +15551234567)", "required": True},
        "to_number": {"type": "string", "label": "Destination Phone Number", "required": True},
    }

    def send(self, title: str, message: str, severity: str, monitor_name: str = "",
             check_details: dict = None) -> NotificationResult:
        sid = self.config.get("account_sid", "")
        token = self.config.get("auth_token", "")
        from_num = self.config.get("from_number", "")
        to_num = self.config.get("to_number", "")

        if not all([sid, token, from_num, to_num]):
            return NotificationResult(success=False, message="Twilio not fully configured")

        body = f"[{severity.upper()}] {title}"
        if monitor_name:
            body = f"[{severity.upper()}] {monitor_name}: {title}"
        body = body[:1600]

        try:
            resp = requests.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                auth=HTTPBasicAuth(sid, token),
                data={"From": from_num, "To": to_num, "Body": body},
                timeout=15
            )
            if resp.status_code == 201:
                return NotificationResult(success=True, message="SMS sent")
            return NotificationResult(success=False, message=f"Twilio error: {resp.status_code} {resp.text[:100]}")
        except Exception as e:
            return NotificationResult(success=False, message=f"Twilio error: {e}")
