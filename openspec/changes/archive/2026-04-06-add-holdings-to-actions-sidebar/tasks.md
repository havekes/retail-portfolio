## 1. Backend: Holdings Endpoint

- [x] 1.1 Create schema in `src/account/schema.py` to represent the account name and quantity held (e.g., `AccountHoldingRead`).
- [x] 1.2 Add a repository method in `src/account/repository_sqlalchemy.py` (e.g., `get_holdings_by_security`) that joins accounts and positions for a given user and security ID.
- [x] 1.3 Add a service method in `src/account/service/position.py` (or a relevant service) to call the repository method.
- [x] 1.4 Add `GET /api/accounts/holdings/{security_id}` to `src/account/router.py` that uses the service method. Add appropriate unit tests to ensure isolation by user.

## 2. Frontend: Holdings Group Component

- [x] 2.1 Create `src/lib/components/actions-sidebar/holdings-group.svelte`.
- [x] 2.2 Implement data fetching in the component to call the new `/api/accounts/holdings/{security_id}` endpoint using the current `securityId`.
- [x] 2.3 Implement the UI to display a list of accounts and quantities, including a loading state and an empty state for no holdings.
- [x] 2.4 Add `HoldingsGroup` to `src/lib/components/actions-sidebar/actions-sidebar.svelte`, placing it logically (e.g., near the top of the sidebar below summary or alerts).