## Why

We need to provide users with a clear, detailed view of the specific holdings (securities) they own within an individual account, including the quantity, total value, and profit/loss. This allows users to track the performance and composition of specific accounts.

## What Changes

- Add a new "Account Details" page that displays a list of holdings for a specific account.
- Update the existing "Accounts List" page to make account names clickable, routing to the new Account Details page.
- On the Account Details page, make security names clickable, routing to the existing Security Details page.
- Display the following information for each holding on the Account Details page: Security Name, Shares Owned, Total Amount, Profit/Loss.

## Capabilities

### New Capabilities
- `account-holdings-view`: Displaying the detailed list of holdings, shares, value, and P/L for a specific account.

### Modified Capabilities

## Impact

- Frontend: New route/page for account details (e.g., `/accounts/[id]`), updates to the accounts list component to add links.
- Backend/API: Need to ensure the backend can provide holdings data specifically filtered by account ID, including shares owned, total amount, and profit/loss calculations.
