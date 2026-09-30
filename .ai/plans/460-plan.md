## Plan

**Approach:** Stop awaiting holdings pagination in the server load — it already exists client-to-server in `HoldingsService.load()` (`frontend/src/lib/components/holdings/holdingsService.svelte.ts:30`), so a SvelteKit streamed promise would just duplicate the sequential-waterfall problem (rejected alternative: server-streamed promise; it can't cleanly convert a mid-stream 401 into the login redirect and the client fetch path already implements everything). The server load awaits only the cheap preferences request and returns the preferences-derived keys; `+page.svelte` instantiates its own `HoldingsService`, seeds `groupBy` from `data.group_mode`, and calls `service.load()` on mount, driving the existing `isLoading` skeletons in `holdings-table.svelte` and `app-header.svelte`. The 401/error seam lives in one new shared helper `frontend/src/lib/api/async-data.ts` that T02/T03 reuse.

**Reusable async error/401 seam (contract for T02/T03):** `frontend/src/lib/api/async-data.ts` exports:

```ts
import { goto } from '$app/navigation';
import { ApiError } from '$lib/api/apiClient';

/**
 * Handle an error caught from an async (post-navigation) data load.
 * Returns true if the error was handled (i.e. a 401 redirected to login).
 * Contract: ApiError with status 401 -> goto('/auth/login?clear_session=true');
 * hooks.server.ts clears the surviving token there. The httpOnly auth_token
 * cookie is NOT deleted client-side. Any other error returns false; the
 * caller surfaces err.message in its own in-page error alert.
 */
export async function redirectOn401(err: unknown): Promise<boolean>
```

Clients use it as `catch (err) { if (await redirectOn401(err)) return; this.errorMessage = ... }`. Server-side 401 handling (deleteAuthCookie + `throw redirect(...)`) stays a **separate, server-only** pattern as it exists today unless a ticket's load still awaits the 401-prone request.

**Files:**
- `frontend/src/lib/api/async-data.ts` — create: `redirectOn401(err)` seam above.
- `frontend/src/lib/api/async-data.test.ts` — create: unit test for the seam (mock `$app/navigation`, ApiError 401 / non-401 / plain Error cases). All mocked.
- `frontend/src/routes/holdings/+page.server.ts` — modify: delete `loadAllHoldings`, `PAGE_SIZE`/`MAX_PAGES`, and the try/catch ApiError unwrapping; `load` awaits only `getUserPreferencesService(fetch).getPreferences(token)` with the unchanged non-fatal fallback, and returns `{ holdings_table_config, group_mode, elliott_waves }`. Remove `UserHolding` and `deleteAuthCookie` imports. Keep the SSR-token comment (`getPreferences(token)` still needs the explicit token server-side).
- `frontend/src/routes/holdings/+page.svelte` — modify:
  - Remove `service.rows = data.holdings;` seeding; keep `const service = new HoldingsService();` and `service.setGroupBy(data.group_mode);`
  - Trigger the async load on mount inside a guarded `$effect` (`$effect(() => { service.load(); })` or an equivalent once-guard) — `$effect` does not run during SSR, so no server-side relative-URL fetch leak; this is mount-time orchestration, not state syncing (frontend/AGENTS.md Gotcha 2 exception is deliberate here; Gotcha 6 stays respected because the sequential waterfall lives in the service).
  - Pass `isLoading={service.isLoading}` to `PageHeader` so title skeletons show before data lands; `HoldingsTable` already receives `service.isLoading` and renders skeleton rows (~line 500).
  - Nothing else changes: `currencyTotals` derive from `service.rows` (fill in as data arrives), `errorMessage = persistError ?? service.errorMessage` already renders the `holdings-error` alert.
- `frontend/src/routes/holdings/page.server.test.ts` — modify: drop holdings-pagination, holdings-401-redirect, non-401-Kit-error, and error-item assertions; keep/adjust: preferences success mapping, defaults-fallback-when-prefs-fail (plus a guard that `getUserHoldings` is **never** called by the server load), and that the returned object contains only the three preference keys.
- `frontend/src/routes/holdings/page.svelte.test.ts` — modify: mock `$lib/api/accountService` (per-page responses for the pagination path), `$lib/api/userPreferencesService`, and `$app/navigation`; route the service's 401 through the seam.
- `frontend/src/lib/components/holdings/holdingsService.svelte.ts` — no API change needed (`load()` already covers it); extend `holdingsService.test.ts` only if you add a 401 branch inside the service instead of the shared seam (do not — use the seam).

**Steps:**
1. Create `frontend/src/lib/api/async-data.ts` with `redirectOn401(err: unknown): Promise<boolean>` exactly per the contract above, plus `async-data.test.ts` (mock `$app/navigation`'s `goto`; assert 401 → `goto('/auth/login?clear_session=true')` and `true`, non-401 ApiError and plain `Error` → no `goto`, `false`).
2. Slim `frontend/src/routes/holdings/+page.server.ts`: remove `loadAllHoldings` and its constants, remove the ApiError/DeleteAuthCookie catch layer; the load body is the unchanged preferences block (with its existing in-file comment) returning `{ holdings_table_config, group_mode, elliott_waves }`.
3. Rework `frontend/src/routes/holdings/+page.svelte`: drop the `service.rows = data.holdings` seed; keep `setGroupBy(data.group_mode)`; add the mount-time `$effect` calling `service.load()`; pass `isLoading` to `PageHeader`. Verify template needs no other structural change (skeleton, error alert, currency totals, settings menu already in place).
4. Update `page.server.test.ts` per the list above (this enforces AC 1's "server load no longer awaits holdings pagination").
5. Update `page.svelte.test.ts` per the list above; assertions map one-to-one to AC 1–4 and AC 5:
   - shell-first: component render with `service.isLoading === true` shows titlebar/actions/table headers + skeleton rows, `data.holdings_table_config`/`group_mode` applied to the settings menu on first render (AC 1, AC 5);
   - async fill: resolve mocked `getUserHoldings` across pages (multi-page using total=51 → 2 calls counts as enough; also assert the stale-`total`/MAX_PAGES semantics already covered by holdingsService tests), rows appear without user action, `currency-total-*` testids render correct totals (AC 2);
   - error: reject with a non-401 `Error` → `holdings-error` alert visible with the real message, no SvelteKit error (AC 3);
   - 401: reject with `ApiError(401, ...)` → mocked `goto` called with `'/auth/login?clear_session=true'` (AC 4).
6. Run targeted checks, then the full frontend regression (see Verification), fix lint/type fallout, and confirm prefs normalization/defaults behavior is byte-identical to today (AC 5 — no logic change in step 2's preferences block).

**Verification:**
- `./scripts/agent-test frontend/src/lib/api/async-data.test.ts frontend/src/routes/holdings/page.server.test.ts frontend/src/routes/holdings/page.svelte.test.ts` — seam + slimmed server load + shell-first/async-fill/error/401 component tests pass (AC 1–5).
- `./scripts/agent-test frontend` — Gate 0 (lint + `svelte-check`/type check) and full frontend suite pass with every API call mocked (AC 7).
- Manual (optional): `docker compose up -d` then press `h` on another page — titlebar "Holdings", actions, table headers and skeletons appear immediately; rows, currency totals follow without re-navigation; simulate 401 by clearing the session → lands on `/auth/login?clear_session=true` (AC 1–4).

**Risks / watch-outs:**
- **Unauthenticated navigation** now renders the shell first and redirects only after the client fetch 401s, instead of redirecting during SSR as today. Acceptable (criterion only covers the async-load 401), but implementers must not "restore" a server-side holdings request to pre-empt it.
- **Duplicate fetch**: SSR hydration runs the component; the mount `$effect` fires only in the browser — do not also call `service.load()` top-level in `<script>`, or fetches run twice.
- `service.isLoading` seeds the `PageHeader` skeleton, but `persistError`-only errors (preference save failures) must still render through the existing combined `errorMessage` — don't split them.
- `Preferences` normalization in the server load must keep its exact existing error-swallowing comment/behavior so AC 5 stays true; only the surrounding holdings try/catch is removed.
- Don't touch `data-sveltekit-preload-data="hover"` in `frontend/src/app.html` (as per ticket).
