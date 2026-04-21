## Context

The frontend currently uses two different base classes for API interaction: `BaseClient` (in `src/lib/api`) and `BaseService` (in `src/lib/services`). Both use the native `fetch` API and handle authentication via `userStore`. This redundancy creates maintenance overhead and inconsistent error handling patterns (e.g., `BaseClient` handles 401s by clearing the user store, while `BaseService` does not).

## Goals / Non-Goals

**Goals:**
- Consolidate all data access into a single `src/lib/api` directory.
- Create a unified `ApiClient` base class.
- Standardize error handling and authentication token injection.
- Migrate all existing services and clients to the new pattern.

**Non-Goals:**
- Changing the backend API endpoints.
- Introducing a third-party library like Axios or TanStack Query (unless specifically requested, we'll stick to native `fetch`).
- Refactoring the Svelte store logic beyond how it interacts with the API layer.

## Decisions

### 1. Unified `ApiClient` Base Class
We will create a single `ApiClient` (or keep and enhance `BaseClient`) that all feature-specific clients will extend.
- **Rationale**: DRY principle. Centralizing logic for headers, interceptors, and error handling.
- **Alternatives**: Keeping both (rejected due to duplication) or using functional composition (rejected as the project already uses a class-based inheritance pattern for clients).

### 2. Standardized `ApiError`
A unified `ApiError` class will be used across all interactions.
- **Rationale**: Allows UI components to reliably catch and inspect error details (status code, message, etc.).

### 3. Automatic 401 Handling
The unified client will automatically clear the user session and potentially redirect to login when a 401 Unauthorized is received.
- **Rationale**: Ensures security and a consistent user experience when tokens expire.

## Risks / Trade-offs

- **[Risk] Migration Effort** → There are many services to update. 
  - **Mitigation**: Perform the migration incrementally, ensuring each migrated client is tested before moving to the next.
- **[Risk] Breaking Changes** → Consumers of `BaseService` might expect different error types than consumers of `BaseClient`.
  - **Mitigation**: Align both to the same `ApiError` interface and update consumers accordingly.
