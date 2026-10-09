## Plan

**Approach:**
Add API client methods to `MarketService` for the valuation persistence endpoints introduced in `F-VALUATION-T01`. Implement a lightweight-charts `ValuationBandPrimitive` plugin rendering a light-shaded horizontal price band across the chart canvas between lower and upper bounds at bottom z-order, controlled by a `show_valuation_band` user preference. In the right actions sidebar, add a "Fundamentals" group displaying the current valuation range (with "Not set" fallback), an edit button opening a validated input modal that saves to `PUT /market/securities/{security_id}/valuation`, and a show/hide toggle for the chart overlay.

**Files:**
- `frontend/src/lib/api/marketService.ts` — modify: Add `SecurityValuationRead` and `SecurityValuationWrite` interfaces, and add `getSecurityValuation` and `updateSecurityValuation` methods to `MarketService`.
- `frontend/src/lib/api/marketService.test.ts` — modify: Add unit tests for `getSecurityValuation` (200 success, 404 returning null) and `updateSecurityValuation` (PUT request payload).
- `frontend/src/lib/api/userPreferencesService.ts` — modify: Add `show_valuation_band?: boolean | null` to the `UserPreferences` interface.
- `src/account/api_types.py` — modify: Add `show_valuation_band: bool | None = None` to the backend `UserPreferences` schema.
- `frontend/src/lib/components/charts/plugins/valuation-band.ts` — create: Implement `ValuationBandPrimitive`, `ValuationBandPaneView`, and `ValuationBandRenderer` to render a light-shaded fill and dashed boundaries between lower and upper bounds at `'bottom'` z-order.
- `frontend/src/lib/components/charts/plugins/valuation-band.test.ts` — create: Unit tests for `ValuationBandPrimitive` verifying canvas drawing, geometry, visibility toggle, null coordinate handling, and detached cleanup.
- `frontend/src/lib/components/charts/security-chart.svelte` — modify: Accept `valuation` and `showValuationBand` props, attach `ValuationBandPrimitive` to `seriesInstance`, reactively sync props, clean up on unmount, and expose getter `getValuationBandPrimitive()`.
- `frontend/src/lib/components/charts/security-chart.test.ts` — modify: Test that `ValuationBandPrimitive` is attached to the chart series and updated with valuation props.
- `frontend/src/lib/components/actions-sidebar/fundamentals/valuation-modal.svelte` — create: Modal component for inputting lower and upper valuation prices, with positive-number and bounds validation, saving via `marketService.updateSecurityValuation`, and notifying callers via `onSaved`.
- `frontend/src/lib/components/actions-sidebar/fundamentals/valuation-modal.test.ts` — create: Unit tests for the modal checking initial value population, validation error messages, successful submission, and error handling.
- `frontend/src/lib/components/actions-sidebar/fundamentals/fundamentals-group.svelte` — create: Sidebar group with `GroupTitle` displaying valuation range formatted as currency (or "Not set"), Edit button opening `ValuationModal`, and a toggle for chart overlay visibility persisting via `userPreferencesService.patchPreferences`.
- `frontend/src/lib/components/actions-sidebar/fundamentals/fundamentals-group.test.ts` — create: Unit tests for `FundamentalsGroup` checking "Not set" state, formatted range display, opening edit modal, and toggling overlay visibility.
- `frontend/src/routes/security/[security_id]/+page.svelte` — modify: Integrate `FundamentalsGroup` into sidebar content, load valuation on security initialization, wire `valuation` and `showValuationBand` into `SecurityChart`, and handle preference persistence.
- `frontend/src/routes/security/[security_id]/page.svelte.test.ts` — modify: Test asserting `FundamentalsGroup` renders in sidebar and reflects valuation data.

**Steps:**
1. In `frontend/src/lib/api/marketService.ts`, define `SecurityValuationRead` (`id`, `user_id`, `security_id`, `lower_bound`, `upper_bound`, `created_at`, `updated_at`) and `SecurityValuationWrite` (`lower_bound`, `upper_bound`). Add `getSecurityValuation(securityId, token?)` handling 404 by returning `null`, and `updateSecurityValuation(securityId, payload, token?)` sending a `PUT` request to `/market/securities/${securityId}/valuation`.
2. In `frontend/src/lib/api/marketService.test.ts`, add unit tests covering `getSecurityValuation` returning data on HTTP 200, returning `null` on HTTP 404, and `updateSecurityValuation` dispatching `PUT` with body `{ lower_bound, upper_bound }`.
3. In `frontend/src/lib/api/userPreferencesService.ts` and `src/account/api_types.py`, add `show_valuation_band?: boolean | null` to `UserPreferences`.
4. In `frontend/src/lib/components/charts/plugins/valuation-band.ts`, implement `ValuationBandPrimitive` implementing `ISeriesPrimitive`. Create `ValuationBandPaneView` returning `zOrder(): 'bottom'` and `ValuationBandRenderer` using `BitmapCoordinatesRenderingScope` to fill a shaded rectangle (`rgba(59, 130, 246, 0.12)`) and draw boundary lines across the chart width between the `priceToCoordinate` coordinates for `lower` and `upper` bounds when `visible` is true.
5. In `frontend/src/lib/components/charts/plugins/valuation-band.test.ts`, write unit tests verifying: no drawing when valuation is unset or `visible` is false; shaded band rectangle geometry drawn when set and visible; null coordinate handling; reactive updates via `setValuation` and `setVisible`; and detachment cleanup.
6. In `frontend/src/lib/components/charts/security-chart.svelte`, add optional props `valuation?: { lower_bound: number; upper_bound: number } | null` and `showValuationBand?: boolean`. Attach `ValuationBandPrimitive` to `seriesInstance`, reactively sync valuation and visibility props, clean up on unmount, and export `getValuationBandPrimitive()`. Add test in `frontend/src/lib/components/charts/security-chart.test.ts`.
7. In `frontend/src/lib/components/actions-sidebar/fundamentals/valuation-modal.svelte`, implement the valuation modal using `@/components/ui/dialog`, input fields for lower bound and upper bound, client validation (positive values, `lower <= upper`), saving via `marketService.updateSecurityValuation`, displaying API errors, and calling `onSaved(newValuation)` on success.
8. In `frontend/src/lib/components/actions-sidebar/fundamentals/valuation-modal.test.ts`, write unit tests verifying modal open state, initial value population, input validation errors, and successful save callback.
9. In `frontend/src/lib/components/actions-sidebar/fundamentals/fundamentals-group.svelte`, implement the sidebar group with `GroupTitle` ("Fundamentals"), showing formatted valuation range (or "Not set"), Edit button opening `ValuationModal`, and a toggle switch/checkbox controlling `showValuationBand` that persists changes via `userPreferencesService.patchPreferences({ show_valuation_band })`.
10. In `frontend/src/lib/components/actions-sidebar/fundamentals/fundamentals-group.test.ts`, write unit tests verifying "Not set" text when unvalued, formatted range when valued, opening the edit modal, and toggling overlay visibility.
11. In `frontend/src/routes/security/[security_id]/+page.svelte`, integrate `FundamentalsGroup` into `<Sidebar.Content>` below `HoldingsGroup`. Add `loadValuation()` called during security data initialization, bind `valuation` and `showValuationBand` (initialized from `userPreferences?.show_valuation_band ?? true`), pass both to `SecurityChart`, and handle preference updates.
12. In `frontend/src/routes/security/[security_id]/page.svelte.test.ts`, add test asserting `FundamentalsGroup` is rendered in the security sidebar with valuation information.
13. Run full linting, type checks, and tests across backend and frontend to confirm build and all tests pass.

**Verification:**
- AC 1 (Fundamentals group in sidebar displaying range or "Not set" and Edit button):
  - Run `npm run test:run -- src/lib/components/actions-sidebar/fundamentals/fundamentals-group.test.ts` to verify "Fundamentals" group header, formatted valuation range (e.g. "$25.00 – $60.00"), fallback "Not set", and presence of the Edit button.
- AC 2 (Edit button opens modal to input lower/upper, saving via PUT):
  - Run `npm run test:run -- src/lib/components/actions-sidebar/fundamentals/valuation-modal.test.ts` and `npm run test:run -- src/lib/api/marketService.test.ts` to verify modal opens with inputs, validates bounds, sends `PUT /api/v1/market/securities/{security_id}/valuation`, and updates state on success.
- AC 3 (Chart displays light-shaded horizontal price band between lower and upper bounds):
  - Run `npm run test:run -- src/lib/components/charts/plugins/valuation-band.test.ts` to verify canvas draw calls render a shaded horizontal rectangle spanning the full chart width between lower and upper price coordinates at `'bottom'` zOrder.
- AC 4 (Toggle to show/hide valuation band overlay, persisted in preferences):
  - Run `npm run test:run -- src/lib/components/actions-sidebar/fundamentals/fundamentals-group.test.ts` to verify clicking the overlay toggle switches visibility and calls `userPreferencesService.patchPreferences({ show_valuation_band: ... })`.
- AC 5 (Unit tests for sidebar group, modal, and chart overlay pass):
  - Run `npm run test:run -- src/lib/components/actions-sidebar/fundamentals/ src/lib/components/charts/plugins/valuation-band.test.ts` and observe all tests pass.
- AC 6 (Build passes and relevant tests pass):
  - In `frontend/`, run `npm run check`, `npm run lint`, and `npm run test:run`. In backend, run `uv run ruff check` and `uv run pytest tests/routers/test_market.py`.

**Risks / watch-outs:**
- Bounds ordering: Users might enter lower > upper; modal client validation must check and present a clear inline error before calling the API.
- Off-screen prices: If current price range on the chart does not include the valuation range, `priceToCoordinate` returns values outside the viewport. The canvas renderer should handle off-screen y-coordinates safely without crashing or throwing.
- Concurrent soft navigation: In `+page.svelte`, ensuring `loadValuation` handles soft navigations between securities cleanly alongside `loadAlerts` and `loadHoldings`.
