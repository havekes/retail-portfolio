## 1. Backend Data Exposure

- [x] 1.1 Update `AccountHoldingRead` in `src/account/schema.py` to include `average_cost: float | None`.
- [x] 1.2 Update `get_holdings_by_security` in `src/account/repository_sqlalchemy.py` to select `average_cost`.
- [x] 1.3 Update `get_holdings_by_security` in `src/account/service/position.py` to populate `average_cost` in the response.

## 2. Frontend Service & Types

- [x] 2.1 Update `AccountHoldingRead` type in `frontend/src/lib/services/accountService.ts` to include `average_cost`.

## 3. Chart Implementation

- [x] 3.1 Add logic to `frontend/src/lib/components/charts/security-chart.svelte` to manage an average price line.
- [x] 3.2 Implement `createPriceLine` from `lightweight-charts` within the chart component to render the horizontal line.

## 4. Integration & UI

- [x] 4.1 Update `frontend/src/routes/security/[security_id]/+page.svelte` to calculate the weighted average cost from fetched holdings.
- [x] 4.2 Add a toggle to the Indicators menu in the sidebar to show/hide the average price line.
- [x] 4.3 Wire the calculated average price and toggle state to the chart component.
- [x] 4.4 Verify the line appears at the correct price and updates correctly when holdings or visibility change.
