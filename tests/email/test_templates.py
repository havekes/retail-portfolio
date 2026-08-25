"""Test email template rendering integrity."""

import pytest

from src.core.email import jinja_env


class TestVerifyEmailTemplates:
    """Verify-email templates must render identically to pre-refactor output."""

    def test_verify_email_html_contains_link(self):
        template = jinja_env.get_template("verify_email.html")
        test_link = "http://localhost:8101/auth/verify-email?token=abc123"
        html = template.render(link=test_link)

        assert test_link in html
        assert "Verify Email" in html
        assert "Verify your email address" in html
        assert 'href="' in html

    def test_verify_email_html_extends_base(self):
        template = jinja_env.get_template("verify_email.html")
        test_link = "http://localhost:8101/auth/verify-email?token=abc123"
        html = template.render(link=test_link)

        # Structural elements from base.html must be present
        assert "Retail Portfolio" in html
        assert "class=\"container\"" in html
        assert "class=\"card\"" in html
        assert "class=\"logo\"" in html
        assert "class=\"footer\"" in html
        assert "class=\"button\"" in html

    def test_verify_email_text_contains_link(self):
        template = jinja_env.get_template("verify_email.txt")
        test_link = "http://localhost:8101/auth/verify-email?token=abc123"
        text = template.render(link=test_link)

        assert test_link in text
        assert "Verify your email address" in text
        assert "Retail Portfolio" in text

    def test_verify_email_html_has_doctype_and_style(self):
        """The HTML template must include DOCTYPE and <style> from base."""
        template = jinja_env.get_template("verify_email.html")
        test_link = "http://localhost:8101/auth/verify-email?token=abc123"
        html = template.render(link=test_link)

        assert "<!DOCTYPE html>" in html
        assert "<style>" in html
        assert "font-family" in html

    def test_verify_email_text_no_html_tags(self):
        """Text template should not contain HTML tags."""
        template = jinja_env.get_template("verify_email.txt")
        test_link = "http://localhost:8101/auth/verify-email?token=abc123"
        text = template.render(link=test_link)

        assert "<html" not in text.lower()
        assert "<style" not in text.lower()
        assert "<div" not in text.lower()


class TestPriceAlertTemplates:
    """Price alert templates must render all context vars correctly."""

    def test_price_alert_html_contains_all_vars(self):
        template = jinja_env.get_template("price_alert.html")
        context = {
            "security_name": "Apple Inc",
            "security_symbol": "AAPL",
            "condition_text": "rose above",
            "target_price": "150.00",
            "latest_price": "152.50",
            "deeplink": "http://localhost:8101/security/abc-uuid",
        }
        html = template.render(**context)

        assert "Apple Inc" in html
        assert "AAPL" in html
        assert "rose above" in html
        assert "150.00" in html
        assert "152.50" in html
        assert "http://localhost:8101/security/abc-uuid" in html
        assert "View Apple Inc" in html

    def test_price_alert_html_extends_base(self):
        template = jinja_env.get_template("price_alert.html")
        context = {
            "security_name": "Test",
            "security_symbol": "TST",
            "condition_text": "fell below",
            "target_price": "100.00",
            "latest_price": "99.00",
            "deeplink": "http://localhost:8101/security/xyz",
        }
        html = template.render(**context)

        assert "<!DOCTYPE html>" in html
        assert "class=\"container\"" in html
        assert "Retail Portfolio" in html

    def test_price_alert_text_contains_all_vars(self):
        template = jinja_env.get_template("price_alert.txt")
        context = {
            "security_name": "Microsoft Corp",
            "security_symbol": "MSFT",
            "condition_text": "fell below",
            "target_price": "300.00",
            "latest_price": "298.50",
            "deeplink": "http://localhost:8101/security/def-uuid",
        }
        text = template.render(**context)

        assert "Microsoft Corp" in text
        assert "MSFT" in text
        assert "fell below" in text
        assert "300.00" in text
        assert "298.50" in text
        assert "http://localhost:8101/security/def-uuid" in text

    def test_price_alert_text_no_html_tags(self):
        template = jinja_env.get_template("price_alert.txt")
        context = {
            "security_name": "Test",
            "security_symbol": "TST",
            "condition_text": "rose above",
            "target_price": "100",
            "latest_price": "101",
            "deeplink": "http://localhost:8101/security/123",
        }
        text = template.render(**context)

        assert "<html" not in text.lower()
        assert "<style" not in text.lower()
        assert "<div" not in text.lower()


class TestExternalAccountErrorTemplates:
    """External account error templates must render all context vars correctly."""

    def test_external_account_error_html_contains_all_vars(self):
        template = jinja_env.get_template("external_account_error.html")
        context = {
            "account_name": "TFSA Trading",
            "institution_name": "Wealthsimple",
            "error_message": "Invalid API credentials or session expired.",
            "deeplink": "http://localhost:8101/accounts",
        }
        html = template.render(**context)

        assert "TFSA Trading" in html
        assert "Wealthsimple" in html
        assert "Invalid API credentials or session expired." in html
        assert "http://localhost:8101/accounts" in html
        assert "View Accounts" in html
        assert "Sync Error: TFSA Trading (Wealthsimple)" in html

    def test_external_account_error_html_extends_base(self):
        template = jinja_env.get_template("external_account_error.html")
        context = {
            "account_name": "Checking",
            "institution_name": "Bank",
            "error_message": "Network timeout",
            "deeplink": "http://localhost:8101/accounts",
        }
        html = template.render(**context)

        assert "<!DOCTYPE html>" in html
        assert "class=\"container\"" in html
        assert "class=\"card\"" in html
        assert "Retail Portfolio" in html

    def test_external_account_error_html_escapes_special_chars(self):
        template = jinja_env.get_template("external_account_error.html")
        context = {
            "account_name": "Test <Account>",
            "institution_name": "Bank & Co",
            "error_message": "<script>alert('xss')</script> & error",
            "deeplink": "http://localhost:8101/accounts?a=1&b=2",
        }
        html = template.render(**context)

        assert "<script>" not in html
        assert "&lt;script&gt;alert(&#39;xss&#39;)&lt;/script&gt; &amp; error" in html
        assert "Test &lt;Account&gt;" in html
        assert "Bank &amp; Co" in html

    def test_external_account_error_text_contains_all_vars(self):
        template = jinja_env.get_template("external_account_error.txt")
        context = {
            "account_name": "RRSP Investing",
            "institution_name": "Questrade",
            "error_message": "Rate limit exceeded. Please try again later.",
            "deeplink": "http://localhost:8101/accounts",
        }
        text = template.render(**context)

        assert "RRSP Investing" in text
        assert "Questrade" in text
        assert "Rate limit exceeded. Please try again later." in text
        assert "http://localhost:8101/accounts" in text
        assert "Sync Error: RRSP Investing (Questrade)" in text
        assert "Retail Portfolio" in text

    def test_external_account_error_text_no_html_tags(self):
        template = jinja_env.get_template("external_account_error.txt")
        context = {
            "account_name": "Test",
            "institution_name": "Bank",
            "error_message": "Failed sync",
            "deeplink": "http://localhost:8101/accounts",
        }
        text = template.render(**context)

        assert "<html" not in text.lower()
        assert "<style" not in text.lower()
        assert "<div" not in text.lower()
        assert "<a" not in text.lower()

