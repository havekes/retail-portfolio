## Plan

**Approach:**
Add split ratio calculation (`adjusted_close / close`) and candle transformation helpers to `frontend/src/lib/utils/finance/candle.ts`, and integrate them across `frontend/src/routes/security/[security_id]/+page.svelte` so mapped raw and Heikin-Ashi candles automatically scale OHLC across stock splits. In the backend (`src/market/router.py`), apply the same split scaling when mapping daily/weekly/monthly prices to indicator candles so server-computed indicators also operate on continuous adjusted prices.

**Files:**
- `frontend/src/lib/utils/finance/candle.ts` — modify: add `calculateSplitRatio`, `applySplitAdjustment`, and `mapPriceToCandle` functions scaling OHLC when `adjusted_close` is available and differs from `close`.
- `frontend/src/lib/utils/finance/candle.test.ts` — create: unit tests for `calculateSplitRatio`, `applySplitAdjustment`, `mapPriceToCandle`, and `convertToHeikinAshi` across normal, split (forward and reverse), missing `adjusted_close`, zero close, and intraday cases.
- `frontend/src/routes/security/[security_id]/+page.svelte` — modify: replace inline candle mapping in `changeTimeframe`, `handleLoadMoreData`, and initial `$effect` with `mapPriceToCandle` so chart and frontend indicators consume split-adjusted candles.
- `frontend/src/routes/security/[security_id]/page.svelte.test.ts` — modify: add tests asserting that candles and Heikin-Ashi candles passed to the chart and indicator payloads are scaled when `adjusted_close` differs from `close`.
- `src/market/router.py` — modify: scale `open`, `high`, `low`, and `close` by `adjusted_close / close` when constructing `IndicatorCandleSchema` from `prices_sorted` for indicator computation.
- `tests/market/test_indicator_compute_api.py` — modify: add a test verifying backend indicator computation scales input candles by split ratio when `adjusted_close != close`.

**Steps:**
1. In `frontend/src/lib/utils/finance/candle.ts`, implement `calculateSplitRatio(close: number, adjustedClose?: number | null): number` (returns 1 if `adjustedClose == null`, `close === 0`, or `adjustedClose === close`, else `adjustedClose / close`), `applySplitAdjustment<T>(candle: T): T`, and `mapPriceToCandle(price: MarketPrice, isIntraday?: boolean): Candle`.
2. In `frontend/src/lib/utils/finance/candle.test.ts`, write comprehensive unit tests for `calculateSplitRatio`, `applySplitAdjustment`, `mapPriceToCandle`, and `convertToHeikinAshi` checking forward split (0.5x), reverse split (2x), equality, undefined/null, zero price, and continuous Heikin-Ashi calculation across splits.
3. In `frontend/src/routes/security/[security_id]/+page.svelte`, import `mapPriceToCandle` from `@/utils/finance/candle` and use it in `changeTimeframe`, `handleLoadMoreData`, and initial `$effect` to map `priceResponse.items` / `items` into split-adjusted `mappedCandles`.
4. In `frontend/src/routes/security/[security_id]/page.svelte.test.ts`, add test cases with fixtures containing `adjusted_close != close` verifying that `mockChartProps.candles` receives split-adjusted OHLC values, Heikin-Ashi receives adjusted values, and rewind indicator payloads are adjusted.
5. In `src/market/router.py` (lines ~975-985), update the daily/weekly/monthly candle building loop to compute `split_ratio = float(p.adjusted_close / p.close)` when `p.adjusted_close is not None and p.close != 0 and p.adjusted_close != p.close` (else 1.0) and scale `open`, `high`, `low`, and `close` accordingly.
6. In `tests/market/test_indicator_compute_api.py`, add a test verifying that when historical prices have `adjusted_close != close`, the candles passed to `indicator_client.compute` have scaled OHLC prices matching the split ratio.

**Verification:**
- AC 1: `cd frontend && npm run test:run frontend/src/lib/utils/finance/candle.test.ts` passes, verifying `calculateSplitRatio` and `mapPriceToCandle` compute `adjusted_close / close` and scale open, high, low, close.
- AC 2: `cd frontend && npm run test:run frontend/src/routes/security` passes, confirming Candlestick and Heikin Ashi chart props receive continuous split-adjusted prices.
- AC 3: `uv run pytest tests/market/test_indicator_compute_api.py` and `cd frontend && npm run test:run` pass, verifying volume and server-side indicators compute on split-adjusted prices.
- AC 4: All newly added unit tests in `candle.test.ts`, `page.svelte.test.ts`, and `test_indicator_compute_api.py` pass.
- AC 5: Full verification suites pass:
  - Frontend: `npm run lint`, `npm run check`, `npm run test:run` in `frontend/`.
  - Backend: `uv run ruff check`, `uv run ruff format --check`, `uv run ty check`, `uv run pytest`.

**Risks / watch-outs:**
- Division by zero: if `close` is 0 or NaN, `calculateSplitRatio` must guard against division by zero and default to 1.
- Floating-point precision: when `adjusted_close` is applied to `close`, set `close` directly to `adjusted_close` to prevent precision drift from `close * (adjusted_close / close)`.
- Intraday data: intraday prices do not provide `adjusted_close`; ensure `mapPriceToCandle` falls back cleanly to unadjusted OHLC without errors.
