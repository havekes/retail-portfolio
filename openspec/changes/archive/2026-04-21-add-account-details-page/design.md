## Context

We currently have an "Accounts" view that lists user accounts, but there is no dedicated page to view the specific holdings of an individual account. Users need to click into an account and see a detailed breakdown of the securities held within it, including the shares owned, total amount (value), and profit/loss.

## Goals / Non-Goals

**Goals:**
- Implement a dedicated Account Details page that displays a list of all security holdings for that account.
- Make the account names in the Accounts list clickable, navigating to the new Account Details page.
- Ensure each security in the Account Details holdings list is clickable, navigating to the existing Security Details page.
- Compute and display `shares owned`, `total amount` (market value), and `profit/loss` for each holding.

**Non-Goals:**
- Creating new transaction/import flows.
- Modifying how the portfolio values are fundamentally calculated (we will reuse existing logic, scoped to an account).

## Decisions

- **Frontend Route**: Introduce a new dynamic route `src/routes/accounts/[id]/+page.svelte` (assuming SvelteKit is used based on typical project structure).
- **Backend API Update**: Update the backend account API (e.g. `src/account/api/account.py`) to expose a `GET /api/accounts/{account_id}/holdings` endpoint, or extend an existing endpoint to return holdings data grouped by account.
- **Holdings Calculation**: The backend will aggregate positions by security for the specific `account_id`, multiply by the current market price to get `total amount`, and calculate `profit/loss` based on the cost basis of the positions within that account.
- **UI Components**: Reuse existing table/list components from the application's design system to render the holdings list.

## Risks / Trade-offs

- **Risk**: Performance issues if an account has a massive number of positions.
  - **Mitigation**: Holdings are typically aggregated by security, which reduces the number of items to display. If needed, pagination can be introduced later.
- **Risk**: Missing current market prices for some securities.
  - **Mitigation**: Fallback to the latest available price or display a warning if the price is stale.
