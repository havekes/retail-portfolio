# Plan: F-cache-security-search-T02

## Plan

**Approach:**
Implement `SecuritySearchCache` in `src/market/cache.py` using Redis with normalized query keys (`market:search:{normalized_query}`), configurable TTL defaulting to 30 days (2,592,000 seconds), Pydantic JSON serialization of `list[SecuritySearchResult]`, and resilient try/except fallback returning `None` on Redis errors. Register the cache factory in `src/market/__init__.py` and `src/config/services.py`, and inject it into `SecurityApi` and the market router search endpoints (`/search` and `/securities/search`) to eliminate redundant EODHD queries when results are already cached. Direct database caching of raw search results was rejected because search queries are ephemeral, cross-user strings that fit naturally into TTL-driven Redis keys without requiring database schema overhead.

**Files:**
- `src/market/cache.py` — modify: Implement `DEFAULT_SEARCH_CACHE_TTL = 2_592_000`, `SecuritySearchCache` class with normalized key generation, `get`, and `set` methods with resilient exception logging, and factory function `security_search_cache_factory`.
- `src/market/__init__.py` — modify: Export `SecuritySearchCache` and `security_search_cache_factory` and register the factory in `register_market_services`.
- `src/config/services.py` — modify: Import and register `SecuritySearchCache` with `security_search_cache_factory` in `register_market_stub_services`.
- `src/market/api.py` — modify: Update `SecurityApi.__init__` to accept `search_cache: SecuritySearchCache | None = None`; update `get_or_create_from_broker` to check `_search_cache.get(query)` before calling `_gateway.search(query)` and store results with `_search_cache.set(query, search_results)` on miss; update `security_api_factory` to resolve `SecuritySearchCache`.
- `src/market/router.py` — modify: Add `@market_router.get("/securities/search")` alias route to `market_search`; resolve `SecuritySearchCache` from container, check `cache.get(q)` before invoking `gateway.search(q)`, and populate cache via `cache.set(q, results)` on miss.
- `tests/market/test_security_search_cache.py` — create: Add unit tests for `SecuritySearchCache` verifying key normalization, TTL handling, get/set roundtrip of `SecuritySearchResult` models, Redis failure resilience (warning log and `None`/no-throw return), and corrupt JSON handling.
- `tests/market/test_security_api.py` — modify: Update `security_api` fixture to support `mock_search_cache`; add tests verifying `SecurityApi.get_or_create_from_broker` uses cached search results on broker mapping miss without calling `_gateway.search`, and populates `search_cache.set` on cache miss.
- `tests/market/test_search_router.py` — create: Add tests for market search endpoint verifying cache hit skips gateway search and cache miss invokes gateway search and populates `SecuritySearchCache`.

**Steps:**
1. In `src/market/cache.py`:
   - Define constant `DEFAULT_SEARCH_CACHE_TTL = 2_592_000` (30 days in seconds).
   - Implement `SecuritySearchCache`:
     - `__init__(self, redis_client: Redis | None = None, cache_ttl: int = DEFAULT_SEARCH_CACHE_TTL, redis_manager: RedisManager | None = None)` storing references and TTL.
     - Helper `_normalize_query(self, query: str) -> str`: strips whitespace, lowercases, and collapses internal whitespace.
     - Helper `_get_cache_key(self, query: str) -> str`: returns `f"market:search:{self._normalize_query(query)}"`.
     - Context manager `_get_client(self)`: yields `self._redis_client` if provided, else `self._redis_manager.client()`, else `default_redis_manager.client()`.
     - `async def get(self, query: str) -> list[SecuritySearchResult] | None`: returns `None` for empty query; fetches from Redis key; deserializes JSON array into `list[SecuritySearchResult]` via `SecuritySearchResult.model_validate(item)`; logs warning and returns `None` on any Redis or parsing exception.
     - `async def set(self, query: str, results: list[SecuritySearchResult], ttl: int | None = None) -> None`: serializes results via `[r.model_dump(mode="json") for r in results]`; writes to Redis key via `client.setex(cache_key, effective_ttl, payload)`; logs warning on any Redis exception without raising.
   - Implement `async def security_search_cache_factory() -> SecuritySearchCache` returning `SecuritySearchCache(redis_manager=redis_manager)`.
2. In `src/market/__init__.py`:
   - Import `SecuritySearchCache` and `security_search_cache_factory` from `src.market.cache`.
   - In `register_market_services`, call `registry.register_factory(SecuritySearchCache, security_search_cache_factory)`.
3. In `src/config/services.py`:
   - In `register_market_stub_services`, import `SecuritySearchCache` and `security_search_cache_factory` from `src.market.cache` and register with `registry.register_factory(SecuritySearchCache, security_search_cache_factory)`.
4. In `src/market/api.py`:
   - Import `SecuritySearchCache` from `src.market.cache`.
   - Update `SecurityApi.__init__` signature and fields: add parameter `search_cache: SecuritySearchCache | None = None` and attribute `self._search_cache = search_cache`.
   - In `SecurityApi.get_or_create_from_broker`: when `existing` is `None`, construct `query = f"{mapped_symbol}.{mapped_exchange}"`. If `self._search_cache` is set, call `search_results = await self._search_cache.get(query)`. If `search_results is None`, call `self._gateway.search(query=query)` and store with `await self._search_cache.set(query, search_results)`.
   - Update `security_api_factory` to resolve `search_cache=await container.aget(SecuritySearchCache)` and pass it to `SecurityApi`.
5. In `src/market/router.py`:
   - Import `SecuritySearchCache` from `src.market.cache`.
   - Add `@market_router.get("/securities/search")` decorator to `market_search` (alongside existing `@market_router.get("/search")`).
   - In `market_search`, resolve `cache = await services.aget(SecuritySearchCache)`. Check `cached_results = await cache.get(q)`. If not `None`, return `cached_results`. On miss, call `gateway.search(q)`, call `await cache.set(q, results)`, and return results.
6. In `tests/market/test_security_search_cache.py`:
   - Create unit tests for `SecuritySearchCache`:
     - Key normalization (case insensitivity, leading/trailing whitespace, multiple inner spaces).
     - Cache hit and miss with `list[SecuritySearchResult]`.
     - TTL verification (default 2,592,000s and custom TTL).
     - Redis error handling on `get` and `set` (verify warning logged, returns `None`, no unhandled exceptions).
     - Corrupted cache payload handling (returns `None`, logs warning).
7. In `tests/market/test_security_api.py`:
   - Update `security_api` fixture with `mock_search_cache` fixture (default `AsyncMock(spec=SecuritySearchCache)`).
   - Add test `test_get_or_create_from_broker_uses_search_cache_hit_when_no_broker_mapping`: mock `get_by_broker` returns `None`, `search_cache.get` returns `[search_result]`; verify `_gateway.search` is not called and security is created.
   - Add test `test_get_or_create_from_broker_populates_search_cache_on_cache_miss`: mock `get_by_broker` returns `None`, `search_cache.get` returns `None`; verify `_gateway.search` is called and `search_cache.set` is called with query and gateway results.
   - Update existing tests to verify compatibility when `search_cache` is provided or `None`.
8. In `tests/market/test_search_router.py`:
   - Add tests for `market_search` router endpoint testing both `/search` and `/securities/search`:
     - Cache hit: returns cached results, `gateway.search` not called.
     - Cache miss: queries `gateway.search`, calls `cache.set`, returns results.
9. Run verification commands to ensure linters, type checks, and test suite pass cleanly.

**Verification:**
- Unit tests for SecuritySearchCache: Run `uv run pytest tests/market/test_security_search_cache.py` to verify key normalization, get/set roundtrip, custom TTL, and Redis error resilience.
- SecurityApi search cache tests: Run `uv run pytest tests/market/test_security_api.py` to verify `SecurityApi.get_or_create_from_broker` uses search cache on hit and sets search cache on miss.
- Market search router tests: Run `uv run pytest tests/market/test_search_router.py` to verify `GET /api/v1/market/securities/search` and `GET /api/v1/market/search` check cache before gateway and cache on miss.
- Quality check: Run `uv run ruff check .` and `uv run ty check` to verify zero lint or type errors.

**Risks / watch-outs:**
- Query normalization consistency: `_normalize_query` must strip leading/trailing whitespace and collapse multiple spaces into single spaces before lowercasing so equivalent queries (`" AAPL "` and `"aapl"`) match the same cache key.
- Redis client lifecycle: Using `redis_manager` in production and stub factory prevents unmanaged connection pool proliferation across async requests while allowing clean injection of mock `Redis` client in tests.
- Non-breaking parameter in `SecurityApi`: `search_cache` parameter in `SecurityApi.__init__` defaults to `None` so any existing direct callers or test fixtures that do not supply `search_cache` continue to function without error.
