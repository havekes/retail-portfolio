# Backend Domains

The backend under `src/` is organized by business domain. Each domain follows the layered structure described in [Architecture Overview](./overview.md).

## Shared conventions

- **Models** live in `model.py` and inherit from `BaseModel` (`src/config/database.py`).
- **Schemas** live in `schema.py`. Repositories and services exchange schemas, never ORM models.
- **Public API types** live in `api_types.py` and are used for cross-domain calls.
- **Repositories** define abstract interfaces in `repository.py` and SQLAlchemy implementations in `repository_sqlalchemy.py`. Other implementations use `repository_<impl>.py`.
- **Services** contain orchestration and calculations; routers delegate to them.
- **Exceptions** inherit from `src.core.exception.EntityNotFoundError` or `AuthorizationError` for consistent HTTP mapping.

## account

`src/account` manages accounts, positions, portfolios, institutions, and account types.

### Models (source: `src/account/model.py`)

| Entity | Key fields | Notes |
|--------|------------|-------|
| `AccountModel` | `id: UUID`, `external_id: str`, `user_id: UUID`, `account_type_id`, `institution_id`, `currency`, `broker_display_name`, `net_deposits`, `deleted_at` | Unique on `(user_id, institution_id, external_id)`; soft-delete column exists |
| `AccountTypeModel` | `id`, `name`, `country`, `tax_advantaged` | Reference data seeded at startup |
| `InstitutionModel` | `id`, `name`, `country`, `integration_enabled` | `WEALTHSIMPLE` is the only integration institution currently |
| `PositionModel` | `id`, `account_id`, `security_id: UUID`, `quantity: Decimal(16,8)`, `average_cost`, `currency` | Unique on `(account_id, security_id)` |
| `PortfolioModel` | `id`, `user_id`, `name`, `deleted_at` | Unique on `(user_id, name)` |
| `PortfolioAccountModel` | `portfolio_id`, `account_id` | Many-to-many association |

### Public APIs (source: `src/account/api/account.py`, `position.py`, `institution.py`)

- `AccountApi`: `get_all`, `get_by_id`, `get_broker_id_by_id`, `rename`, `import_from_broker`
- `PositionApi`: `create(positions)` groups by account and delegates to repository `sync_by_account`
- `InstitutionApi`: returns integration-enabled institutions

### Services (source: `src/account/service/`)

- `AccountService`: get, ownership check, delete
- `PositionService`: calculates account totals/holdings, converts currency, syncs broker positions; depends on `MarketPricesApi`, `SecurityApi`, and integration APIs
- `PortfolioService`: CRUD + account membership validation

### Router (source: `src/account/router.py`)

- `/api/portfolios` — list, create, sync accounts, delete
- `/api/accounts` — list, rename, delete, totals, holdings per account, holdings per security, sync positions

### Business rules

- Account uniqueness is enforced by `(user_id, institution_id, external_id)`.
- Portfolio account membership is validated to belong to the portfolio owner.
- Position sync fully replaces positions for the account (`sync_by_account` deletes existing and re-inserts).
- Holdings calculations convert currency using `CurrencyConverter` and `stockholm.Money`.

## auth

`src/auth` handles users, login, JWT, email verification, and resource authorization.

### Models (source: `src/auth/model.py`)

| Entity | Key fields | Notes |
|--------|------------|-------|
| `UserModel` | `id: UUID`, `email`, `_password_hash`, `is_active`, `is_verified`, `last_login_at` | Password hashed with `argon2.PasswordHasher` |
| `VerificationTokenModel` | `id`, `user_id`, `token`, `expires_at`, `is_used` | Used for email verification |

### Service (source: `src/auth/service.py`, `api.py`)

- `EmailVerificationService`: creates/verifies/resends signed tokens using `itsdangerous.URLSafeTimedSerializer` with `email-verification` salt.
- `UserApi`: signup, login, JWT encode/decode (HS256, 24h), current-user extraction.
- `AuthorizationApi`: checks ownership of entities with `user_id`; returns 404 to avoid leaking existence.

### Router (source: `src/auth/router.py`)

- `/api/auth/signup`
- `/api/auth/login` — sets httponly `auth_token` cookie in production
- `/api/auth/logout`
- `/api/auth/verify-email`
- `/api/auth/resend-verification`
- `/api/auth/ws-ticket` — signed 30-second ticket for WebSocket auth

### Business rules

- Users must verify their email before logging in.
- Verification tokens for a user are invalidated when a new verification email is requested.
- Resource authorization returns HTTP 404 rather than 403 to hide resource existence.

## market

`src/market` manages securities, prices, watchlists, price alerts, security notes, documents, technical indicators, and AI analysis.

### Models (source: `src/market/model.py`)

| Entity | Key fields | Notes |
|--------|------------|-------|
| `SecurityModel` | `id: UUID`, `symbol`, `exchange`, `currency`, `name`, `isin` | Unique on `(symbol, exchange)` |
| `SecurityBrokerModel` | Maps broker symbol/exchange to `SecurityModel`; stores raw EODHD search results as JSON | Used when importing broker positions |
| `PriceModel` | OHLCV + `adjusted_close`, `date`, `security_id` | Unique on `(security_id, date)` |
| `WatchlistModel` | `id`, `user_id`, `name` | Many-to-many with securities |
| `PriceAlertModel` | `security_id`, `user_id`, `target_price`, `condition`, `triggered_at` | Per-user per-security alerts |
| `SecurityNoteModel` | `security_id`, `user_id`, `title`, `content` | AI can generate titles asynchronously |
| `SecurityDocumentModel` | `security_id`, `user_id`, `filename`, `file_path`, `file_size`, `file_type` | Uploads saved under `settings.upload_path` |
| `IndicatorPreferencesModel` | `security_id`, `user_id`, `indicators_json` | User-selected technical indicators per security |

### Public APIs (source: `src/market/api.py`)

- `SecurityApi`: `get_by_id`, `get_or_create_from_broker`, `create_or_get_from_search` (fetches full price history for new securities)
- `MarketPricesApi`: `get_latest_close`, `get_latest_price`

### Services (source: `src/market/service.py`, `ai_service.py`, `indicators.py`, `cache.py`)

- `MarketService`: `update_daily_prices_for_all_securities`, `fetch_and_save_price_history`
- `AIService`: calls an OpenAI-compatible endpoint configured by `ai_api_endpoint`/`ai_api_key`/`ai_api_model`. Methods: `analyze_fundamentals`, `summarize_notes`, `generate_note_title`, `analyze_portfolio_fit`
- `IndicatorCache`: Redis cache for technical indicator results
- `indicators.py`: SMA/EMA, weekly MAs, MACD, RSI

### External gateway (source: `src/market/gateway.py`, `eodhd.py`)

- `MarketGateway` ABC: `search()`, `get_price_on_date()`, `get_prices()`
- `EodhdGateway`: EODHD SDK + direct `requests.get` for search; exchange mapping (`CSE→CA`, `TSX→TO`, `NYSE/NASDAQ→US`)
- `EodhdPriceRepository` (`repository_eodhd.py`) implements read-through caching: fetches from DB, pulls missing data from EODHD, and persists it

### Router (source: `src/market/router.py`)

Prefix `/api/market`:

- `/prices/{id}/last-close`
- `/prices/{id}` (historical)
- `/search`
- `/security` (create/get)
- `/watchlists`
- `/securities/{id}/alerts`
- `/securities/{id}/notes`
- `/securities/{id}/documents`
- `/securities/{id}/indicators`
- `/securities/{id}/ai-fundamentals`, `/ai-summarize-notes`, `/ai-portfolio-debate`

### Business rules

- Security uniqueness by `(symbol, exchange)`.
- `EodhdPriceRepository` is the default `PriceRepository` in non-stub mode, so price reads transparently backfill from EODHD.
- AI note-title generation is enqueued as a Huey task after note creation/update.
- Documents are stored on disk at `settings.upload_path` with random filenames.

## integration

`src/integration` connects to broker APIs. Currently only Wealthsimple is implemented.

### Models and types

- `IntegrationUserModel` (`src/integration/repository_sqlalchemy.py`): `user_id`, `institution_id`, `external_user_id`, `display_name`, `last_used_at`. Unique on `(user_id, institution_id, external_user_id)`.
- `IntegrationUser` public API type in `src/integration/api_types.py`.
- Broker types in `src/integration/brokers/api_types.py`: `BrokerAccount`, `BrokerPosition`.

### Broker gateway (source: `src/integration/brokers/wealthsimple.py`)

- `WealthsimpleApiGateway` wraps `ws_api`.
- `BrokerApiGateway` ABC in `src/integration/brokers/__init__.py` defines `login`, `get_accounts`, `get_positions_by_account`.
- Sessions are cached in `keyring` using `PlaintextKeyring` (flagged with a TODO for production security).
- Maps Wealthsimple account types to `AccountTypeEnum` values.
- Skips the `sec-c-cad` cash position.

### APIs, services, tasks (source: `src/integration/api.py`, `service.py`, `task.py`)

- `IntegrationUserApi`: get by id / by user+institution
- `IntegrationAccountApi.sync_account_positions`: enqueues a Huey task
- `_sync_account_positions_task`: sends WebSocket sync events, fetches positions, resolves securities via `SecurityApi`, saves via `PositionApi`, updates `net_deposits`

### Router (source: `src/integration/router.py`)

- `/api/integration` — enabled institutions
- `/api/external` — broker users, login, accounts import, positions import

### Business rules

- Credentials are not persisted; only an `IntegrationUser` record and broker session tokens via keyring.
- Account import deduplicates existing accounts by `(user_id, external_id)` via `AccountApi.import_from_broker`.
- Broker symbols are mapped to market securities through EODHD search.

## ws

`src/ws` provides user-scoped WebSocket broadcast across backend/worker processes.

- `ConnectionManager` (`src/ws/manager.py`): tracks per-user connections, uses Redis Pub/Sub channel `ws_messages` for fan-out, falls back to local broadcast.
- `ws_router` (`src/ws/router.py`): `/api/ws` endpoint. Auth via signed ticket, cookie, or `sec-websocket-protocol`.

Messages use `WsEventType` (`ACCOUNT_SYNC_STARTED`, `ACCOUNT_SYNC_FINISHED`, `ACCOUNT_SYNC_FAILED`) defined in `src/ws/api_types.py`.

## core

Shared building blocks used by all domains.

- `src/core/exception.py`: `AuthorizationError`, `EntityNotFoundError`
- `src/core/email.py`: `EmailService` with Jinja2 templates under `src/templates/email/`
- `src/core/registry.py`: registers `EmailService`

## Cross-domain dependencies

| Consumer | Uses | Purpose |
|----------|------|---------|
| `account.PositionService` | `MarketPricesApi`, `SecurityApi` | Pricing and security resolution for totals/holdings |
| `account.PositionService` | `IntegrationAccountApi`, `IntegrationUserApi` | Broker position sync |
| `integration.task._sync_account_positions_task` | `SecurityApi`, `PositionApi`, `AccountRepository` | Background broker sync |
| `market.SecurityApi` | `MarketGateway`, `MarketPricesApi` | Broker security resolution and backfill |
| `market.AIService` | `SecurityRepository`, `PriceRepository`, `SecurityNoteRepository` | AI context gathering |

## Extension points

- Adding a new institution: add `InstitutionEnum` value, seed it in `seed.py`, and optionally implement a `BrokerApiGateway`.
- Adding a new market gateway: implement `MarketGateway` and register it in `src/config/services.py`.
- Adding a new domain: create a folder under `src/`, follow the model/schema/repository/api/service/router pattern, register services, and include the router in `src/main.py`.
