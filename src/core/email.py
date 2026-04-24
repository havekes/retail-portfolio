import logging
import smtplib
from email.message import EmailMessage
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from src.config.settings import settings

logger = logging.getLogger(__name__)

template_dir = Path(__file__).parent.parent / "templates" / "email"
jinja_env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=True,
)


class EmailSendError(Exception):
    pass


class EmailService:
    def send_verification_email(self, email: str, token: str) -> None:
        link = f"{settings.frontend_url}/auth/verify-email?token={token}"

        template_html = jinja_env.get_template("verify_email.html")
        template_text = jinja_env.get_template("verify_email.txt")

        html_content = template_html.render(link=link)
        text_content = template_text.render(link=link)

        msg = EmailMessage()
        msg["Subject"] = "Verify your email"
        msg["From"] = settings.smtp_sender_email
        msg["To"] = email

        msg.set_content(text_content)
        msg.add_alternative(html_content, subtype="html")

        logger.info(
            "Sending email via SMTP to %s at %s:%s",
            email,
            settings.smtp_host,
            settings.smtp_port,
        )
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                if settings.smtp_use_tls:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                if settings.smtp_user and settings.smtp_password:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
        except Exception as exc:
            logger.exception("Failed to send email")
            msg = "Failed to send verification email"
            raise EmailSendError(msg) from exc
