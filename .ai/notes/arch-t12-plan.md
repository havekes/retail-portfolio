## Plan

**Approach:**
In `market_data_fundamentals` (`src/market/data_router.py`), replace the three serial `await asyncio.to_thread(...)` calls in `fetch()` with `await asyncio.gather(...)` to issue `gateway.get_company_profile`, `gateway.get_key_metrics`, and `gateway.get_financial_ratios` concurrently in worker threads. If any provider or configuration error occurs, `asyncio.gather` propagates it immediately to the existing `(MarketDataProviderError, MarketDataConfigurationError)` handler which maps to 502/503 via `_map_market_error`, while `MarketDataNotFoundError` propagates to `EndpointResponseCache.cached_response` for negative caching and 404 translation.
Rejected alternative: `asyncio.TaskGroup` wraps exceptions in `ExceptionGroup`, which complicates exception matching without benefit over `asyncio.gather` for three homogeneous threads.

**Files:**
- `src/market/data_router.py` — modify: In `market_data_fundamentals`, update `fetch()` to await `asyncio.gather(...)` for `get_company_profile`, `get_key_metrics`, and `get_financial_ratios`.
- `tests/market/test_data_router.py` — modify: Add unit tests verifying concurrent execution using `threading.Barrier`, and partial-failure tests verifying that if one read fails (`MarketDataProviderError` / `MarketDataConfigurationError`) while others succeed, the route maps to 502/503 properly without provider name leak.

**Steps:**
1. In `src/market/data_router.py` within `market_data_fundamentals`:
   Replace the sequential awaits inside `fetch()` with a single `await asyncio.gather(...)`:
   ```python
   profile, key_metrics, ratios = await asyncio.gather(
       asyncio.to_thread(
           gateway.get_company_profile, normalized_symbol, exchange=exchange
       ),
       asyncio.to_thread(gateway.get_key_metrics, normalized_symbol, exchange=exchange),
       asyncio.to_thread(
           gateway.get_financial_ratios, normalized_symbol, exchange=exchange
       ),
   )
   ```
   Retain the existing `try...except (MarketDataProviderError, MarketDataConfigurationError)` block around `asyncio.gather` and ensure uncaught `MarketDataNotFoundError` propagates to `cache.cached_response` unchanged.
2. In `tests/market/test_data_router.py`:
   - Import `threading`.
   - Add test `test_fundamentals_reads_issued_concurrently(client, mock_gateway)`: configure `mock_gateway.get_company_profile`, `get_key_metrics`, and `get_financial_ratios` side effects to each call `barrier.wait()` on a `threading.Barrier(3, timeout=5.0)` before returning their default mock models. Verify response status is 200 (proving all 3 executed concurrently; sequential execution would deadlock/timeout on the barrier).
   - Add test `test_fundamentals_concurrent_partial_failure(client, mock_gateway, failing_method, side_effect, expected_status)`: parametrize across `["get_company_profile", "get_key_metrics", "get_financial_ratios"]` and `[(MarketDataProviderError("..."), 502), (MarketDataConfigurationError("..."), 503)]`. Set only `getattr(mock_gateway, failing_method).side_effect = side_effect` while leaving the other two methods returning default payloads. Assert response status matches `expected_status` (502 or 503) and generic error detail hides provider names and raw message.
3. Run verification suite:
   Execute `./scripts/agent-test tests/market/test_data_router.py` to confirm all tests pass, including formatting, ruff linting, and mypy type checks.

**Verification:**
- **AC1 (Concurrent reads):** Run `./scripts/agent-test tests/market/test_data_router.py -k test_fundamentals_reads_issued_concurrently` — verify passes within < 1s, confirming `threading.Barrier(3)` was satisfied concurrently across threads.
- **AC2 (Error mapping & negative caching):** Run `./scripts/agent-test tests/market/test_data_router.py -k "test_fundamentals_provider_failure or test_fundamentals_unknown_symbol or test_unknown_fundamentals_symbol_is_negative_cached"` — verify 502/503 mapping, 404 mapping, and Redis negative cache storage still pass identically.
- **AC3 (Concurrent partial failure coverage):** Run `./scripts/agent-test tests/market/test_data_router.py -k test_fundamentals_concurrent_partial_failure` — verify 6 combinations (3 methods × 2 error types) pass with 502/503 status and sanitized detail.
- **AC4 (Lint, types, targeted suite):** Run `./scripts/agent-test tests/market/test_data_router.py` — verify Gate 0 (ruff format check, ruff check, mypy) passes and all targeted tests pass.

**Risks / watch-outs:**
- Thread safety in test fixtures: using `threading.Barrier(3, timeout=5.0)` inside mock side effects relies on `asyncio.to_thread` executing on separate worker threads in Python's default thread pool. Setting a reasonable timeout (e.g. 5.0s) prevents pytest from hanging indefinitely if a regression makes calls sequential.
- Negative cache retention: `MarketDataNotFoundError` must not be intercepted by `fetch()`'s `except (MarketDataProviderError, MarketDataConfigurationError)` block, so `EndpointResponseCache.cached_response` can negative-cache the symbol under `_negative_ttl()`.
