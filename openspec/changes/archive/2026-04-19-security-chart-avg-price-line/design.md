## Context

The system currently stores user positions including `average_cost` in the `account_positions` table. The security detail page displays a price chart using `lightweight-charts` and a list of holdings in the sidebar. Users want to see their cost basis visualized on the chart to quickly assess performance.

## Goals / Non-Goals

**Goals:**
- Expose `average_cost` in the holdings API.
- Calculate a weighted average price across all user accounts for a specific security.
- Render a horizontal line at the average price on the security chart.
- Provide a UI toggle to show/hide the average price line.

**Non-Goals:**
- Historical cost basis tracking (only current average price).
- Support for multiple currencies within a single security's chart (security currency is used).

## Decisions

### Decision 1: Data Exposure
We will update the `AccountHoldingRead` schema and the corresponding repository method to include `average_cost`. This is the most efficient way as the data is already being fetched for the holdings sidebar.

### Decision 2: Aggregate Calculation
The frontend will perform the weighted average calculation: `Total Cost / Total Quantity`. This avoids adding complex aggregation logic to the backend for a UI-specific feature and allows for dynamic updates if the user's holdings data changes in the session.

### Decision 3: Chart Implementation
We will use the `createPriceLine` API of `lightweight-charts`. This is the standard way to add horizontal lines at a specific price level. We will add a method to `security-chart.svelte` to manage these lines.

## Risks / Trade-offs

- **[Risk] Performance** → **Mitigation**: The calculation is a simple linear aggregate of a few records, impact is negligible.
- **[Risk] UI Consistency** → **Mitigation**: The average price line will be styled similarly to price alerts but with a distinct color (e.g., orange or yellow) and a "Avg Price" label to avoid confusion.
