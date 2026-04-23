## Why

Currently, API errors are inconsistently handled across the application, with many client-side components manually catching and processing `ApiError` exceptions. This leads to repetitive try/catch boilerplate and couples UI components with API error specifics. Standardizing on SvelteKit's built-in `error()` function and `+error.svelte` boundaries will ensure a consistent, robust error UI for fatal errors and reduce redundant code.

## What Changes

- Refactor `+page.server.ts` loaders to catch `ApiError` exceptions and throw SvelteKit's native `error(status, message)`.
- Create or update global `+error.svelte` boundaries to cleanly present error states to the user.
- Remove explicit `ApiError` imports and try/catch logic from client-side `.svelte` and `.svelte.ts` components, delegating error handling to SvelteKit's routing and server actions.

## Capabilities

### New Capabilities
None. This is a technical refactoring of existing error handling mechanisms.

### Modified Capabilities
None. The underlying business requirements and spec-level behavior remain unchanged.

## Impact

- `frontend/src/routes/+page.server.ts` and nested route loaders.
- `frontend/src/routes/+error.svelte` (creation or modification).
- Various `frontend/src/lib/components/**/*.svelte` and `.svelte.ts` files that currently import `ApiError` (excluding those handled by the separate form actions migration).