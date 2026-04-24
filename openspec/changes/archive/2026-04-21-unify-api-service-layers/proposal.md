## Why

The current frontend architecture has redundant data access patterns with both `src/lib/api` (using `BaseClient`) and `src/lib/services` (using `BaseService`). This duplication leads to inconsistent error handling, token management, and developer confusion regarding where to implement new API interactions.

## What Changes

- **Merge Layers**: Consolidate all data fetching logic into `src/lib/api`.
- **Standardize Client**: Replace `BaseClient` and `BaseService` with a single, robust `ApiClient` class that handles HTTP methods, auth headers, and unified error parsing.
- **Refactor Consumers**: Update all Svelte components and stores to use the unified API clients.
- **Remove Redundancy**: Delete the `src/lib/services` directory after migration.
- **Unified Error Handling**: Ensure all API calls use a consistent `ApiError` class with standardized 401 (Unauthorized) handling.

## Capabilities

### New Capabilities
- `unified-api-client`: A single source of truth for all backend communication, providing consistent patterns for GET, POST, PATCH, and DELETE requests.

### Modified Capabilities
- `account-management`: Update account-related actions to use the unified API client.
- `market-data`: Update market data fetching to use the unified API client.
- `auth-service`: Migrate authentication logic to the unified API layer.

## Impact

- **Breaking Changes**: Removal of `BaseService` and `BaseClient` will require updating all files that extend these classes.
- **File System**: `src/lib/services/` will be removed. All files will be consolidated under `src/lib/api/`.
- **Consistency**: Improved reliability of session management and error reporting across the entire application.
