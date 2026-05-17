import requests
from src.outbounds import BaseOutbound, DispatchResult, register_outbound
from requests.auth import HTTPBasicAuth


@register_outbound
class TwilioSmsOutbound(BaseOutbound):
    channel_type = "twilio_sms"
    name = "SMS (Twilio)"
    config_schema = {
        "account_sid": {"type": "string", "label": "Account SID", "required": True},
        "auth_token": {"type": "string", "label": "Auth Token", "required": True},
        "from_number": {"type": "string", "label": "From number", "required": True},
        "to_number": {"type": "string", "label": "To number", "required": True},
    }

    def send(self, title: str, message: str, severity: str, source_name: str = "",
             item_url: str = "") -> DispatchResult:
        sid = self.config.get("account_sid", "")
        token = self.config.get("auth_token", "")
        from_num = self.config.get("from_number", "")
        to_num = self.config.get("to_number", "")
        if not all([sid, token, from_num, to_num]):
            return DispatchResult(success=False, message="Twilio not configured")

        body = f"[{severity.upper()}] {source_name}: {title}"[:1600]

        try:
            resp = requests.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                auth=HTTPBasicAuth(sid, token),
                data={"From": from_num, "To": to_num, "Body": body},
                timeout=15
            )
            return DispatchResult(success=resp.status_code == 201, message=f"HTTP {resp.status_code}")
        except Exception as e:
            return DispatchResult(success=False, message=str(e))
