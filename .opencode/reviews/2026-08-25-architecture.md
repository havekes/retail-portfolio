---
date: 2026-08-25
verdict: needs-remediation
focus: auth package (backend src/auth + frontend auth flow), security
---

# Architecture Review 2026-08-25 — Auth Security

## Summary

First (baseline) architecture review, scoped to the auth package across backend and frontend. The auth domain is structurally faithful to the documented layering (router → api/service → repository, schemas everywhere, svcs factories) and ships genuinely strong primitives: argon2 password hashing, single-use email verification tokens, hashed single-use recovery codes, replay-protected WS tickets, and solid test coverage in `tests/routers/test_auth.py` (forged/expired MFA tokens, mfa-token scope rejection). However, three risks undermine the perimeter: the rate limiter's key function trusts unsigned JWT claims (full rate-limit bypass), the JWT signing key fails open (empty default, shared with the frontend server, reused for three token purposes), and the Huey dashboard is mounted with no authentication at all. Verdict: **needs-remediation** — ARCH-T01 and ARCH-T03 block upcoming broker-sync and valuation work that will put real financial data behind these endpoints.

## Findings

### 1. Rate limiter key function trusts unsigned JWT claims [severity: risk]

**Observation:** `user_or_ip_key_func` in `src/config/limiter.py` decodes the `auth_token` cookie / `Authorization` header with `jwt.decode(..., options={"verify_signature": False})` and uses `user_id`/`sub` as the rate-limit bucket key; on decode failure it falls back to the raw (attacker-controlled) token string. All sensitive endpoints use this limiter: `/auth/login` (10/min), `/auth/signup` (5/min), `/auth/2fa/login-verify` (10/min), `/auth/passkey/authenticate/*` (10/min) in `src/auth/router.py`.
**Impact:** An attacker attaches a garbage JWT with a fresh random `user_id` per request and gets a fresh bucket every time — rate limiting on credential brute force, 2FA brute force, and signup abuse is completely bypassed. This directly enables finding 4.
**Recommendation:** Key authenticated routes only on verified identity (or just use IP for unauthenticated auth endpoints). Ticketed as ARCH-T01.

### 2. JWT secret fails open and one key is reused for every token purpose [severity: risk]

**Observation:** `Settings.secret_key` defaults to `""` (`src/config/settings.py:11`), `src/.env.example` ships `SECRET_KEY=` empty, and nothing at startup validates it. The same key signs HS256 access/MFA JWTs (`src/auth/api.py`), itsdangerous email-verification tokens (`src/auth/service.py:73`), and itsdangerous WS tickets (`src/auth/router.py:200`, `src/ws/router.py`). The SvelteKit server holds the same secret as `JWT_SECRET` (`frontend/src/hooks.server.ts:3`) — a verify-only consumer that can therefore also mint valid tokens.
**Impact:** A misconfigured prod/staging deploy signs tokens with an empty HMAC key — trivially forgeable sessions with zero startup warning. Key reuse across three purposes plus a second service widens the blast radius of any single leak (frontend env var, logs, etc.).
**Recommendation:** Fail fast at startup when `secret_key` is empty/weak outside dev/test. Ticketed as ARCH-T02. The frontend holding the signing key is addressed in ARCH-T09.

### 3. Huey dashboard at `/worker/api` has no authentication [severity: risk]

**Observation:** `src/main.py` calls `init_huey_dashboard(app, ..., api_prefix="/worker/api")`; the mounted router (`huey_dashboard/api/router.py`) carries only a logging `Depends` — no `current_user`, no authorization. It exposes task list (`GET /worker/api/tasks/`), task detail (`GET /worker/api/tasks/{id}`), and a WebSocket updates channel.
**Impact:** Task metadata for broker sync (`src/integration/task.py`) — account ids, sync timing, error contents — is readable by anyone who can reach the backend port. As broker sync gains richer payloads, this leaks financial account data and operational internals. Auth-adjacent authorization boundary gap.
**Recommendation:** Gate the dashboard router behind an authenticated dependency (or bind to localhost / strip the mount outside dev). Ticketed as ARCH-T03. **Blocking** upcoming broker-sync enrichment.

### 4. 2FA verification has no per-user throttle [severity: risk]

**Observation:** `TotpService.verify_2fa_login` (`src/auth/service.py:261`) performs unbounded TOTP/recovery-code attempts per MFA token; the only brake is the router's 10/min limiter, which finding 1 bypasses. `valid_window=1` means ~3 valid 6-digit codes per 30s step; the 5-minute MFA token TTL is the only real bound.
**Impact:** With the limiter bypassed, online brute force of the 6-digit TOTP space becomes feasible within the token window; recovery codes (16 hex chars) are safer but also unthrottled. A financial app should not rely on a single bypassable control here.
**Recommendation:** Add a per-user attempt counter with lockout (e.g. Redis `INCR` + expiry keyed on user_id, independent of the HTTP limiter) in the service layer. Ticketed as ARCH-T04, depends_on ARCH-T01.

### 5. No password policy anywhere [severity: concern]

**Observation:** `SignupRequest` (`src/auth/api_types.py:13`) accepts `password: str` with no constraints; the frontend signup form (`frontend/src/lib/components/auth/signup-form.svelte`) only checks confirmation match. Nothing else validates length or complexity server-side.
**Impact:** 1-character passwords are valid; combined with a bypassable login rate limit (finding 1), weak passwords are the last line of defense and it is not enforced.
**Recommendation:** Enforce a minimum policy server-side in the schema (and mirror on the frontend for UX). Ticketed as ARCH-T05.

### 6. Login leaks account existence and credential validity [severity: concern]

**Observation:** `UserApi.login` (`src/auth/api.py:144`) returns before any argon2 verify when the email is unknown (timing side channel), and distinguishes 403 "Email not verified" from 401 "Invalid credentials" — confirming a correct email+password pair for unverified accounts. Signup returns a revealing 409 while `resend-verification` deliberately succeeds silently — an inconsistent anti-enumeration posture.
**Impact:** Attackers can enumerate registered emails by response timing and confirm password correctness against unverified accounts.
**Recommendation:** Perform a dummy hash verify for unknown users; keep the 403 path only if product explicitly wants it (document the trade-off), and align signup's response with the silent-success posture or accept-and-document 409. Ticketed as ARCH-T06.

### 7. No server-side session invalidation or auth audit trail [severity: concern]

**Observation:** Logout (`src/auth/router.py:145`, `frontend/src/routes/auth/logout/+page.server.ts`) only deletes the cookie; JWTs stay valid until their 24h `exp`. Tokens carry no `jti` and there is no denylist. `UserModel.last_login_at` is never written, and only failed logins are logged (`src/auth/router.py:86`) — successful logins, 2FA events, passkey registrations/deletions leave no audit record.
**Impact:** A stolen token cannot be revoked; there is no way to answer "when did this account last authenticate" — poor incident response posture for a finance app.
**Recommendation:** Add `jti` + Redis denylist checked in `get_current_user_from_token`, wire logout to revoke, persist `last_login_at`, and log security events (login success/failure, 2FA changes, passkey changes) with user_id. Ticketed as ARCH-T07.

### 8. Passkey user-verification policy mismatch and non-atomic challenge consumption [severity: debt]

**Observation:** `PasskeyService` requests `user_verification=PREFERRED` in both options calls but verifies with `require_user_verification=False` (`src/auth/service.py:365,480`) — the enforced policy is silently weaker than the advertised one. The authentication challenge is consumed via `redis.get` then `redis.delete` (`src/auth/service.py:464-470`) — two concurrent submissions of the same assertion can both pass before the delete lands. `verify_registration` also accepts `dict | str` credentials with broad `except` parsing (`src/auth/service.py:371-379`).
**Impact:** UV policy drift weakens phishing-resistance assumptions on authenticators that support UV; the GET→DELETE race permits assertion replay within a millisecond window. Both are small but compound as passkeys become a primary login path.
**Recommendation:** Decide and enforce one UV policy; consume challenges atomically (`GETDEL`). Ticketed as ARCH-T08.

### 9. Frontend route guard accepts any JWT scope and holds the signing key [severity: debt]

**Observation:** `frontend/src/hooks.server.ts` verifies signature and expiry with the shared `JWT_SECRET` but never checks `payload.scope` — an `mfa_pending` token in the `auth_token` cookie passes the route guard (backend APIs still reject it, so impact is limited to the SSR guard contract). The exp check (`payload.exp > Date.now()/1000`) duplicates what `jose.jwtVerify` already enforces.
**Impact:** Frontend/backend auth contract drift: the SSR layer treats a pre-2FA token as a session. Holding the signing key (finding 2) means a frontend env leak equals full session forgery.
**Recommendation:** Require `scope === 'access'` in the guard; longer term, stop sharing the signing key (backend introspection endpoint or asymmetric JWT). Ticketed as ARCH-T09.

### 10. Observations only (no ticket)

- **Dev-mode CORS reflection:** `src/main.py` uses `allow_origin_regex=r"https?://.*"` with `allow_credentials=True` whenever `environment != "prod"` — any non-prod deployment (e.g. `staging`, which tests show is a used value) reflects arbitrary origins with credentials. Backend cookies are also non-httponly/non-secure outside prod (`src/auth/router.py:97`). Acceptable for local dev; flag before any shared staging deploy.
- **TOTP secrets at rest are plaintext** (`auth_totp.secret`). Common practice, but a DB dump yields live 2FA seeds; consider encryption at rest if a secrets-management story emerges.
- **WS ticket replay guard fails open:** `_check_ticket_not_replayed` (`src/ws/router.py`) returns `True` (treats as new) when Redis errors — replay protection silently disabled during Redis outages.
- **`create_test_token.py`** mints 365-day access tokens from an interactive CLI — fine as a dev tool, but the default `scope="access"` and year-long TTL deserve a docstring warning.
- **Token in response body:** login/2FA/passkey responses return `access_token` in the JSON body in addition to the cookie — needed for Bearer clients, but it doubles the token's exposure surface (logs, browser devtools, frontend error paths).
- **Contract drift:** the frontend `AuthResponse` interface declares `token_type: string` (`frontend/src/lib/api/authService.ts:28`); the backend `AuthResponse` never sends it.

## What went well

- Layering matches the documented domain structure exactly: thin routers, repositories returning schemas only, factories in `__init__.py`, cross-domain access via `AuthorizationApi`.
- Strong primitives by default: argon2 for passwords *and* recovery codes, single-use recovery codes with `used_at`, single-use email tokens invalidated on resend, single-use WebAuthn challenges with TTL, WS tickets with 30s `max_age` + Redis replay protection.
- Anti-enumeration done right on `resend-verification` (silent success) — the pattern to align signup with.
- Security-relevant test coverage is unusually good: forged/expired MFA tokens, mfa-token scope rejection on authenticated endpoints, recovery-code reuse rejection, passkey challenge expiry (`tests/routers/test_auth.py`), plus dedicated rate-limit tests (`tests/routers/test_rate_limit.py`).

## Prior finding disposition

None — this is the first review; `.opencode/reviews/` was empty and no open `ARCH-T` tickets exist.
