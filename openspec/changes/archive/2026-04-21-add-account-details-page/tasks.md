## 1. Backend Updates

- [x] 1.1 Implement logic in the backend to calculate account-specific holdings (aggregating positions by security, computing shares owned, total amount, and profit/loss).
- [x] 1.2 Create or update an API endpoint (e.g., `GET /api/accounts/{account_id}/holdings` or similar) to serve the account holdings data.
- [x] 1.3 Write backend tests to verify the accuracy of the account-specific holdings calculations.

## 2. Frontend Routing & Accounts List
 
- [x] 2.1 Update the Accounts list component (e.g., on the main dashboard) to make account names clickable, routing to `/accounts/[id]`.
- [x] 2.2 Create the new dynamic route file `src/routes/accounts/[id]/+page.svelte`.
- [x] 2.3 Create the data loader file `src/routes/accounts/[id]/+page.ts` (or `+page.server.ts`) to fetch the holdings data for the specified account ID.
 
## 3. Frontend Account Details Page
 
- [x] 3.1 Implement the layout for the Account Details page, displaying the account name and basic info.
- [x] 3.2 Add a table or list component to display the holdings, including columns for Security Name, Shares Owned, Total Amount, and Profit/Loss.
- [x] 3.3 Ensure the security names in the holdings list are clickable links that navigate to the existing Security Details page (e.g., `/security/[symbol]`).
