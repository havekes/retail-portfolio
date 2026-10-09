# WATCHLISTS-T08 Implementation Plan

## Plan

**Approach:**
Rework the watchlist user experience across three coordinated areas:
1. Update user preferences and root layout to replace the obsolete global `sidebar_watchlists` preference with `collapsed_watchlist_ids` and provide a layout-level `openGlobalSearch(watchlist)` context.
2. In `app-sidebar-watchlist.svelte`, list all watchlists unconditionally, defaulting to expanded, and persist collapsed states via `patchPreferences({ collapsed_watchlist_ids })` on caret click.
3. On `/watchlists/+page.svelte`, move "Create watchlist" into PageHeader actions, remove `WatchlistSecurityPicker` and Eye/EyeOff toggle, and render each watchlist as its own section with title inline rename, action buttons (+, pencil, trash), and rounded hover links (`rounded-md px-2 py-1.5 transition-colors hover:bg-muted`) for each security. In `global-search.svelte`, accept an optional `targetWatchlist` prop to update placeholder and star toggle target, auto-resetting on dialog close.

**Files:**
- `frontend/src/lib/api/userPreferencesService.ts` — modify: add `collapsed_watchlist_ids?: string[] | null` to `UserPreferences` and clean up `sidebar_watchlists`.
- `frontend/src/routes/+layout.server.ts` — modify: load `collapsed_watchlist_ids` from preferences instead of `sidebar_watchlists`.
- `frontend/src/routes/+layout.svelte` — modify: clean up `sidebar_watchlists` state/context, provide `openGlobalSearch(watchlist)` context and `initialCollapsedWatchlistIds` context, bind `targetWatchlist` to `<GlobalSearch />`.
- `frontend/src/lib/components/layout/app-sidebar-watchlist.svelte` — modify: remove `sidebar_watchlists` branching, always render all watchlists, initialize `collapsedIds` (defaulting to empty/expanded), persist toggled IDs via `userPreferencesService.patchPreferences`.
- `frontend/src/lib/components/layout/app-sidebar.test-harness.svelte` — modify: update test harness to drop `sidebar_watchlists` props/context and support `initialCollapsedWatchlistIds`.
- `frontend/src/lib/components/global-search.svelte` — modify: support bindable `targetWatchlist` prop, update placeholder and star button toggle target, reset `targetWatchlist` on dialog close.
- `frontend/src/routes/watchlists/+page.svelte` — modify: move "Create watchlist" to PageHeader actions, remove Eye/EyeOff toggle, remove `WatchlistSecurityPicker`, render each watchlist in its own section with header actions (+, pencil, trash) and rounded hover links for securities.
- `frontend/src/lib/components/layout/watchlist-sidebar-pref.ts` — modify/delete: remove obsolete sidebar toggle context file.
- `frontend/src/lib/components/layout/watchlist-sidebar-pref-probe.svelte` — modify/delete: remove obsolete probe component.
- `frontend/src/lib/components/global-search.test.ts` — create: add unit tests for global search target watchlist behavior, placeholder updates, star button toggle, and close reset.
- `frontend/src/lib/components/layout/app-sidebar.test.ts` — modify: update tests to verify unconditional watchlist rendering, caret toggle collapse persistence, and default expanded state.
- `frontend/src/routes/watchlists/page.svelte.test.ts` — modify: update tests to verify PageHeader create button, multiple watchlist sections rendering, targeted search "+" button opening, security rounded link styling, and security removal.
- `frontend/src/routes/layout.test.ts` — modify: update layout tests to reflect `collapsed_watchlist_ids` and removal of `sidebar_watchlists`.
- `frontend/src/routes/settings/security/page.svelte.test.ts` — modify: clean up obsolete `sidebar_watchlists` mock data.

**Steps:**
1. **Update UserPreferences interface and server load:**
   - In `frontend/src/lib/api/userPreferencesService.ts`, add `collapsed_watchlist_ids?: string[] | null` to `UserPreferences`.
   - In `frontend/src/routes/+layout.server.ts`, replace `sidebar_watchlists` with `collapsed_watchlist_ids: string[]`, populating from `prefs.collapsed_watchlist_ids` if present.
2. **Refactor sidebar watchlist navigation and collapse persistence:**
   - In `frontend/src/lib/components/layout/app-sidebar-watchlist.svelte`, remove `showWatchlists` conditional branching so all watchlists always render.
   - Initialize `collapsedIds` from context (`initialCollapsedWatchlistIds`) or `page.data.collapsed_watchlist_ids`, defaulting to an empty `SvelteSet<string>()` (expanded).
   - In `toggleCollapsed(watchlistId)`, update `collapsedIds` and call `userPreferencesService.patchPreferences({ collapsed_watchlist_ids: Array.from(collapsedIds) })`.
   - Update `frontend/src/lib/components/layout/app-sidebar.test-harness.svelte` to remove obsolete `showWatchlists` and provide `initialCollapsedWatchlistIds`.
   - Remove obsolete `frontend/src/lib/components/layout/watchlist-sidebar-pref.ts` and `frontend/src/lib/components/layout/watchlist-sidebar-pref-probe.svelte`.
3. **Enhance GlobalSearch component and layout communication:**
   - In `frontend/src/lib/components/global-search.svelte`, add bindable prop `targetWatchlist = $bindable<WatchlistRead | null>(null)`.
   - Derive placeholder: `targetWatchlist ? "Search securities to add to " + targetWatchlist.name + "..." : "Search for a company or symbol..."`.
   - In `getWatchlistSecurity(result)` and `handleWatchlistToggle(e, result)`, if `targetWatchlist` is active, check membership and toggle via `removeSecurityFromWatchlist(targetWatchlist.id, existing.id)` or `addSecurityToWatchlist(targetWatchlist.id, response.security_id)`. If `targetWatchlist` is null, preserve existing default watchlist toggle behavior.
   - In the `$effect` triggered on `!open`, reset `targetWatchlist = null` alongside `query` and `searchResults`.
   - In `frontend/src/routes/+layout.svelte`, remove `sidebar_watchlists` state and context. Manage `globalSearchTargetWatchlist = $state<WatchlistRead | null>(null)`. Provide `setContext('openGlobalSearch', (watchlist?: WatchlistRead | null) => { globalSearchTargetWatchlist = watchlist ?? null; globalSearchOpen = true; })` and pass `bind:targetWatchlist={globalSearchTargetWatchlist}` to `<GlobalSearch />`.
4. **Rework Watchlists page (`/watchlists/+page.svelte`):**
   - Move the "Create watchlist" button into the `PageHeader` `actions` snippet to open `CreateWatchlistModal`, and remove the Eye/EyeOff toggle and `sidebarPref` references.
   - Remove the inline `WatchlistSecurityPicker` and obsolete single active watchlist detail section.
   - Render each watchlist from `watchlistService.watchlists` in its own `<section>`:
     - Header: Watchlist title on the left with inline rename input/buttons; action buttons on the right: "+" (calls `openGlobalSearch(watchlist)`), pencil (calls `startRename(watchlist)`), trash (calls `requestDelete(watchlist)`).
     - Securities list: Each item wraps ticker symbol and company name in an `<a href={resolve('/security/' + security.id)}>` link with `class="flex flex-1 items-center gap-2 rounded-md px-2 py-1.5 transition-colors hover:bg-muted focus:bg-muted"`, alongside an "X" button calling `watchlistService.removeSecurityFromWatchlist(watchlist.id, security.id)`.
     - Empty state: Render `<p class="text-sm text-muted-foreground">No securities in this watchlist yet.</p>` when `watchlist.securities.length === 0`.
5. **Add tests and update existing test suites:**
   - Create `frontend/src/lib/components/global-search.test.ts` to test default search placeholder/behavior, targeted placeholder/star toggle, and reset on dialog close.
   - Update `frontend/src/lib/components/layout/app-sidebar.test.ts` to assert all watchlists render, default expanded state, and `patchPreferences` call with `collapsed_watchlist_ids` on caret click.
   - Update `frontend/src/routes/watchlists/page.svelte.test.ts` to assert PageHeader create button, each watchlist rendered as its own section, "+" opening targeted search, security rounded link styling, and security removal.
   - Update `frontend/src/routes/layout.test.ts` and `frontend/src/routes/settings/security/page.svelte.test.ts` to remove obsolete `sidebar_watchlists` assertions and mock properties.
6. **Run quality verification:**
   - Run type checking: `npm --prefix frontend run check`.
   - Run linter/formatting checks: `npm --prefix frontend run lint`.
   - Run tests: `npm --prefix frontend run test:run`.

**Verification:**
- `npm --prefix frontend run check`: passes with zero TypeScript / Svelte check errors.
- `npm --prefix frontend run lint`: passes with zero ESLint or Prettier issues.
- `npx --prefix frontend vitest run frontend/src/lib/components/global-search.test.ts`: verifies placeholder, targeted star toggle, and close reset.
- `npx --prefix frontend vitest run frontend/src/routes/watchlists/page.svelte.test.ts`: verifies PageHeader create button, per-watchlist sections, "+" button action, rounded link styling, and security removal.
- `npx --prefix frontend vitest run frontend/src/lib/components/layout/app-sidebar.test.ts`: verifies unconditional listing of all watchlists, default expansion, and caret collapse persistence to `collapsed_watchlist_ids`.
- `npx --prefix frontend vitest run frontend/src/routes/layout.test.ts`: verifies layout passes with cleaned-up preferences.
- `npm --prefix frontend run test:run`: full frontend test suite passes cleanly.

**Risks / watch-outs:**
- **Dynamic route shell discipline**: Avoid unquoted brackets in shell commands involving `/security/[security_id]`. Pass test file paths explicitly without bracket wildcards.
- **Search reactivity**: In `global-search.svelte`, derive the active target watchlist from `watchlistService.watchlists` using `targetWatchlist.id` so that newly added or removed securities immediately toggle the star icon between hollow and filled states without needing to reopen the search modal.
- **Async collapse persistence**: In `app-sidebar-watchlist.svelte`, catch rejection from `userPreferencesService.patchPreferences` to ensure network errors do not freeze or revert the local caret collapse toggle.
