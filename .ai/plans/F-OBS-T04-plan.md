## Plan

**Approach:** Implement a centralized telemetry redaction module (`src/observability/redaction.py`) defining deny-by-default sensitive key sets and regex scrubbing patterns (Bearer tokens, JWTs, broker session material, OTP codes, URL query credentials, email PII), while preserving provider identities. Wrap this boundary into a custom OpenTelemetry `RedactingSpanProcessor` hooked into `bootstrap_observability` ahead of exporters, ensuring automatic redaction across spans, wide-event fields, and exception records before telemetry leaves the process.

**Files:**
- `src/observability/redaction.py` — create: Sensitive key lists, scrubbing patterns, `redact_string`, `redact_value`, `redact_event_fields`, `redact_exception_record`, `redact_span`, and `RedactingSpanProcessor`.
- `src/observability/bootstrap.py` — modify: Register `RedactingSpanProcessor` ahead of active span exporters in `bootstrap_observability`.
- `src/observability/__init__.py` — modify: Export public redaction symbols (`RedactingSpanProcessor`, `redact_event_fields`, `redact_exception_record`, `redact_string`, `redact_value`, `is_sensitive_key`, `REDACTED_MASK`).
- `tests/test_redaction.py` — create: Unit tests covering deny-list masking, pattern scrubbing, PII masking, provider preservation, and each surface (spans, wide-event fields, exception records).

**Steps:**
1. Create `src/observability/redaction.py` with:
   - `REDACTED_MASK = "[REDACTED]"`
   - `SENSITIVE_EXACT_KEYS` set (e.g. `authorization`, `proxy-authorization`, `x-service-token`, `cookie`, `set-cookie`, `password`, `secret`, `token`, `otp`, etc.) and sensitive suffixes (`_token`, `_secret`, `_password`, `_api_key`, `_otp`, `_2fa`).
   - `PROTECTED_KEYS` set (e.g. `provider`, `provider_name`, `provider.name`, `broker`, `broker_name`, `broker.name`, `market_provider`) to guarantee provider dimensions are never redacted.
   - `is_sensitive_key(key: str) -> bool` function handling case-insensitivity and dotted/namespaced key hierarchy.
   - Compiled regex patterns for Bearer tokens (`(?i)\b(bearer\s+)([A-Za-z0-9_\-\.~+/]+=*)`), JWTs (`\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+`), broker session tokens (`\bws_sess_[A-Za-z0-9_\-]+\b` and session key/value patterns), OTP codes (`(?i)\b(?:otp(?:_code)?|totp|2fa(?:_code)?|two_factor_code)\s*[=:]\s*([0-9]{4,8}|[A-Za-z0-9]{6,8})\b`), URL query credential params (`(?i)([?&](?:api[_-]?key|api[_-]?token|access[_-]?token|token|secret|password)=)[^&\s'"]+`), and email addresses (`\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b`).
   - `redact_string(text: str) -> str` running pattern scrubs while preserving provider names.
   - `redact_value(key: str, value: Any) -> Any` handling recursion over dictionaries, lists, and primitives.
   - `redact_event_fields(fields: Mapping[str, Any]) -> dict[str, Any]` returning scrubbed dict without dropping records.
   - `redact_exception_record(record: Mapping[str, Any]) -> dict[str, Any]` applying field and pattern scrubbing specifically for exception payloads.
   - `redact_span(span: Any) -> None` mutating span `_attributes` and `_events` in-place prior to export.
   - `RedactingSpanProcessor(SpanProcessor)` calling `redact_span(span)` in `on_end(span: ReadableSpan)`.
2. Update `src/observability/bootstrap.py`:
   - Import `RedactingSpanProcessor` from `src.observability.redaction`.
   - In `bootstrap_observability`: when attaching span processors (either via custom `span_processor` or when `is_telemetry_enabled` is true), register `provider.add_span_processor(RedactingSpanProcessor())` immediately before the exporter processor.
   - Preserve kill-switch behavior when telemetry is disabled and `span_processor` is `None` (0 processors attached).
3. Update `src/observability/__init__.py`:
   - Re-export `RedactingSpanProcessor`, `redact_event_fields`, `redact_exception_record`, `redact_string`, `redact_value`, `is_sensitive_key`, and `REDACTED_MASK` in `__all__`.
4. Create `tests/test_redaction.py`:
   - Test sensitive key list masking (`authorization`, `x-service-token`, `password`, `cookie`, `otp`, `token`, etc.) replacing values with `[REDACTED]` while retaining keys/records.
   - Test pattern scrubbing for Bearer JWTs, broker session tokens (`ws_sess_...`), OTP codes, and URL query credentials inside string values and payloads.
   - Test PII masking replacing email addresses with `[REDACTED]`.
   - Test provider preservation asserting `provider="wealthsimple"`, `broker="wealthsimple"`, `provider="eodhd"`, etc., remain unmasked.
   - Test surface 1 (spans): Trace with `InMemorySpanExporter` verifying finished span attributes have sensitive keys and secret substrings redacted.
   - Test surface 2 (wide-event fields): Verify `redact_event_fields` and span event attributes (`span.add_event`) are redacted before export.
   - Test surface 3 (exception records): Verify `span.record_exception` scrubs `exception.message` and `exception.stacktrace`, and test `redact_exception_record`.
5. Run linting, type checks, and tests:
   - Run `./scripts/agent-test --gate0-only` (ruff check + ty check).
   - Run `./scripts/agent-test tests/test_redaction.py tests/test_observability.py`.

**Verification:**
- Sensitive key list: `test_sensitive_keys_masked` asserts keys on deny list are replaced with `[REDACTED]` and record keys are retained.
- Secret pattern scrubbing: `test_pattern_scrubbing_*` asserts bearer JWTs, broker tokens, and OTP codes leave no secret substring in payloads.
- PII masking: `test_pii_masking_email` asserts email addresses are replaced with `[REDACTED]`.
- Three surfaces: `test_surface_span_attributes_redacted_before_export`, `test_surface_wide_event_fields_redacted`, and `test_surface_exception_records_redacted` assert redaction runs before export on each respective surface.
- Provider preservation: `test_provider_names_preserved` asserts `provider` and `broker` attributes with values like `wealthsimple` and `eodhd` are untouched.
- Quality gates: `./scripts/agent-test --backend` passes with zero regressions; `./scripts/agent-test --gate0-only` passes clean.

**Risks / watch-outs:**
- False-positive redaction of internal telemetry dimensions: `provider` and `broker` must be explicitly protected against sensitive key checks (e.g. `broker_token` is sensitive, but `broker` / `provider` is not).
- Span immutability in OTel SDK: `_Span` stores attributes in `_attributes` and events in `_events`; `RedactingSpanProcessor.on_end` must mutate or replace entries in these SDK containers before downstream exporter processors (`BatchSpanProcessor` / `SimpleSpanProcessor`) read them.
- Multi-line stacktraces and exception messages: regexes must handle multi-line strings without truncation or backtracking issues.
