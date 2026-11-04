import logging
import smtplib
from email.message import EmailMessage

from .config import get_settings

log = logging.getLogger(__name__)


def email_configured() -> bool:
    s = get_settings()
    return bool(s.smtp_host and s.smtp_from)


def send_invitation(to: str, name: str, link: str, valid_days: int) -> bool:
    """Send the interview link. Returns False (and logs) instead of raising so HR can copy the link manually."""
    s = get_settings()
    if not email_configured():
        return False
    msg = EmailMessage()
    msg["Subject"] = f"Your exit interview with {s.company_name}"
    msg["From"] = s.smtp_from
    msg["To"] = to
    msg.set_content(
        f"Hi {name},\n\n"
        f"Thank you for your time at {s.company_name}. We'd value your honest feedback in a short, "
        f"confidential conversation with Parting Pal, our HR assistant:\n\n{link}\n\n"
        f"The link is valid for {valid_days} days.\n\nBest wishes,\nHR team"
    )
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as smtp:
            smtp.starttls()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password or "")
            smtp.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        log.error("Failed to send invitation email for %s: %s", to, exc)
        return False
