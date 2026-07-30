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
    """Synchronous email service using smtplib.

    All send methods are synchronous (blocking smtplib). Async callers
    (e.g. Huey tasks) should bridge via asyncio.to_thread().
    """

    def send_email(
        self,
        recipient: str,
        subject: str,
        *,
        html_template: str,
        text_template: str,
        context: dict,
    ) -> None:
        """Generic email send: renders templates and SMTP-sends.

        Args:
            recipient: destination email address.
            subject: email subject line.
            html_template: Jinja template name for HTML body (e.g. "verify_email.html").
            text_template: Jinja template name for text body (e.g. "verify_email.txt").
            context: variables passed to both templates.

        Raises:
            EmailSendError: on any SMTP failure.
        """
        template_html = jinja_env.get_template(html_template)
        template_text = jinja_env.get_template(text_template)

        html_content = template_html.render(**context)
        text_content = template_text.render(**context)

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = settings.smtp_sender_email
        msg["To"] = recipient

        msg.set_content(text_content)
        msg.add_alternative(html_content, subtype="html")

        logger.info(
            "Sending email via SMTP to %s at %s:%s",
            recipient,
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
            raise EmailSendError("Failed to send email") from exc

    def send_verification_email(self, email: str, token: str) -> None:
        """Send email verification link. Thin wrapper over send_email."""
        link = f"{settings.frontend_url}/auth/verify-email?token={token}"
        self.send_email(
            email,
            "Verify your email",
            html_template="verify_email.html",
            text_template="verify_email.txt",
            context={"link": link},
        )

    def send_price_alert_email(
        self,
        recipient: str,
        security_name: str,
        security_symbol: str,
        condition: str,
        target_price,
        latest_price,
        security_id,
    ) -> None:
        """Send a price alert notification email.

        Args:
            recipient: user's email address.
            security_name: full security name (e.g. "Apple Inc").
            security_symbol: ticker symbol (e.g. "AAPL").
            condition: alert condition ("above" or "below").
            target_price: the target price the user set.
            latest_price: the latest intraday close price.
            security_id: UUID of the security for the deeplink.
        """
        # Humanize the condition text
        if condition == "above":
            condition_text = "rose above"
        else:
            condition_text = "fell below"

        deeplink = f"{settings.frontend_url}/security/{security_id}"

        self.send_email(
            recipient,
            f"Price Alert: {security_name} ({security_symbol})",
            html_template="price_alert.html",
            text_template="price_alert.txt",
            context={
                "security_name": security_name,
                "security_symbol": security_symbol,
                "condition_text": condition_text,
                "target_price": str(target_price),
                "latest_price": str(latest_price),
                "deeplink": deeplink,
            },
        )
