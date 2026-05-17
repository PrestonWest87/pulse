from src.outbounds import BaseOutbound, DispatchResult, register_outbound
from src.mailer import send_alert_email


@register_outbound
class EmailOutbound(BaseOutbound):
    channel_type = "email"
    name = "Email (SMTP)"
    config_schema = {
        "recipient": {"type": "string", "label": "Recipient email", "required": True},
    }

    def send(self, title: str, message: str, severity: str, source_name: str = "",
             item_url: str = "") -> DispatchResult:
        recipient = self.config.get("recipient", "")
        if not recipient:
            return DispatchResult(success=False, message="No recipient")

        body = f"Source: {source_name}\nSeverity: {severity.upper()}\nURL: {item_url}\n\n{message}"
        success, msg = send_alert_email(f"[{severity.upper()}] {title}", body, recipient_override=recipient, is_html=False)
        return DispatchResult(success=success, message=msg)
