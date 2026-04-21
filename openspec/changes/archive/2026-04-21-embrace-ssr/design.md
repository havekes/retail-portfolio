## Context

Currently, the application uses SvelteKit universal load functions (`+page.ts`) paired with `export const ssr = false;` for data fetching on certain routes (e.g., `frontend/src/routes/accounts/[id]/+page.ts`). This configuration forces SvelteKit to run the data fetching exclusively on the client-side. The result is an empty initial HTML payload, requiring the browser to download JavaScript, execute it, make API calls, and finally render the UI. This client-side rendering (CSR) approach causes noticeable loading delays, introduces unnecessary loading spinners during the initial data fetch, and can lead to network waterfalls.

## Goals / Non-Goals

**Goals:**
- Improve initial page load performance by fetching data on the server during the initial request.
- Eliminate client-side network waterfalls for initial page loads.
- Remove client-side loading states (spinners) that are currently used to mask the delay of initial data fetches.

**Non-Goals:**
- Changing the backend API structure or endpoints.
- Modifying the overall SvelteKit routing architecture.

## Decisions

1. **Migrate `+page.ts` to `+page.server.ts`**:
   - *Rationale*: Server load functions (`+page.server.ts`) run exclusively on the server, fetching data directly from the backend API before generating the HTML payload. This approach avoids client-side network requests for the initial load and leverages the backend's proximity to the database. SvelteKit automatically serializes this data and passes it to the client.
   - *Alternative Considered*: Keep `+page.ts` but remove `ssr = false`. This would run the load function on both the server (during SSR) and the client (during hydration or subsequent client-side navigations). However, moving strictly to `+page.server.ts` ensures data fetching logic is kept on the server, which is generally more secure and guarantees no redundant client-side fetching during initial load.

2. **Remove `export const ssr = false`**:
   - *Rationale*: Removing this line enables SvelteKit's default behavior, which includes Server-Side Rendering (SSR) for the affected routes.

3. **Remove unnecessary loading UI**:
   - *Rationale*: Since the initial HTML will be fully populated with data, loading UI components that were previously necessary to mask the delay of client-side fetching can be removed. 

## Risks / Trade-offs

- [Risk] Server load increases slightly due to SSR processing. → *Mitigation*: The application data fetching is lightweight, and backend API responses are typically fast, making the impact negligible.
- [Risk] Loss of fine-grained loading states during client-side navigation. → *Mitigation*: SvelteKit handles navigation loading states globally or via `await` blocks if needed. We will ensure the UX remains smooth during subsequent client-side navigations.