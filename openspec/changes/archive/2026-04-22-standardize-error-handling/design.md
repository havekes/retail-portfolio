## Context

Currently, the application relies on catching a custom `ApiError` exception within client-side components to handle API failures. This pattern leads to repetitive, boilerplate try/catch blocks scattered throughout the UI, inconsistent error messaging, and tight coupling between the UI and API error structure. SvelteKit provides a robust, built-in mechanism for error handling using `error()` and `+error.svelte` boundaries, which we are not fully utilizing for API errors.

## Goals / Non-Goals

**Goals:**
- Centralize API error handling by catching `ApiError` in `+page.server.ts` loaders and throwing SvelteKit's `error()`.
- Provide a consistent, accessible user experience for fatal errors via global or nested `+error.svelte` boundaries.
- Simplify client-side `.svelte` and `.svelte.ts` components by removing explicit `ApiError` handling (where not already handled by form actions).

**Non-Goals:**
- Refactoring form submission errors (e.g., validation failures). These are being handled by the separate `sveltekit-form-actions-for-mutations` change using SvelteKit's `fail()` function.
- Changing the backend API error responses or the `ApiClient` implementation, apart from how the client consumes them.

## Decisions

1. **Throwing SvelteKit `error()` from Loaders**:
   Loaders in `+page.server.ts` that fetch data using the API client will wrap their calls in a try/catch. If an `ApiError` is caught, the loader will throw `error(err.status, err.message)`.
   *Rationale:* This delegates the rendering of the error to SvelteKit's routing system, ensuring that fatal errors (e.g., 404, 500, or unauthorized 401/403) are consistently displayed by the nearest `+error.svelte` boundary.

2. **Using `+error.svelte` for Error UI**:
   We will ensure a top-level `frontend/src/routes/+error.svelte` exists to catch and display these errors. It will read the status and message from `$page.error`.
   *Rationale:* This provides a unified error page design across the application.

3. **Removing Client-Side `ApiError` Handling**:
   Components that currently import `ApiError` and wrap API calls in try/catch (and aren't already being refactored to form actions) will be cleaned up. They will assume successful data fetching if they are rendered, as the loaders will have already handled any fatal errors.

## Risks / Trade-offs

- [Risk] Granular error context might be lost if we only map status and message.
  *Mitigation:* We will ensure the `message` extracted by `ApiClient` is descriptive enough for the user.
- [Risk] Some client-side components might rely on non-fatal `ApiError`s for inline UI updates (e.g., showing a toast instead of a full page error).
  *Mitigation:* If any such cases exist outside of form actions, we will carefully evaluate if they should use SvelteKit's `fail()` (via a server action) instead, or retain specific try/catch logic only where absolutely necessary for UX.