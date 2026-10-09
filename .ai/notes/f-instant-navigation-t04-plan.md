## Meta
- id: F-INSTANT-NAVIGATION-T04
- depends_on: [F-INSTANT-NAVIGATION-T01, F-INSTANT-NAVIGATION-T02, F-INSTANT-NAVIGATION-T03]
- branch: feat/f-instant-navigation-t04-prefetch-shortcuts
- source: ".opencode/features/instant-page-navigation.md"

## Objective

Warm the keyboard-shortcut targets so pressing `w`, `h`, or `1`–`9`/`0` navigates against already-prefetched route data instead of starting a cold load, and so the default watchlist's top securities are ready before the user asks for them.

## Scope

**In scope:**
- For authenticated users, eagerly prefetch (SPA route data prefetch, e.g. `preloadData` from `$app/navigation`) the shortcut target routes `/watchlists` and `/holdings`, plus `/security/<id>` for the default watchlist's first up-to-ten securities — using the same ordering the `0`–`9` shortcuts use (`watchlistService.defaultWatchlistSecurities`, index 0 → the tenth security).
- Trigger it once watchlists are known (after `watchlistService.loadWatchlists()` resolves) and without delaying or competing with the current route's own data load.
- Optionally also prefetch on the first shortcut keydown for any target not yet prefetched, so the first press is warm even if the background pass has not finished.
- Deduplicate: each URL is prefetched at most once; prefetch failures are swallowed (the real navigation load still runs) and must never surface as an error or unhandled rejection.
- Do nothing when unauthenticated.
- Tests: layout-level tests asserting `preloadData` is called with the expected URLs (both shortcut routes plus one per default-watchlist security, capped at ten, in the right order), that it is not called when unauthenticated, and that repeated calls are deduped. Mock `$app/navigation`, `$app/paths`, and every API client.

**Out of scope:**
- Changing the keyboard shortcuts themselves or their key mapping.
- Changing hover prefetch: `data-sveltekit-preload-data="hover"` in `frontend/src/app.html` stays exactly as-is, and sidebar/command-palette link behavior is unchanged.
- Prefetching other routes (brokers, accounts, settings).
- Any new client-side cache/stale-while-revalidate layer.
- Backend changes.

## Acceptance criteria

- [ ] After an authenticated app start (and once watchlists are loaded), `/watchlists`, `/holdings`, and `/security/<id>` for the default watchlist's first up-to-ten securities are prefetched in the background.
- [ ] `w`, `h`, and `1`–`9`/`0` navigation uses the warm route data where available; no prefetch delays the first render of the current page or blocks any user interaction.
- [ ] No prefetch happens when the user is unauthenticated.
- [ ] Each URL is prefetched at most once per session, and a failed prefetch produces no visible error and no unhandled rejection.
- [ ] `data-sveltekit-preload-data="hover"` remains in `frontend/src/app.html` and existing link-hover prefetch tests/behavior are unchanged.
- [ ] All tests mock every API call (no real network) and `./scripts/agent-test frontend` (or `./scripts/agent-test`) passes.

## Technical notes

- `frontend/src/routes/+layout.svelte` is the natural home: it has `data.user`, mounts `watchlistService` via `setWatchlistService()`, calls `watchlistService.loadWatchlists()` in an effect, and owns the keydown handler that maps `e.key` `'1'`–`'9'`/`'0'` to `watchlistService.defaultWatchlistSecurities[index]` (with `'0'` → index 9).
- Prefetch API: `$app/navigation` exposes `preloadData(url)` (and `preloadCode`). Resolve route URLs with `$app/paths` `resolve()` so base paths stay correct. Do not use `$effect` to trigger fetches (frontend/AGENTS.md Gotcha 2) — kick off the background pass from the existing data/watchlist-availability point or the keydown handler.
- Prefetching the security routes only pays off after T01–T03 land (cheap shell + async data); on `main` today those loads are blocking, which is why this ticket depends on all three.
- Respect the "no global instances / no SSR bleed" rule (Gotcha 3): keep prefetch state inside the layout component instance, not module scope.
- The prefetch must stay resilient: wrap calls so a rejection cannot break layout rendering, and guard against duplicate/racing invocations (e.g. keydown before the background pass completes).
- Do not touch `data-sveltekit-preload-data="hover"` in `frontend/src/app.html`.
- This branch targets the shared feature branch `feat/f-instant-navigation`, not `main`.

## Plan

**Approach:** Keep prefetching entirely inside `frontend/src/routes/+layout.svelte` as a small per-instance helper (Gotcha 3: no module-scope state) that wraps `preloadData(resolve(url))` from `$app/navigation` in a promise `.catch()` with a per-instance `Set<string>` used-set for dedupe. Trigger it (a) from the existing authenticated watchlists-load IIFE — after `watchlistService.loadWatchlists()` resolves successfully — for `/watchlists`, `/holdings`, then the default watchlist's first ten securities in shortcut order, and (b) from `handleKeydown` before each shortcut `goto` so the first press is warm even if the background pass hasn't reached that URL yet. Rejected alternative: a standalone `prefetchService.svelte.ts` — overkill for ~12 one-shot calls consumed only by the layout, and the state would still have to live in the layout instance to respect Gotcha 3.

**Files:**
- `frontend/src/routes/+layout.svelte` — modify: add prefetch helper + triggers (script logic only; no markup changes).
- `frontend/src/routes/layout.test.ts` — modify: extend the `$app/navigation` mock and add a prefetch test block.
- `frontend/src/app.html` — **do not touch** (`data-sveltekit-preload-data="hover"` stays).

**Steps:**

1. Create branch `feat/f-instant-navigation-t04-prefetch-shortcuts` off `feat/f-instant-navigation` (HEAD `70f25e86`, which already contains merged T01 #460, T02 #461, T03 #462).

2. In `+layout.svelte`, extend the existing import: `import { goto, preloadData } from '$app/navigation'` (`resolve` from `$app/paths` is already imported at line 11).

3. Add per-instance prefetch state + helper (script, near `handleKeydown`):
   ```ts
   let prefetchedUrls = new Set<string>();
   function prefetchUrl(url: string): void {
       if (prefetchedUrls.has(url)) return;
       prefetchedUrls.add(url);
       preloadData(resolve(url)).catch(() => {}); // swallow: the real navigation still loads
   }
   ```
   Resolve inside the helper so callers pass plain route paths (`/watchlists`, `/holdings`, `/security/${id}`) and base paths stay correct. No rejection may escape.

4. Wire the background pass into the existing `$effect` watchlists-load IIFE (lines ~36–46): after `const err = await watchlistService.loadWatchlists()`, only when `err === null` (skip the `redirectOn401` error path), kick off the (fire-and-forget, non-awaited) prefetch pass:
   ```ts
   prefetchUrl('/watchlists');
   prefetchUrl('/holdings');
   for (const s of watchlistService.defaultWatchlistSecurities.slice(0, 10)) {
       prefetchUrl(`/security/${s.id}`);
   }
   ```
   Ordering matches the `0`–`9` shortcut mapping: `defaultWatchlistSecurities` index 0 → key `1` … index 9 → key `0`. Because the pass only gets queued promises the render path never awaits, it cannot delay or block the current page's first render or any interaction. It stays inside the browser-only `$effect` path (per its existing SSR comment) rather than module scope.

5. In `handleKeydown`, call `prefetchUrl(...)` immediately before each shortcut `goto` (dedupe makes repeated work impossible):
   - `w`/`W` → `prefetchUrl('/watchlists'); void goto(resolve('/watchlists'));`
   - `h`/`H` → `prefetchUrl('/holdings'); void goto(resolve('/holdings'));`
   - digits → keep the exact index mapping (`e.key === '0' ? 9 : Number(e.key) - 1`), and when a `security` exists: `prefetchUrl(\`/security/${security.id}\`)` before `goto`. Do not change shortcut behavior otherwise.

6. Tests — extend `frontend/src/routes/layout.test.ts` (every API/framework module mocked, zero real network per frontend/AGENTS.md):
   - Update `vi.mock('$app/navigation', …)` to also export `preloadData: vi.fn()` (default `mockResolvedValue(undefined)`); reset it in `beforeEach` alongside `goto`. The existing `vi.mock('$app/paths', …)` identity `resolve` already covers base-path mocking.
   - New `describe('shortcut-target prefetch')` block, reusing the existing `renderLayout()` + captured-watchlist-service pattern:
     - **Authenticated background pass — URLs, order, cap of ten**: render authed; set `capturedWatchlistService.defaultWatchlistSecurities` to 11 securities (same object shape as the existing digits test); `await waitFor` `preloadData` calls; collect call arguments in order and assert the exact sequence `['/watchlists', '/holdings', '/security/sec-0', …, '/security/sec-9']` — 12 calls, each URL exactly once, the eleventh security (`sec-10`) absent. (AC 1)
     - **Unauthenticated no-op**: render with `data.user: null`; flush promises; assert `preloadData` never called. (AC 3)
     - **Dedupe against/racing the background pass**: fresh render; dispatch two `w` keydowns; assert `preloadData` called exactly once with `/watchlists` while `goto` was called twice (each press still navigates). Also covers the keydown-before-background-pass case. (AC 4)
     - **Swallowed failure**: `preloadData.mockRejectedValueOnce(new Error('prefetch boom'))`; press `w`; assert the test completes without an unhandled rejection, no error toast/alert is rendered, and `goto('/watchlists')` still fired. (AC 4)
     - Optional: press `'1'` after watchlists load and assert a `preloadData('/security/sec-0')` call ordering before/with `goto('/security/sec-0')`.
   - Confirm the added export doesn't break other tests that only import `goto`.

7. Verify the branch diff leaves `frontend/src/app.html` (line 14, `data-sveltekit-preload-data="hover"`) untouched.

**Verification:**
- Targeted: `./scripts/agent-test frontend/src/routes/layout.test.ts` — new prefetch block passes (background order/cap/dedupe, unauth no-op, swallowed failure) and the existing shortcut + 401-redirect suites remain green (AC 1, 3, 4).
- Full regression: `./scripts/agent-test` — Gate 0 (lint + typecheck) and both suites green (AC 6).
- `git diff feat/f-instant-navigation -- frontend/src/app.html` is empty (AC 5).
- AC 2 is covered by the design itself (fire-and-forget queued `preloadData`, never awaited by rendering — asserted indirectly by tests above not blocking/awaiting anything render-related).

**Risks / watch-outs:**
- `preloadData` is client-only: the background pass must stay inside the browser-only `$effect` IIFE (never module scope / SSR path), which the existing code comment already guarantees.
- Failure paths: `loadWatchlists()` error (e.g. 401 → `redirectOn401`) must lead to zero prefetches; a missing "Default" watchlist yields an empty array so `.slice(0, 10)` naturally no-ops.
- Test isolation: the dedupe `Set` is per-layout-instance, so a fresh `render()` resets it — just clear the `preloadData` mock in `beforeEach`. Missing `preloadData` from the `$app/navigation` mock factory would break the entire existing layout suite at import time.
- Don't re-run the warm pass reactively on unrelated layout invalidation: keep it in the already-detached async IIFE (`untrack` reads of `defaultWatchlistSecurities` if needed); the per-instance Set additionally guards duplicates if the effect re-runs after watchlist mutations.
- Always wrap with `resolve()` for base-path correctness.

## Review feedback

<Empty at creation. Orchestrator appends PR-review findings here.>
