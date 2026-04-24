## 1. Global Error Boundary

- [x] 1.1 Create or update `frontend/src/routes/+error.svelte` to present a unified error UI displaying `$page.status` and `$page.error.message`.

## 2. Server Loader Refactoring

- [x] 2.1 Update `frontend/src/routes/accounts/[id]/+page.server.ts` loader to catch `ApiError` and throw SvelteKit's `error(err.status, err.message)`.
- [x] 2.2 Search for all other `+page.server.ts` or `+layout.server.ts` loaders that use the API client and update them to catch `ApiError` and throw SvelteKit's `error()`.

## 3. Client Component Cleanup

- [x] 3.1 Search for `ApiError` usage in all `.svelte` and `.svelte.ts` components across `frontend/src/`.
- [x] 3.2 For components not affected by the form actions migration (e.g. data viewing components), remove redundant `ApiError` try/catch blocks and assume successful data fetching.