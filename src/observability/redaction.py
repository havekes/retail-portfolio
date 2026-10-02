from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from opentelemetry.attributes import BoundedAttributes
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor

REDACTED_MASK = "[REDACTED]"

# Keys that are allowed internal telemetry dimensions and must never be redacted
PROTECTED_KEYS: frozenset[str] = frozenset(
    {
        "provider",
        "provider_name",
        "provider.name",
        "provider_id",
        "provider.id",
        "broker",
        "broker_name",
        "broker.name",
        "broker_id",
        "broker.id",
        "market_provider",
        "market_provider_name",
    }
)

# Exact sensitive key names (checked case-insensitively and with '-' normalized to '_')
SENSITIVE_EXACT_KEYS: frozenset[str] = frozenset(
    {
        "authorization",
        "proxy_authorization",
        "proxy-authorization",
        "x_service_token",
        "x-service-token",
        "cookie",
        "cookies",
        "set_cookie",
        "set-cookie",
        "password",
        "passwords",
        "secret",
        "secrets",
        "token",
        "tokens",
        "auth_token",
        "access_token",
        "refresh_token",
        "api_key",
        "api-key",
        "apikey",
        "apikeys",
        "api_token",
        "session_id",
        "session_key",
        "session_token",
        "private_key",
        "client_secret",
        "otp",
        "totp",
        "2fa",
        "two_factor_code",
        "email",
        "emails",
    }
)

# Suffixes marking a key as sensitive
SENSITIVE_SUFFIXES: tuple[str, ...] = (
    "_token",
    "_tokens",
    "_secret",
    "_secrets",
    "_password",
    "_passwords",
    "_api_key",
    "_api_keys",
    "_otp",
    "_2fa",
    "_email",
    "_emails",
    "-token",
    "-tokens",
    "-secret",
    "-secrets",
    "-password",
    "-passwords",
    "-api-key",
    "-api-keys",
    "-otp",
    "-2fa",
    "-email",
    "-emails",
)

ALL_SENSITIVE_SUFFIXES: tuple[str, ...] = tuple(
    {suffix for s in SENSITIVE_SUFFIXES for suffix in (s, s.replace("-", "_"))}
)

# Regex patterns for scrubbing sensitive substrings
BEARER_PATTERN = re.compile(
    r"(?i)\b(bearer\s+)([A-Za-z0-9_\-\.~+/]+=*)",
)
JWT_PATTERN = re.compile(
    r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+",
)
BROKER_SESSION_PATTERN = re.compile(
    r"\bws_sess_[A-Za-z0-9_\-]+\b",
)
SESSION_KV_PATTERN = re.compile(
    r"(?i)\b((?:ws_session|session_token|session_id|session_key)[\"'\s]*[=:]\s*[\"']?)[^\s,;'\"&]+",
)
OTP_PATTERN = re.compile(
    r"(?i)\b((?:otp(?:_code)?|totp|2fa(?:_code)?|two_factor_code)[\"'\s]*[=:]\s*[\"']?)(?:[0-9]{4,8}|[A-Za-z0-9]{6,8})\b",
)
URL_CREDENTIAL_PATTERN = re.compile(
    r"(?i)([?&](?:api[_-]?key|api[_-]?token|access[_-]?token|token|secret|password)=)[^&\s'\"]+",
)
EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
)


def is_sensitive_key(key: str) -> bool:
    """Determine whether a key represents a sensitive credential or token."""
    if not isinstance(key, str) or not key:
        return False

    norm = key.lower().strip()
    if norm in PROTECTED_KEYS:
        return False

    leaf = norm.rsplit(".", 1)[-1].rsplit(":", 1)[-1].strip()
    if leaf in PROTECTED_KEYS and norm not in SENSITIVE_EXACT_KEYS:
        return False

    norm_clean = norm.replace("-", "_")
    leaf_clean = leaf.replace("-", "_")
    candidates = {norm, leaf, norm_clean, leaf_clean}
    if not candidates.isdisjoint(SENSITIVE_EXACT_KEYS):
        return True

    return any(
        c.endswith(ALL_SENSITIVE_SUFFIXES) for c in (norm, leaf, norm_clean, leaf_clean)
    )


def redact_string(text: str) -> str:
    """Scrub sensitive patterns from a string value."""
    if not isinstance(text, str) or not text:
        return text

    s = BEARER_PATTERN.sub(r"\g<1>" + REDACTED_MASK, text)
    s = JWT_PATTERN.sub(REDACTED_MASK, s)
    s = BROKER_SESSION_PATTERN.sub(REDACTED_MASK, s)
    s = SESSION_KV_PATTERN.sub(r"\g<1>" + REDACTED_MASK, s)
    s = OTP_PATTERN.sub(r"\g<1>" + REDACTED_MASK, s)
    s = URL_CREDENTIAL_PATTERN.sub(r"\g<1>" + REDACTED_MASK, s)
    return EMAIL_PATTERN.sub(REDACTED_MASK, s)


def redact_value(key: str, value: Any) -> Any:
    """Recursively redact a value based on key sensitivity and content scrubbing."""
    if is_sensitive_key(key):
        return REDACTED_MASK

    if isinstance(value, str):
        return redact_string(value)
    if isinstance(value, Mapping):
        return redact_event_fields(value)
    if isinstance(value, (list, tuple)):
        redacted_items = [
            redact_value(key if isinstance(item, (int, float, bool)) else "", item)
            for item in value
        ]
        return tuple(redacted_items) if isinstance(value, tuple) else redacted_items
    if isinstance(value, set):
        return {redact_value("", item) for item in value}
    return value


def redact_event_fields(fields: Mapping[str, Any]) -> dict[str, Any]:
    """Return a scrubbed dictionary without silently dropping any keys."""
    return {str(k): redact_value(str(k), v) for k, v in fields.items()}


def redact_exception_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Apply field and pattern scrubbing specifically for exception records."""
    return redact_event_fields(record)


def _redact_attributes_container(raw_attrs: Any) -> Any:
    """Redact an attributes container and return an updated or new container."""
    if not raw_attrs:
        return raw_attrs
    redacted = redact_event_fields(raw_attrs)
    if isinstance(raw_attrs, BoundedAttributes):
        return BoundedAttributes(
            maxlen=getattr(raw_attrs, "maxlen", None),
            attributes=redacted,
            immutable=True,
            max_value_len=getattr(raw_attrs, "max_value_len", None),
        )
    if isinstance(raw_attrs, dict):
        raw_attrs.clear()
        raw_attrs.update(redacted)
        return raw_attrs
    return redacted


def redact_span(span: Any) -> None:
    """Mutate span _attributes and _events in-place prior to export."""
    span_name = getattr(span, "_name", None)
    if isinstance(span_name, str):
        span._name = redact_string(span_name)  # noqa: SLF001

    if getattr(span, "_attributes", None):
        span._attributes = _redact_attributes_container(span._attributes)  # noqa: SLF001

    events = getattr(span, "_events", None)
    if events:
        for event in events:
            if getattr(event, "_attributes", None):
                event._attributes = _redact_attributes_container(  # noqa: SLF001
                    event._attributes  # noqa: SLF001
                )


class RedactingSpanProcessor(SpanProcessor):
    """SpanProcessor that scrubs sensitive keys and values before export."""

    def on_end(self, span: ReadableSpan) -> None:
        """Process ended span before downstream exporter processors receive it."""
        redact_span(span)
