## Why

Fetching data client-side using `+page.ts` paired with `export const ssr = false;` creates initial page load delays, shows client-side loading spinners unnecessarily, and can lead to network waterfalls. Server-to-server data fetching leverages the backend's proximity to the database and eliminates these issues, providing a faster, smoother initial render.

## What Changes

- Remove `export const ssr = false;` from SvelteKit route files, specifically `frontend/src/routes/accounts/[id]/+page.ts`.
- Migrate data fetching logic from universal load functions (`+page.ts`) to server load functions (`+page.server.ts`) in affected routes.
- Remove client-side loading spinners that are no longer needed for initial page loads.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
None.

## Impact

- SvelteKit routing and data loading layer (`frontend/src/routes/accounts/[id]`).
- Components relying on `data` prop from SvelteKit.
- Loading UI components (spinners, skeletons) currently used during client-side fetch on initial load.