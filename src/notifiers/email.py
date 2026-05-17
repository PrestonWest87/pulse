from src.notifiers import BaseNotifier, NotificationResult, register_notifier
from src.mailer import send_alert_email


@register_notifier
class EmailNotifier(BaseNotifier):
    channel_type = "email"
    name = "Email (SMTP)"
    config_schema = {
        "recipient": {"type": "string", "label": "Recipient email", "required": True},
    }

    def send(self, title: str, message: str, severity: str, monitor_name: str = "",
             check_details: dict = None) -> NotificationResult:
        recipient = self.config.get("recipient", "")
        if not recipient:
            return NotificationResult(success=False, message="No recipient configured")

        subject = f"[{severity.upper()}] {title}"
        body = message
        if monitor_name:
            body = f"Monitor: {monitor_name}\nSeverity: {severity.upper()}\n\n{message}"
        if check_details:
            body += "\n\nDetails:\n"
            for k, v in check_details.items():
                body += f"  {k}: {v}\n"

        success, msg = send_alert_email(subject, body, recipient_override=recipient, is_html=False)
        return NotificationResult(success=success, message=msg)
