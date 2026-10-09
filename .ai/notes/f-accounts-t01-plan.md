# Implementation Plan - F-ACCOUNTS-T01: Display relative last sync date on account card

## Plan

**Approach:** Add `last_sync_at?: string | Date | null` to the frontend `Account` interface and implement relative timestamp formatting in `frontend/src/lib/utils/date.ts` (`formatRelativeSyncTime`) to handle "Never synced" (for null/undefined/invalid dates) and "Synced <relative>" with minute ("5m ago"), hour ("2 hours ago"), day, week, month, and year intervals. Display the formatted string in `AccountsListItem`'s footer row, reactively updating both when `account.last_sync_at` updates and immediately when an active sync completes (`wasSyncing && !isSyncing && !syncError`), and trigger account refetch on `SYNC_FINISHED` in `AccountsListState`. (Alternative rejected: using raw `Intl.RelativeTimeFormat` directly in the component, because it outputs "5 min. ago" instead of "5m ago" and requires custom wrapper code for "Never synced" and prefix handling anyway).

**Files:**
- `frontend/src/lib/types/account.ts` — modify: add `last_sync_at?: string | Date | null;` to the `Account` interface.
- `frontend/src/lib/utils/date.ts` — modify: export `formatRelativeTime` and `formatRelativeSyncTime` supporting relative units ("5m ago", "2 hours ago", "just now", "Never synced").
- `frontend/src/lib/utils/date.test.ts` — modify: add unit tests verifying `formatRelativeSyncTime` with null, undefined, invalid dates, future/clock skew, minutes, hours, days, weeks, months, and years against deterministic reference dates.
- `frontend/src/lib/components/accounts/accounts-list-item.svelte` — modify: render relative sync time in the metadata footer, bind reactive local state to `account.last_sync_at`, and update local sync timestamp to `new Date()` upon sync completion (`wasSyncing && !isSyncing && !syncError`).
- `frontend/src/lib/components/accounts/accounts-list.svelte.ts` — modify: invoke `await this.fetchAccounts()` on `WsEventType.SYNC_FINISHED` to synchronize updated account records across the app.
- `frontend/src/lib/components/accounts/accounts-list-item.test.ts` — modify: add tests for relative sync time rendering with timestamps, "Never synced" when null/undefined, reactive transition when sync completes, and error resilience.

**Steps:**
1. Update `frontend/src/lib/types/account.ts` to include `last_sync_at?: string | Date | null;` on `Account`.
2. In `frontend/src/lib/utils/date.ts`, implement `formatRelativeTime(date: Date | string, now?: Date): string` and `formatRelativeSyncTime(date: Date | string | null | undefined, now?: Date): string` matching the required intervals ("just now", "5m ago", "2 hours ago", "Never synced").
3. Add unit tests for `formatRelativeSyncTime` in `frontend/src/lib/utils/date.test.ts` covering null, undefined, invalid date strings, just now (<60s), minutes, hours, days, and older timestamps with deterministic `now` values.
4. Update `frontend/src/lib/components/accounts/accounts-list-item.svelte` to import `formatRelativeSyncTime`, display the relative timestamp in the footer row, maintain reactive state `localLastSyncAt`, and set `localLastSyncAt = new Date()` when sync finishes without error.
5. In `frontend/src/lib/components/accounts/accounts-list.svelte.ts`, call `await this.fetchAccounts()` in the `WsEventType.SYNC_FINISHED` handler so backend-persisted `last_sync_at` updates in accounts list state.
6. In `frontend/src/lib/components/accounts/accounts-list-item.test.ts`, add unit tests verifying:
   - Rendering "Never synced" when `account.last_sync_at` is null or omitted.
   - Rendering relative timestamps like "Synced 2 hours ago" and "Synced 5m ago" when `account.last_sync_at` is provided.
   - Reactively updating from "Never synced" to "Synced just now" when `isSyncing` changes from `true` to `false`.
   - Reactively updating when `account` prop is rerendered with an updated `last_sync_at`.
   - Preserving previous sync state without false update when sync completes with a `syncError`.

**Verification:**
- Run unit tests: `pnpm --filter frontend test:run src/lib/components/accounts/accounts-list-item.test.ts src/lib/utils/date.test.ts` to verify all sync display and date formatting tests pass.
- Run type check and lint: `pnpm --filter frontend check` and `pnpm --filter frontend lint` to verify clean types and linting.
- Run full frontend test suite: `pnpm --filter frontend test:run` to verify no regressions in other account components or tests.
- Observe:
  - Account with `last_sync_at: null` renders "Never synced" (AC: [ ] When account.last_sync_at is null, displays "Never synced").
  - Account with `last_sync_at` 2 hours in past renders "Synced 2 hours ago"; 5 minutes in past renders "Synced 5m ago" (AC: [ ] When account.last_sync_at is set, displays relative time).
  - Toggling `isSyncing` from `true` to `false` updates rendered text to "Synced just now" (AC: [ ] Reactively updates when account sync completes).
  - All unit tests pass in `accounts-list-item.test.ts` (AC: [ ] Unit tests in accounts-list-item.test.ts pass).
  - Svelte check and Vitest suite pass cleanly (AC: [ ] Build passes and relevant tests pass).

**Risks / watch-outs:**
- Clock skew: server timestamps might occasionally be slightly ahead of local machine time. `formatRelativeSyncTime` must treat negative diffs (< 0) as "Synced just now" rather than "in X seconds" or throwing an error.
- Prop reactivity: Svelte 5 runes (`$props()`) require derived state or an `$effect` to keep local sync tracking synchronized when the parent passes an updated account prop.
