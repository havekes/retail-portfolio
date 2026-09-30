## Plan

**Approach:**
Remove legacy client-side indicator calculation functions from finance utilities (`moving-average.ts`, `macd.ts`, `rsi.ts`, `bollinger-bands.ts`, `obv.ts`) while preserving configuration types, series value types, and default configurations required by the UI. Clean up `chart-preferences.ts` by removing `computeIndicatorData` and unused finance imports, and remove obsolete calculation unit tests in `moving-average.test.ts` and `page.svelte.test.ts`. This safely eliminates dead client-side computation code now that calculations are performed server-side via `indicatorsService.computeIndicators`.

**Files:**
- `frontend/src/lib/utils/finance/moving-average.ts` — modify: Remove calculation functions (`calculateSMA`, `calculateEMA`, `calculateTimeframeMA`, `calculateDayMA`, `calculateWeekMA`, `calculate50DayMA`, `calculate200DayMA`, `calculate50WeekMA`, `calculate200WeekMA`) and unused `Candle` import; retain `TimeframeMAUnit`, `TimeframeMAOptions`, `MAValue`, and `MASeries`.
- `frontend/src/lib/utils/finance/macd.ts` — modify: Remove `calculateMACD` and unused `Candle` and `calculateEMA` imports; retain `MACDSettings`, `MACDConfig`, `defaultMACDConfig`, `MACDValue`, and `MACDSeries`.
- `frontend/src/lib/utils/finance/rsi.ts` — modify: Remove `calculateRSI` and unused `Candle` import; retain `RSISettings`, `RsiConfig`, `defaultRSIConfig`, `RSIValue`, and `RSISeries`.
- `frontend/src/lib/utils/finance/bollinger-bands.ts` — modify: Remove `calculateBollingerBands` and unused `Candle` import; retain `BBSettings`, `BBConfig`, `defaultBBConfig`, `BBValue`, and `BBSeries`.
- `frontend/src/lib/utils/finance/obv.ts` — modify: Remove `calculateOBV` and unused `Candle` import; retain `OBVSettings`, `OBVConfig`, `defaultOBVConfig`, `OBVValue`, and `OBVSeries`.
- `frontend/src/lib/utils/finance/moving-average.test.ts` — delete: Remove obsolete unit test file for the deleted moving average calculation routines.
- `frontend/src/lib/chart-preferences.ts` — modify: Remove `computeIndicatorData`, `IndicatorComputeConfig`, `VolumeSeriesItem`, `IndicatorSeriesData`, and all imports from `moving-average`, `macd`, `rsi`, `bollinger-bands`, and `obv`.
- `frontend/src/routes/security/[security_id]/page.svelte.test.ts` — modify: Remove `computeIndicatorData` from `$lib/chart-preferences` import and remove obsolete `computeIndicatorData` test blocks (Day MA, Week MA, timestamp preservation, HA candle sensitivity, non-MA indicators).

**Steps:**
1. In `frontend/src/lib/utils/finance/moving-average.ts`, remove calculation functions (`calculateSMA`, `calculateEMA`, `calculateTimeframeMA`, `calculateDayMA`, `calculateWeekMA`, `calculate50DayMA`, `calculate200DayMA`, `calculate50WeekMA`, `calculate200WeekMA`) and the unused `Candle` import, retaining `TimeframeMAUnit`, `TimeframeMAOptions`, `MAValue`, and `MASeries`.
2. In `frontend/src/lib/utils/finance/macd.ts`, remove `calculateMACD` and unused imports (`calculateEMA` from `./moving-average`, `Candle` from `./candle`), retaining `MACDSettings`, `MACDConfig`, `defaultMACDConfig`, `MACDValue`, and `MACDSeries`.
3. In `frontend/src/lib/utils/finance/rsi.ts`, remove `calculateRSI` and the unused `Candle` import, retaining `RSISettings`, `RsiConfig`, `defaultRSIConfig`, `RSIValue`, and `RSISeries`.
4. In `frontend/src/lib/utils/finance/bollinger-bands.ts`, remove `calculateBollingerBands` and the unused `Candle` import, retaining `BBSettings`, `BBConfig`, `defaultBBConfig`, `BBValue`, and `BBSeries`.
5. In `frontend/src/lib/utils/finance/obv.ts`, remove `calculateOBV` and the unused `Candle` import, retaining `OBVSettings`, `OBVConfig`, `defaultOBVConfig`, `OBVValue`, and `OBVSeries`.
6. Delete the obsolete unit test file `frontend/src/lib/utils/finance/moving-average.test.ts`.
7. In `frontend/src/lib/chart-preferences.ts`, remove `computeIndicatorData`, `IndicatorComputeConfig`, `VolumeSeriesItem`, `IndicatorSeriesData`, and all imports from `$lib/utils/finance/(moving-average|macd|rsi|bollinger-bands|obv)`.
8. In `frontend/src/routes/security/[security_id]/page.svelte.test.ts`, remove `computeIndicatorData` from the `$lib/chart-preferences` import statement, and delete the 5 obsolete `describe` test suites testing `computeIndicatorData` (lines 411-744).
9. Run `npm --prefix frontend run check` to verify TypeScript and Svelte typing has zero errors.
10. Run `npm --prefix frontend run test:run` to verify all frontend unit tests pass, and `npm --prefix frontend run build` to verify the frontend production build passes.

**Verification:**
- Client-side calculation functions removed: run `rg "calculate(SMA|EMA|TimeframeMA|DayMA|WeekMA|50DayMA|200DayMA|50WeekMA|200WeekMA|MACD|RSI|BollingerBands|OBV)" frontend/src/` and verify 0 occurrences.
- Modal interface types and defaults preserved: inspect `frontend/src/lib/utils/finance/` to confirm `MACDConfig`, `defaultMACDConfig`, `RsiConfig`, `defaultRSIConfig`, `BBConfig`, `defaultBBConfig`, `OBVConfig`, and `defaultOBVConfig` remain exported.
- chart-preferences.ts cleanliness: run `rg "computeIndicatorData" frontend/src/` and verify 0 occurrences; run `rg "from '\$lib/utils/finance/(moving-average|macd|rsi|bollinger-bands|obv)'" frontend/src/lib/chart-preferences.ts` and verify 0 matches.
- Type check: run `npm --prefix frontend run check` and confirm exit code 0 with 0 errors.
- Unit tests: run `npm --prefix frontend run test:run` and confirm all test suites pass.
- Build check: run `npm --prefix frontend run build` and confirm exit code 0.

**Risks / watch-outs:**
- The route test file `frontend/src/routes/security/[security_id]/page.svelte.test.ts` contains square brackets in its path; ensure file commands avoid unquoted bracket globs.
- Ensure non-indicator finance utilities (`fibonacci.ts`, `elliott-wave.ts`, `holdings-metrics.ts`, `candle.ts`, `average-cost.ts`) and `INDICATOR_DEFAULTS` in `indicator-defaults.ts` are left completely untouched.
