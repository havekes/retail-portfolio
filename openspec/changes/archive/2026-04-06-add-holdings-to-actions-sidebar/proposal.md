## Why

Currently, when viewing a specific security on the security page, users cannot easily see if they already own this security or how many shares they hold across their various accounts. To answer this question, they have to navigate away from the security page or manually check their dashboard/portfolios. A "Holdings" group in the right sidebar (`ActionsSidebar`) would provide immediate context on their current position in the viewed security.

## What Changes

1.  **Backend API**: Create a new endpoint `/api/accounts/holdings/{security_id}` (or similar) that returns a list of accounts and the quantity/shares of the specific security held in each account by the current user.
2.  **Right Sidebar Enhancement**: Add a new `HoldingsGroup` component to the `ActionsSidebar` on the security page. This group will display a list of the user's accounts that hold the security, along with the quantity held in each.

## Capabilities

### New Capabilities
- `security-holdings-display`: Displaying user's holdings for a specific security across all their accounts directly in the security context.

### Modified Capabilities
- None

## Impact

-   **Frontend**:
    -   `src/lib/components/actions-sidebar/holdings-group.svelte`: New component to display the holdings.
    -   `src/lib/components/actions-sidebar/actions-sidebar.svelte`: Include the new `HoldingsGroup`.
-   **API**:
    -   New endpoint: `GET /api/accounts/holdings/{security_id}` (or similar RESTful route).
    -   Updates to backend repository and service layers to efficiently query positions by security ID across all user accounts.