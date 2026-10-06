from __future__ import annotations

from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
import pytest

from src.config.settings import Settings
from src.observability import (
    REDACTED_MASK,
    RedactingSpanProcessor,
    bootstrap_observability,
    get_tracer,
    is_sensitive_key,
    redact_event_fields,
    redact_exception_record,
    redact_string,
    redact_value,
    reset_observability,
)


@pytest.fixture(autouse=True)
def _cleanup_observability():
    yield
    reset_observability()


def test_sensitive_keys_masked():
    sensitive_keys = [
        "authorization",
        "Authorization",
        "proxy-authorization",
        "proxy_authorization",
        "x-service-token",
        "x_service_token",
        "password",
        "passwords",
        "secret",
        "secrets",
        "token",
        "tokens",
        "auth_token",
        "access_token",
        "refresh_token",
        "cookie",
        "cookies",
        "set-cookie",
        "set_cookie",
        "otp",
        "totp",
        "2fa",
        "two_factor_code",
        "api_key",
        "api-key",
        "apikey",
        "session_id",
        "session_token",
        "private_key",
        "client_secret",
        "user_password",
        "db_secret",
        "client_token",
        "http.request.header.authorization",
        "auth:password",
        "user.access_token",
    ]

    for key in sensitive_keys:
        assert is_sensitive_key(key) is True, f"Key {key} should be sensitive"

    input_fields = {
        "authorization": "Bearer raw-token-123",
        "x-service-token": "secret-svc-token",
        "password": "super-secret-password",
        "cookie": "session=abc-def-123",
        "otp": "123456",
        "token": "token-xyz",
        "normal_key": "safe_value",
        "status_code": 200,
    }

    scrubbed = redact_event_fields(input_fields)

    # Records must not be silently dropped: all keys retained
    assert set(scrubbed.keys()) == set(input_fields.keys())

    # Sensitive values replaced with REDACTED_MASK
    assert scrubbed["authorization"] == REDACTED_MASK
    assert scrubbed["x-service-token"] == REDACTED_MASK
    assert scrubbed["password"] == REDACTED_MASK
    assert scrubbed["cookie"] == REDACTED_MASK
    assert scrubbed["otp"] == REDACTED_MASK
    assert scrubbed["token"] == REDACTED_MASK

    # Non-sensitive keys remain unmasked
    assert scrubbed["normal_key"] == "safe_value"
    assert scrubbed["status_code"] == 200


def test_pattern_scrubbing_bearer_jwt():
    raw_jwt = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
        "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0."
        "G3xU9zJ7kH5v_secret_signature"
    )
    bearer_token = f"Bearer {raw_jwt}"

    scrubbed_bearer = redact_string(f"Header: {bearer_token} in request")
    assert raw_jwt not in scrubbed_bearer
    assert f"Header: Bearer {REDACTED_MASK} in request" == scrubbed_bearer

    scrubbed_raw_jwt = redact_string(f"Raw token={raw_jwt}")
    assert raw_jwt not in scrubbed_raw_jwt
    assert REDACTED_MASK in scrubbed_raw_jwt


def test_pattern_scrubbing_broker_session_token():
    broker_token = "ws_sess_abc123456789_xyz"
    raw_text = f"Connected to broker with session {broker_token} successfully"

    scrubbed = redact_string(raw_text)
    assert broker_token not in scrubbed
    assert f"Connected to broker with session {REDACTED_MASK} successfully" == scrubbed

    session_kv = "ws_session=sess_tok_9988 and session_token: tok_abc_123"
    scrubbed_kv = redact_string(session_kv)
    assert "sess_tok_9988" not in scrubbed_kv
    assert "tok_abc_123" not in scrubbed_kv
    assert f"ws_session={REDACTED_MASK} and session_token: {REDACTED_MASK}" == scrubbed_kv


def test_pattern_scrubbing_otp_code():
    samples = [
        ("otp=123456", "123456"),
        ("otp: 654321", "654321"),
        ("totp: 789012", "789012"),
        ("2fa=998877", "998877"),
        ("two_factor_code: 11223344", "11223344"),
        ("otp_code=445566", "445566"),
    ]

    for text, secret in samples:
        scrubbed = redact_string(f"User validation failed: {text}")
        assert secret not in scrubbed, f"Secret {secret} found in {scrubbed}"
        assert REDACTED_MASK in scrubbed


def test_pattern_scrubbing_url_credentials():
    url = "https://api.eodhd.com/api/eod/AAPL.US?api_token=secret_tok_123&fmt=json"
    scrubbed = redact_string(url)

    assert "secret_tok_123" not in scrubbed
    assert (
        scrubbed
        == f"https://api.eodhd.com/api/eod/AAPL.US?api_token={REDACTED_MASK}&fmt=json"
    )

    oauth_url = "https://auth.example.com/oauth/callback?access_token=acc_sec_456&state=ok"
    scrubbed_oauth = redact_string(oauth_url)
    assert "acc_sec_456" not in scrubbed_oauth
    assert (
        scrubbed_oauth
        == f"https://auth.example.com/oauth/callback?access_token={REDACTED_MASK}&state=ok"
    )


def test_pii_masking_email():
    email = "greg.havekes@example.com"
    log_text = f"Audit log: user {email} updated account balance"

    scrubbed = redact_string(log_text)
    assert email not in scrubbed
    assert f"Audit log: user {REDACTED_MASK} updated account balance" == scrubbed

    fields = {
        "user_email": "john.doe+tag@example.com",
        "username": "johndoe",
    }
    scrubbed_fields = redact_event_fields(fields)
    assert "john.doe+tag@example.com" not in str(scrubbed_fields)
    assert scrubbed_fields["user_email"] == REDACTED_MASK
    assert scrubbed_fields["username"] == "johndoe"


def test_provider_names_preserved():
    # Protected provider keys must never be classified as sensitive
    protected = [
        "provider",
        "provider_name",
        "provider.name",
        "provider_id",
        "broker",
        "broker_name",
        "broker.name",
        "broker_id",
        "market_provider",
    ]
    for key in protected:
        assert is_sensitive_key(key) is False, f"Key {key} should be protected"

    # Specific broker dimensions (e.g. broker_token) remain sensitive
    assert is_sensitive_key("broker_token") is True
    assert is_sensitive_key("provider_api_key") is True

    # Values like 'wealthsimple' or 'eodhd' are preserved and not scrubbed
    event_data = {
        "provider": "wealthsimple",
        "broker": "wealthsimple",
        "provider.name": "eodhd",
        "broker_name": "wealthsimple",
        "market_provider": "eodhd",
    }
    scrubbed = redact_event_fields(event_data)
    assert scrubbed["provider"] == "wealthsimple"
    assert scrubbed["broker"] == "wealthsimple"
    assert scrubbed["provider.name"] == "eodhd"
    assert scrubbed["broker_name"] == "wealthsimple"
    assert scrubbed["market_provider"] == "eodhd"

    # Redacting text mentioning providers preserves provider names
    text = "Connected to wealthsimple broker via eodhd market feed"
    assert redact_string(text) == text


def test_surface_span_attributes_redacted_before_export():
    exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(exporter)
    settings = Settings(environment="test")
    bootstrap_observability(
        service_name="backend",
        settings=settings,
        span_processor=processor,
    )

    tracer = get_tracer("test.tracer")
    jwt_secret = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.secret_sig_span"
    with tracer.start_as_current_span("span.attributes.surface") as span:
        span.set_attribute("authorization", f"Bearer {jwt_secret}")
        span.set_attribute("provider", "wealthsimple")
        span.set_attribute("broker", "wealthsimple")
        span.set_attribute("provider.name", "eodhd")
        span.set_attribute("user.email", "operator@example.com")
        span.set_attribute("account_id", "act-456")
        span.set_attribute(
            "fetch_url",
            "https://api.eodhd.com/v1/eod?api_token=secret_query_param",
        )

    finished = exporter.get_finished_spans()
    assert len(finished) == 1
    assert finished[0].attributes is not None
    attrs = dict(finished[0].attributes)

    # Sensitive key replaced
    assert attrs["authorization"] == REDACTED_MASK

    # Protected provider names preserved
    assert attrs["provider"] == "wealthsimple"
    assert attrs["broker"] == "wealthsimple"
    assert attrs["provider.name"] == "eodhd"

    # Non-sensitive attributes intact
    assert attrs["account_id"] == "act-456"

    # Pattern scrubs applied
    assert attrs["user.email"] == REDACTED_MASK
    assert (
        attrs["fetch_url"]
        == f"https://api.eodhd.com/v1/eod?api_token={REDACTED_MASK}"
    )

    # Verify no secret substring exists anywhere in attributes
    attrs_str = str(attrs)
    assert jwt_secret not in attrs_str
    assert "secret_query_param" not in attrs_str
    assert "operator@example.com" not in attrs_str


def test_surface_wide_event_fields_redacted():
    exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(exporter)
    settings = Settings(environment="test")
    bootstrap_observability(
        service_name="backend",
        settings=settings,
        span_processor=processor,
    )

    tracer = get_tracer("test.tracer")
    broker_token = "ws_sess_event_surface_secret"
    with tracer.start_as_current_span("wide.event.surface") as span:
        span.add_event(
            "order.submitted",
            {
                "x-service-token": "srv-tok-secret-123",
                "session": broker_token,
                "validation": "otp: 887766",
                "customer_email": "customer@example.com",
                "provider": "wealthsimple",
                "order_id": "ord-9988",
            },
        )

    finished = exporter.get_finished_spans()
    assert len(finished) == 1
    events = finished[0].events
    assert len(events) == 1
    assert events[0].attributes is not None
    event_attrs = dict(events[0].attributes)

    # Sensitive key masked
    assert event_attrs["x-service-token"] == REDACTED_MASK

    # Pattern scrubs applied
    assert event_attrs["session"] == REDACTED_MASK
    assert event_attrs["validation"] == f"otp: {REDACTED_MASK}"
    assert event_attrs["customer_email"] == REDACTED_MASK

    # Provider and un-sensitive fields preserved
    assert event_attrs["provider"] == "wealthsimple"
    assert event_attrs["order_id"] == "ord-9988"

    # No secret substring anywhere in event payload
    event_str = str(event_attrs)
    assert broker_token not in event_str
    assert "srv-tok-secret-123" not in event_str
    assert "887766" not in event_str
    assert "customer@example.com" not in event_str


def test_surface_exception_records_redacted():
    exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(exporter)
    settings = Settings(environment="test")
    bootstrap_observability(
        service_name="backend",
        settings=settings,
        span_processor=processor,
    )

    tracer = get_tracer("test.tracer")
    jwt_in_error = (
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJleGMifQ.secret_exc_sig"
    )
    session_in_error = "ws_sess_exc_secret_123"
    email_in_error = "failing_user@example.com"
    param_in_error = "secret_exc_param"

    with tracer.start_as_current_span("exception.surface") as span:
        try:
            msg = (
                f"Failed request to https://api.eodhd.com?api_token={param_in_error} "
                f"with Bearer {jwt_in_error} and session {session_in_error} "
                f"for user {email_in_error}"
            )
            raise RuntimeError(msg)
        except RuntimeError as exc:
            span.record_exception(exc)

    finished = exporter.get_finished_spans()
    assert len(finished) == 1
    events = finished[0].events
    assert len(events) == 1
    exc_event = events[0]
    assert exc_event.name == "exception"
    assert exc_event.attributes is not None
    attrs = dict(exc_event.attributes)

    assert attrs["exception.type"] == "RuntimeError"

    # Both exception.message and exception.stacktrace must be scrubbed
    msg_attr = attrs["exception.message"]
    stacktrace_attr = attrs["exception.stacktrace"]
    assert isinstance(msg_attr, str)
    assert isinstance(stacktrace_attr, str)

    for secret in (jwt_in_error, session_in_error, email_in_error, param_in_error):
        assert secret not in msg_attr, f"Found {secret} in exception.message"
        assert secret not in stacktrace_attr, f"Found {secret} in exception.stacktrace"

    assert REDACTED_MASK in msg_attr
    assert REDACTED_MASK in stacktrace_attr

    # Also test direct redact_exception_record call
    direct_record = {
        "exception.type": "ValueError",
        "exception.message": f"Auth failed with Bearer {jwt_in_error}",
        "exception.stacktrace": f"line 10 in func\n  error: user {email_in_error}",
        "password": "leak",
        "provider": "wealthsimple",
    }
    redacted_direct = redact_exception_record(direct_record)
    assert redacted_direct["exception.type"] == "ValueError"
    assert jwt_in_error not in redacted_direct["exception.message"]
    assert email_in_error not in redacted_direct["exception.stacktrace"]
    assert redacted_direct["password"] == REDACTED_MASK
    assert redacted_direct["provider"] == "wealthsimple"


def test_redact_event_fields_scrubs_exception_message_and_stacktrace():
    """Pin the entry point the frontend intake goes through (F-OBS-FIX-T03).

    ``capture_exception`` and ``emit_event`` both scrub via
    ``redact_event_fields``, so the two exception keys must survive as keys while
    their values lose the credential patterns the intake forwards.
    """
    jwt_in_error = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJleGMifQ.secret_exc_sig"
    email_in_error = "failing_user@example.com"
    fields = {
        "exception.message": (
            f"Request failed with Bearer {jwt_in_error} for {email_in_error}"
        ),
        "exception.stacktrace": f"RuntimeError: Bearer {jwt_in_error}",
    }

    redacted = redact_event_fields(fields)

    # Keys are preserved (never silently dropped)...
    assert set(redacted) == set(fields)
    # ...and the secrets inside them are scrubbed.
    assert redacted["exception.message"] == (
        f"Request failed with Bearer {REDACTED_MASK} for {REDACTED_MASK}"
    )
    assert redacted["exception.stacktrace"] == f"RuntimeError: Bearer {REDACTED_MASK}"
    for secret in (jwt_in_error, email_in_error):
        assert secret not in str(redacted)


def test_redact_value_nested_structures():
    data = {
        "users": [
            {
                "name": "Alice",
                "email": "alice@example.com",
                "token": "tok-1",
            },
            {
                "name": "Bob",
                "email": "bob@example.com",
                "token": "tok-2",
            },
        ],
        "meta": {
            "auth": {
                "password": "nested_password",
                "attempts": 3,
            },
            "broker": "wealthsimple",
        },
        "tuple_data": ("safe", "Bearer secret_tuple_tok"),
    }

    result = redact_value("root", data)

    # Users list items
    assert result["users"][0]["name"] == "Alice"
    assert result["users"][0]["email"] == REDACTED_MASK
    assert result["users"][0]["token"] == REDACTED_MASK
    assert result["users"][1]["name"] == "Bob"
    assert result["users"][1]["email"] == REDACTED_MASK
    assert result["users"][1]["token"] == REDACTED_MASK

    # Nested auth dict
    assert result["meta"]["auth"]["password"] == REDACTED_MASK
    assert result["meta"]["auth"]["attempts"] == 3
    assert result["meta"]["broker"] == "wealthsimple"

    # Tuple items
    assert result["tuple_data"][0] == "safe"
    assert result["tuple_data"][1] == f"Bearer {REDACTED_MASK}"


def test_redact_value_primitives_with_sensitive_keys():
    # Sensitive keys with numeric values are masked
    assert redact_value("otp", 123456) == REDACTED_MASK
    assert redact_value("user_token", 99999) == REDACTED_MASK

    # Non-sensitive keys with numeric/boolean values are preserved
    assert redact_value("status_code", 200) == 200
    assert redact_value("duration_ms", 12.5) == 12.5
    assert redact_value("is_active", True) is True
    assert redact_value("empty_field", None) is None
