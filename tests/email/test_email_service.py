"""Tests for EmailService generic send, verification, and price alert emails."""

from email.mime.multipart import MIMEMultipart
from unittest.mock import MagicMock, patch

import pytest

from src.core.email import EmailSendError, EmailService


@pytest.fixture
def email_service():
    return EmailService()


def _get_html_part(msg):
    """Extract the HTML part from an EmailMessage."""
    for part in msg.iter_parts():
        if part.get_content_type() == "text/html":
            return part.get_payload()
    return None


def _get_text_part(msg):
    """Extract the plain-text part from an EmailMessage."""
    # For multipart messages the first part is typically text/plain
    for part in msg.iter_parts():
        if part.get_content_type() == "text/plain":
            return part.get_payload()
    return None


class TestSendEmailGeneric:
    """Test the generic send_email method."""

    def test_send_email_renders_and_sends(self, email_service):
        with (
            patch("src.core.email.settings") as mock_settings,
            patch("src.core.email.smtplib.SMTP") as mock_smtp_cls,
        ):
            mock_settings.smtp_host = "smtp.test.com"
            mock_settings.smtp_port = 587
            mock_settings.smtp_use_tls = True
            mock_settings.smtp_user = "user"
            mock_settings.smtp_password = "pass"
            mock_settings.smtp_sender_email = "test@example.com"

            mock_server = MagicMock()
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

            email_service.send_email(
                "recipient@test.com",
                "Test Subject",
                html_template="verify_email.html",
                text_template="verify_email.txt",
                context={"link": "http://test.com/verify?token=abc"},
            )

            mock_server.send_message.assert_called_once()
            msg = mock_server.send_message.call_args[0][0]
            assert msg["To"] == "recipient@test.com"
            assert msg["Subject"] == "Test Subject"
            assert msg["From"] == "test@example.com"

    def test_send_email_raises_on_smtp_failure(self, email_service):
        with (
            patch("src.core.email.settings") as mock_settings,
            patch("src.core.email.smtplib.SMTP") as mock_smtp_cls,
        ):
            mock_settings.smtp_host = "bad.com"
            mock_settings.smtp_port = 587
            mock_settings.smtp_use_tls = False
            mock_settings.smtp_user = ""
            mock_settings.smtp_password = ""
            mock_settings.smtp_sender_email = "test@example.com"
            mock_smtp_cls.side_effect = ConnectionRefusedError("refused")

            with pytest.raises(EmailSendError, match="Failed to send email"):
                email_service.send_email(
                    "recipient@test.com",
                    "Test",
                    html_template="verify_email.html",
                    text_template="verify_email.txt",
                    context={"link": "http://test.com"},
                )


class TestSendVerificationEmail:
    """Test that send_verification_email still works after refactor."""

    def test_send_verification_email_contains_link(self, email_service):
        with (
            patch("src.core.email.settings") as mock_settings,
            patch("src.core.email.smtplib.SMTP") as mock_smtp_cls,
        ):
            mock_settings.frontend_url = "http://localhost:8101"
            mock_settings.smtp_host = "smtp.test.com"
            mock_settings.smtp_port = 587
            mock_settings.smtp_use_tls = False
            mock_settings.smtp_user = ""
            mock_settings.smtp_password = ""
            mock_settings.smtp_sender_email = "noreply@test.com"

            mock_server = MagicMock()
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

            email_service.send_verification_email("user@test.com", "token123")

            msg = mock_server.send_message.call_args[0][0]
            assert msg["To"] == "user@test.com"
            assert msg["Subject"] == "Verify your email"

            html_part = _get_html_part(msg)
            assert html_part is not None
            # The link appears in the rendered HTML (may be MIME-encoded in transport)
            assert "verify-email" in html_part
            assert "token123" in html_part
            assert "localhost:8101" in html_part

    def test_send_verification_email_text_contains_link(self, email_service):
        with (
            patch("src.core.email.settings") as mock_settings,
            patch("src.core.email.smtplib.SMTP") as mock_smtp_cls,
        ):
            mock_settings.frontend_url = "http://localhost:8101"
            mock_settings.smtp_host = "smtp.test.com"
            mock_settings.smtp_port = 587
            mock_settings.smtp_use_tls = False
            mock_settings.smtp_user = ""
            mock_settings.smtp_password = ""
            mock_settings.smtp_sender_email = "noreply@test.com"

            mock_server = MagicMock()
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

            email_service.send_verification_email("user@test.com", "token123")

            msg = mock_server.send_message.call_args[0][0]
            text_part = _get_text_part(msg)
            assert text_part is not None
            assert "verify-email" in text_part
            assert "token123" in text_part
            assert "localhost:8101" in text_part


class TestSendPriceAlertEmail:
    """Test price alert email rendering and sending."""

    def test_send_price_alert_email_above(self, email_service):
        from decimal import Decimal
        from uuid import uuid4

        sec_id = uuid4()
        with (
            patch("src.core.email.settings") as mock_settings,
            patch("src.core.email.smtplib.SMTP") as mock_smtp_cls,
        ):
            mock_settings.frontend_url = "http://localhost:8101"
            mock_settings.smtp_host = "smtp.test.com"
            mock_settings.smtp_port = 587
            mock_settings.smtp_use_tls = False
            mock_settings.smtp_user = ""
            mock_settings.smtp_password = ""
            mock_settings.smtp_sender_email = "alerts@test.com"

            mock_server = MagicMock()
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

            email_service.send_price_alert_email(
                recipient="user@test.com",
                security_name="Apple Inc",
                security_symbol="AAPL",
                condition="above",
                target_price=Decimal("150.00"),
                latest_price=Decimal("152.50"),
                security_id=sec_id,
            )

            msg = mock_server.send_message.call_args[0][0]
            assert msg["To"] == "user@test.com"
            assert msg["Subject"] == "Price Alert: Apple Inc (AAPL)"

            html_part = _get_html_part(msg)
            assert html_part is not None
            assert "Apple Inc" in html_part
            assert "AAPL" in html_part
            assert "rose above" in html_part
            assert "The price rose above $150.00" in html_part
            assert "150.00" in html_part
            assert "152.50" in html_part
            # UUID in the URL may be MIME line-wrapped, so check the path prefix
            assert "/security/" in html_part
            assert str(sec_id)[:8] in html_part

    def test_send_price_alert_email_below(self, email_service):
        from decimal import Decimal
        from uuid import uuid4

        sec_id = uuid4()
        with (
            patch("src.core.email.settings") as mock_settings,
            patch("src.core.email.smtplib.SMTP") as mock_smtp_cls,
        ):
            mock_settings.frontend_url = "http://localhost:8101"
            mock_settings.smtp_host = "smtp.test.com"
            mock_settings.smtp_port = 587
            mock_settings.smtp_use_tls = False
            mock_settings.smtp_user = ""
            mock_settings.smtp_password = ""
            mock_settings.smtp_sender_email = "alerts@test.com"

            mock_server = MagicMock()
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

            email_service.send_price_alert_email(
                recipient="user@test.com",
                security_name="Microsoft Corp",
                security_symbol="MSFT",
                condition="below",
                target_price=Decimal("300.00"),
                latest_price=Decimal("298.00"),
                security_id=sec_id,
            )

            msg = mock_server.send_message.call_args[0][0]
            assert msg["To"] == "user@test.com"

            html_part = _get_html_part(msg)
            assert html_part is not None
            assert "fell below" in html_part

    def test_send_price_alert_email_raises_on_smtp_failure(self, email_service):
        from decimal import Decimal
        from uuid import uuid4

        with (
            patch("src.core.email.settings") as mock_settings,
            patch("src.core.email.smtplib.SMTP") as mock_smtp_cls,
        ):
            mock_settings.frontend_url = "http://localhost:8101"
            mock_settings.smtp_host = "bad.com"
            mock_settings.smtp_port = 587
            mock_settings.smtp_use_tls = False
            mock_settings.smtp_user = ""
            mock_settings.smtp_password = ""
            mock_settings.smtp_sender_email = "alerts@test.com"
            mock_smtp_cls.side_effect = ConnectionRefusedError("refused")

            with pytest.raises(EmailSendError):
                email_service.send_price_alert_email(
                    "user@test.com",
                    "Test",
                    "TST",
                    "above",
                    Decimal("100"),
                    Decimal("101"),
                    uuid4(),
                )
