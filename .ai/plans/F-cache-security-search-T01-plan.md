# Plan: F-cache-security-search-T01

## Plan

**Approach:**
Add a composite index on `(institution_id, broker_symbol, broker_exchange)` to `market_securities_broker` via an Alembic migration and update `SecurityBrokerModel`'s `__table_args__`. Implement `get_by_broker` on `SecurityBrokerRepository` and its SQLAlchemy implementation, and update `SecurityApi.get_or_create_from_broker` to query for an existing mapping before invoking external gateway search or price fetching. A direct query on `market_securities` was rejected because broker-specific ticker codes and exchange codes frequently diverge from EODHD's canonical tickers and exchanges, necessitating lookup through `market_securities_broker`.

**Files:**
- `src/market/model.py` — modify: Add composite index `Index("ix_market_securities_broker_institution_symbol_exchange", "institution_id", "broker_symbol", "broker_exchange")` in `SecurityBrokerModel.__table_args__`.
- `migrations/versions/<hash>_add_composite_index_to_market_securities_broker.py` — create: Alembic revision adding composite index on `(institution_id, broker_symbol, broker_exchange)` to table `market_securities_broker`, with `down_revision = '5223c29cb058'`.
- `src/market/repository.py` — modify: Import `InstitutionEnum` from `src.core.enum` and declare abstract method `get_by_broker(self, institution_id: InstitutionEnum, broker_symbol: str, broker_exchange: str) -> SecurityBrokerSchema | None` in `SecurityBrokerRepository`.
- `src/market/repository_sqlalchemy.py` — modify: Import `InstitutionEnum` from `src.core.enum`, implement `get_by_broker` in `SqlAlchemySecurityBrokerRepository`, and refactor `get_or_create` to reuse `get_by_broker`.
- `src/market/api.py` — modify: In `SecurityApi.get_or_create_from_broker`, query `_security_broker_repository.get_by_broker(...)` first; if present, load security via `_security_repository.get_by_id_or_fail(mapping.security_id)` and return `Security.model_validate(security)` without calling `_gateway.search` or `_market_prices_api`.
- `tests/repositories/test_repository_sqlalchemy.py` — modify: Add integration test `test_sqlalchemy_security_broker_repository_get_by_broker` verifying `get_by_broker` returns `None` when absent and matching `SecurityBrokerSchema` when present.
- `tests/market/test_security_api.py` — create: Add unit tests for `SecurityApi.get_or_create_from_broker` verifying cached DB mapping returns early without calling gateway or prices API, and cache miss performs gateway search and mapping creation.

**Steps:**
1. In `src/market/model.py`, add `__table_args__ = (Index("ix_market_securities_broker_institution_symbol_exchange", "institution_id", "broker_symbol", "broker_exchange"),)` to `SecurityBrokerModel`.
2. Create Alembic migration `migrations/versions/<hash>_add_composite_index_to_market_securities_broker.py` with `down_revision = '5223c29cb058'`. In `upgrade()`, call `op.create_index('ix_market_securities_broker_institution_symbol_exchange', 'market_securities_broker', ['institution_id', 'broker_symbol', 'broker_exchange'], unique=False)`. In `downgrade()`, call `op.drop_index('ix_market_securities_broker_institution_symbol_exchange', table_name='market_securities_broker')`.
3. In `src/market/repository.py`, import `InstitutionEnum` from `src.core.enum` and add abstract method `get_by_broker(self, institution_id: InstitutionEnum, broker_symbol: str, broker_exchange: str) -> SecurityBrokerSchema | None` to `SecurityBrokerRepository`.
4. In `src/market/repository_sqlalchemy.py`, import `InstitutionEnum` from `src.core.enum` and implement `get_by_broker` on `SqlAlchemySecurityBrokerRepository` using `select(SecurityBrokerModel).where(SecurityBrokerModel.institution_id == inst_val).where(SecurityBrokerModel.broker_symbol == broker_symbol).where(SecurityBrokerModel.broker_exchange == broker_exchange).limit(1)`. Update `get_or_create` to reuse `get_by_broker`.
5. In `src/market/api.py`, update `SecurityApi.get_or_create_from_broker` to first call `await self._security_broker_repository.get_by_broker(institution_id=institution_id, broker_symbol=broker_symbol, broker_exchange=broker_exchange)`. If found, call `await self._security_repository.get_by_id_or_fail(existing.security_id)` and return `Security.model_validate(security)`. If not found, execute existing gateway search and broker creation.
6. In `tests/repositories/test_repository_sqlalchemy.py`, add `test_sqlalchemy_security_broker_repository_get_by_broker(db_session: AsyncSession)` testing `get_by_broker` when mapping does not exist (returns `None`), after mapping is created (returns `SecurityBrokerSchema`), and with mismatched query fields (returns `None`).
7. In `tests/market/test_security_api.py`, add unit tests:
   - `test_get_or_create_from_broker_returns_cached_mapping_without_search`: mock `get_by_broker` returning a schema, verify security is returned and `_gateway.search` / `_market_prices_api.get_latest_close` are never called.
   - `test_get_or_create_from_broker_performs_search_when_no_mapping_found`: mock `get_by_broker` returning `None`, verify `_gateway.search`, `_security_repository.get_or_create`, and `_security_broker_repository.get_or_create` are invoked.
8. Run verification commands to ensure test suite, autogenerate drift check, and linters pass cleanly.

**Verification:**
- Migration & autogenerate drift: Run `uv run pytest tests/test_migrations_autogenerate.py` to verify the migration and model index match with zero schema drift.
- Repository `get_by_broker`: Run `uv run pytest tests/repositories/test_repository_sqlalchemy.py -k test_sqlalchemy_security_broker_repository_get_by_broker` to verify database lookup returns matching schema or None.
- SecurityApi cache hit: Run `uv run pytest tests/market/test_security_api.py -k test_get_or_create_from_broker_returns_cached_mapping_without_search` to verify `_gateway.search` and `_market_prices_api.get_latest_close` are not called on cache hit.
- SecurityApi cache miss: Run `uv run pytest tests/market/test_security_api.py -k test_get_or_create_from_broker_performs_search_when_no_mapping_found` to verify external search and persistence occur when no broker mapping exists.
- Regression & Quality check: Run `uv run pytest tests/services/test_csv_account_service.py`, `uv run ruff check .`, and `uv run pyright` to verify no regressions or type errors.

**Risks / watch-outs:**
- Migration head alignment: Revision must set `down_revision = '5223c29cb058'` so Alembic maintains a single linear migration history.
- Schema drift: Index name in `SecurityBrokerModel.__table_args__` must exactly match the name in `op.create_index(...)` (`ix_market_securities_broker_institution_symbol_exchange`) to prevent `test_migrations_autogenerate.py` failures.
- `institution_id` type: Handle both `InstitutionEnum` and `int` safely via `.value` extraction when constructing the SQL query in `SqlAlchemySecurityBrokerRepository`.
