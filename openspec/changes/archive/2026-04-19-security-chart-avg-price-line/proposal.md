## Why

Users who own a security across one or more accounts want to see their average entry price directly on the price chart. This provides immediate visual context to the current price action relative to their cost basis, helping them quickly assess their profit/loss position without switching between different views.

## What Changes

- **Backend**: Enhance the holdings API to return the `average_cost` for each account holding.
- **Frontend Service**: Update the account service to include `average_cost` in the `AccountHoldingRead` type.
- **Frontend UI**: 
    - Calculate the weighted average price across all accounts for the current security.
    - Add a horizontal line to the `security-chart` component representing this average price.
    - Provide a toggle or configuration to show/hide this line.
    - Add a label to the line on the chart (e.g., "Avg Price: $123.45").

## Capabilities

### New Capabilities
- `avg-buying-price-line`: Displays a horizontal line on the security chart at the user's weighted average cost basis across all accounts.

### Modified Capabilities
- (None)

## Impact

- `src/account/schema.py`: Update `AccountHoldingRead` to include `average_cost`.
- `src/account/repository_sqlalchemy.py`: Update `get_holdings_by_security` to fetch `average_cost`.
- `src/account/service/position.py`: Update `get_holdings_by_security` to populate `average_cost`.
- `frontend/src/lib/services/accountService.ts`: Update type definition.
- `frontend/src/lib/components/charts/security-chart.svelte`: Add logic to render the average price line.
- `frontend/src/routes/security/[security_id]/+page.svelte`: Calculate average price and pass it to the chart.
