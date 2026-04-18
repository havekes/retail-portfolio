## Context

We want to show users their current holdings for a specific security when they are viewing that security's page. The data needs to be aggregated or queried efficiently to avoid N+1 problems on the client side (e.g., fetching all accounts, then fetching positions for each account). Following the user's feedback, the endpoint for this data should reside in the account domain since it is specifically related to the user's account holdings, rather than generic market data.

## Goals / Non-Goals

**Goals:**
- Provide a clear view of how many shares of the current security are held in each account.
- Fetch this data efficiently using a single new API endpoint in the account domain.
- Integrate smoothly into the existing `ActionsSidebar`.

**Non-Goals:**
- Adding functionality to trade or modify holdings directly from this sidebar.
- Displaying historical holdings data or performance metrics in this specific group.

## Decisions

1.  **New API Endpoint**: 
    - Create `GET /api/accounts/holdings/{security_id}`.
    - This will leverage the existing database schema to join `Account` and `Position` where `user_id = current_user.id` and `security_id = requested_security_id`.
    - Response format will be a list of objects containing `account_id`, `account_name`, and `quantity`.
2.  **Frontend Component (`HoldingsGroup.svelte`)**:
    - Create a new group in the actions sidebar that fetches from the new endpoint on mount/security change.
    - If the user holds 0 shares across all accounts, display a friendly empty state (e.g., "You don't hold any shares of this security.").
    - If holdings exist, list each account name and the corresponding quantity.

## Risks / Trade-offs

-   **Risk**: Database query efficiency. 
    -   *Mitigation*: Ensure the query in the account repository uses appropriate joins and indices (filtering by user ID and security ID).