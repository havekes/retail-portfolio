import logging
import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from itsdangerous import URLSafeTimedSerializer
from jinja2 import Environment, FileSystemLoader

from src.auth.api_types import UserId
from src.auth.repository import UserRepository, VerificationTokenRepository
from src.config.settings import settings

logger = logging.getLogger(__name__)

# Initialize Jinja2 environment
template_dir = Path(__file__).parent.parent / "templates" / "email"
jinja_env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=True,
)


class EmailService:
    def send_verification_email(self, email: str, token: str) -> None:
        """
        Send an email verification token using Jinja2 templates.
        """
        link = f"{settings.frontend_url}/auth/verify-email?token={token}"

        # Render templates
        template_html = jinja_env.get_template("verify_email.html")
        template_text = jinja_env.get_template("verify_email.txt")

        html_content = template_html.render(link=link)
        text_content = template_text.render(link=link)

        msg = EmailMessage()
        msg["Subject"] = "Verify your email"
        msg["From"] = settings.smtp_sender_email
        msg["To"] = email

        # Set plain text as the main content, then add HTML alternative
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
                if settings.smtp_user and settings.smtp_password:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
        except Exception:
            logger.exception("Failed to send email")


class EmailVerificationService:
    _user_repository: UserRepository
    _token_repository: VerificationTokenRepository
    _email_service: EmailService
    _serializer: URLSafeTimedSerializer

    def __init__(
        self,
        user_repository: UserRepository,
        token_repository: VerificationTokenRepository,
        email_service: EmailService,
    ):
        self._user_repository = user_repository
        self._token_repository = token_repository
        self._email_service = email_service
        self._serializer = URLSafeTimedSerializer(settings.secret_key)

    def _generate_token(self, email: str) -> str:
        # Add a random uuid string so the token is always unique
        # even if the same email is signed up/resent immediately
        payload = {"email": email, "nonce": str(uuid4())}
        return self._serializer.dumps(payload, salt="email-verification")

    async def generate_and_send_verification(self, email: str, user_id: UserId) -> None:
        await self._token_repository.invalidate_tokens_for_user(user_id)

        token = self._generate_token(email)

        expires_at = datetime.now(UTC) + timedelta(
            hours=settings.email_verification_token_expiry_hours
        )

        await self._token_repository.create_token(
            user_id=user_id,
            token=token,
            expires_at=expires_at,
        )

        self._email_service.send_verification_email(email, token)

    async def verify_token(self, token: str) -> None:
        token_record = await self._token_repository.get_by_token(token)
        if not token_record:
            raise HTTPException(400, "Invalid or expired verification token")

        if token_record.is_used:
            raise HTTPException(400, "Token has already been used")

        # Ensure we're comparing offset-aware datetimes
        expires_at = token_record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at < datetime.now(UTC):
            raise HTTPException(400, "Token has expired")

        try:
            payload = self._serializer.loads(
                token,
                salt="email-verification",
                max_age=settings.email_verification_token_expiry_hours * 3600,
            )
            email = payload["email"]
        except Exception as e:
            raise HTTPException(400, "Invalid token") from e

        user = await self._user_repository.get_by_email(email)
        if not user or user.id != token_record.user_id:
            raise HTTPException(400, "Invalid user for this token")

        await self._user_repository.mark_as_verified(user.id)
        await self._token_repository.mark_as_used(token_record.id)

    async def resend_verification(self, email: str) -> None:
        user = await self._user_repository.get_by_email(email)
        if not user or user.is_verified:
            # Silently succeed to prevent email enumeration
            return

        # Optional: You could check if a valid token already exists and just resend that
        # Or generate a new one, invalidating old ones (by ignoring them)
        await self.generate_and_send_verification(user.email, user.id)
