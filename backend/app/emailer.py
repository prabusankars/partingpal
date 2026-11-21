import logging
import smtplib
from email.message import EmailMessage

from .config import get_settings

log = logging.getLogger(__name__)


def email_configured() -> bool:
    s = get_settings()
    return bool(s.smtp_host and s.smtp_from)


def _send(msg: EmailMessage) -> None:
    s = get_settings()
    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as smtp:
        smtp.starttls()
        if s.smtp_user:
            smtp.login(s.smtp_user, s.smtp_password or "")
        smtp.send_message(msg)


def send_escalation(to: str, employee_name: str, department: str, admin_link: str) -> bool:
    """Tell the HR executive an interview was escalated. The email carries no transcript, only a dashboard link."""
    s = get_settings()
    if not email_configured():
        log.warning("Interview escalated but email is not configured; HR must check the dashboard")
        return False
    msg = EmailMessage()
    msg["Subject"] = f"Exit interview escalated: {employee_name} ({department})"
    msg["From"] = s.smtp_from
    msg["To"] = to
    msg.set_content(
        f"The exit interview with {employee_name} from {department} was ended early because several replies "
        f"were abusive. Parting Pal told them their concerns will be passed to the HR executive, who may "
        f"arrange an in-person session to understand their frustration.\n\n"
        f"Review the conversation (sign-in required):\n{admin_link}\n\nParting Pal"
    )
    try:
        _send(msg)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        log.error("Failed to send escalation email to %s: %s", to, exc)
        return False


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
        _send(msg)
        return True
    except (smtplib.SMTPException, OSError) as exc:
        log.error("Failed to send invitation email for %s: %s", to, exc)
        return False
