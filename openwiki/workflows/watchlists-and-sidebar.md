---
type: workflow
title: Watchlists, Sidebar & Global Navigation
description: The watchlist feature end to end — the market CRUD/membership/reorder API, the repository invariants that make watchlist-not-found indistinguishable from not-owned, the layout-owned WatchlistService client state, the sidebar's Default-list naming convention and numeric shortcuts, the /watchlists page, and global search.
tags: [feed, watchlist, sidebar, frontend, market, navigation, shortcuts]
verified:
  - by: openwiki/0.6.0
    at: 2026-09-28T16:25:02.439Z
sources:
  - id: openwiki-source-5b9c00e9621399c68ca351b0
    resource: repo://frontend/src/lib/components/global-search.svelte
  - id: openwiki-source-d57b417669cd777cd7bd205b
    resource: repo://frontend/src/lib/components/layout/app-sidebar-watchlist.svelte
  - id: openwiki-source-e778f26f995b58e74570ef6f
    resource: repo://frontend/src/lib/components/watchlist/watchlist-utils.ts
  - id: openwiki-source-04059ae9c861b675fbebe0d7
    resource: repo://frontend/src/lib/components/watchlist/watchlistService.svelte.ts
  - id: openwiki-source-eaf28afd746bbeb265c93c7b
    resource: repo://frontend/src/lib/components/watchlist/watchlistService.test.ts
  - id: openwiki-source-a8a830617ab03d4b55d49d9a
    resource: repo://frontend/src/routes/%2Blayout.svelte
  - id: openwiki-source-23b2c24e0397108b043ab98b
    resource: repo://frontend/src/routes/layout.test.ts
  - id: openwiki-source-a680cc2053312375d46bcfe4
    resource: repo://frontend/src/routes/watchlists/%2Bpage.server.ts
  - id: openwiki-source-68c192b8e5d3899c314276cf
    resource: repo://frontend/src/routes/watchlists/%2Bpage.svelte
  - id: openwiki-source-32de67fe2a1cdc378983319d
    resource: repo://frontend/src/routes/watchlists/page.svelte.test.ts
  - id: openwiki-source-11b9d806fcc6dd6e7747ed87
    resource: repo://src/main.py
  - id: openwiki-source-0759916706da37d0d3bef090
    resource: repo://src/market/exception.py
  - id: openwiki-source-8ba9c7034638e16be9336256
    resource: repo://src/market/repository_sqlalchemy.py
  - id: openwiki-source-d8383d22d61483b00080a280
    resource: repo://src/market/router.py
  - id: openwiki-source-ef56252cb773f63950e8458e
    resource: repo://src/market/schema.py
  - id: openwiki-source-dd28499399904d11b673ae13
    resource: repo://tests/repositories/test_repository_sqlalchemy.py
  - id: openwiki-source-a4d537c22eb76e76a0ffde6e
    resource: repo://tests/routers/test_market.py
generated: { by: "openwiki/0.6.0", at: "2026-09-28T16:25:02.439Z" }
---

The watchlist surface is the one part of the market domain with full CRUD rather than
per-security sub-resources: a user owns named lists of securities, each list carries a persisted
sort mode and a manual membership order, and the whole thing is rendered twice — once as compact
sidebar groups and once as the full `/watchlists` page. Both readings share one client-side source
of truth, `WatchlistService`, which the root layout instantiates and owns.

Backend repository mechanics are catalogued in [Backend Domains](../architecture/domains.md); this
page owns the interaction model that spans the two.

## The Default-list naming convention

Everything user-facing hangs off a literal name. The user's *default* watchlist is the one whose
`name` is exactly `"Default"` — there is no flag column and no `is_default` field:

- `SqlAlchemyWatchlistRepository._get_default_watchlist` resolves it by
  `WatchlistModel.name == "Default"`, and `add_security` / `remove_security` (the default-list
  shortcuts behind `POST|DELETE /market/watchlists/securities/{security_id}`) go through it.
  `add_security` creates the `"Default"` list on first add and tolerates a concurrent-create
  `IntegrityError` by re-reading.
- `WatchlistService.defaultWatchlist` in the frontend is
  `watchlists.find((w) => w.name === 'Default') ?? null`, and `defaultWatchlistSecurities` derives
  from it. The global star toggle, the numeric shortcuts, and the prefetch list all read that
  derived value.

Consequences worth knowing before changing anything: renaming the default list away from `"Default"`
silently strips the star toggle and the numeric shortcuts from that list (nothing errors —
`defaultWatchlist` becomes `null`), and a user-created list named `"Default"` is simply the default
list. `create_default(user_id)` exists on the repository contract and mint the literal name, but no
router currently calls it.

## API surface

`market_router` (`src/market/router.py`, prefix `/market`) exposes the watchlist routes directly
against `WatchlistRepository` — there is no watchlist service layer between them:

| Method & path | Behavior |
| --- | --- |
| `GET /market/watchlists` | All watchlists for the caller, each read embedding its securities |
| `POST /market/watchlists` | `201`; body `WatchlistCreate.name` (1–100 chars) |
| `PATCH /market/watchlists/{watchlist_id}` | Rename and/or change the sort mode (`WatchlistUpdate`) |
| `DELETE /market/watchlists/{watchlist_id}` | `204` |
| `GET /market/watchlists/{watchlist_id}/securities` | Paginated, `symbol`-ordered, price-enriched |
| `POST\|DELETE /market/watchlists/{watchlist_id}/securities/{security_id}` | Membership edit; both return the updated `WatchlistRead` |
| `PUT /market/watchlists/{watchlist_id}/securities/order` | Full replacement of the manual order (`WatchlistOrderUpdate.security_ids`) |
| `POST\|DELETE /market/watchlists/securities/{security_id}` | Default-list shortcuts |

The frontend mirror is `MarketService` (`frontend/src/lib/api/marketService.ts`), whose
`WatchlistRead` / `WatchlistSecuritySchema` / `WatchlistSort` types are the wire contract. A
`WatchlistSecuritySchema` is a `SecuritySchema` plus `added_at` and `position`. Note there are two
frontend methods for the same route: `addSecurityToWatchlist(watchlistId, securityId)` and
`removeSecurityFromWatchlist(...)` hit the per-watchlist path, while `addToWatchlist(securityId)` /
`removeFromWatchlist(securityId)` hit the default-list shortcut and are used only by the star toggle
in global search.

Every watchlist read is *enriched*: `_fetch_price_metrics` runs one batched `row_number()` window
query over the latest two closes per security and fills `current_price`,
`daily_price_change`, and `daily_price_change_percent` on each embedded security, so a list read is
never a bare join.

## Security model: three deliberate status codes

The watchlist routes depend on `current_user` and pass `user.id` down into every repository call.
The three error classes are shaped specifically so the global exception handlers do not blur them:

- **Watchlist not found vs. not owned — 404, deliberately indistinguishable.**
  `WatchlistNotFoundError` subclasses `EntityNotFoundError`, and
  `SqlAlchemyWatchlistRepository._get_owned` filters on *both* `id` and `user_id`, raising the same
  error for an unknown id and for another user's list. The global
  `@app.exception_handler(EntityNotFoundError)` in `src/main.py` answers `404 {"error": ...}`.
  A caller therefore cannot use the status code to probe whether a watchlist id exists. The
  repository ABC documents this as a contract requirement on implementations.
- **Duplicate name — 409.** `WatchlistDuplicateNameError` is a plain `Exception`, *not* an
  `EntityNotFoundError`, so the global 404 handler does not intercept it; the router translates it
  to `HTTPException(409, ...)`. It is raised from an `IntegrityError` on commit against the
  `UniqueConstraint("user_id", "name")` on `market_watchlists`. The 409 applies to both
  `POST /market/watchlists` (create) and the rename branch of `PATCH`.
- **Non-permutation reorder payload — 422.** `WatchlistOrderIdentityError` is likewise a plain
  exception translated by the router to `HTTPException(422, ...)`.

One subtlety in `market_update_watchlist`: a `PATCH` payload that changes nothing (no `name`, no
`sort`) still has to prove ownership. The handler leaves `watchlist` as `None` and then re-reads the
caller's lists, raising `WatchlistNotFoundError` if the id is not among them — so a bare `{}` PATCH
on another user's list is a 404, not a 200.

An empty-string or `null` `name` is rejected by the `WatchlistUpdate` field constraints
(`min_length=1, max_length=100`), and an unrecognised `sort` value is a 422 from enum validation
that stores nothing.

## Three ordering mechanisms

The single most confusing thing about watchlists is that "order" means three different things. They
are separate on purpose:

1. **Persisted membership position** — `market_watchlists_securities.position`, an
   application-managed integer. `_load_memberships` queries the association table explicitly
   (joined to the securities) and orders by `position` then `added_at`, because a `secondary`
   relationship cannot order by or carry association columns. An add appends at `max(position) + 1`,
   which is not concurrency-safe under simultaneous adds.
2. **The stored per-watchlist sort mode** — `market_watchlists.sort` (a `WatchlistSortMode`
   StrEnum: `custom`, `name_asc`, `price_change_desc`, `price_change_asc`, `date_added`,
   `date_added_asc`), `server_default="custom"`, exposed on every read as `WatchlistRead.sort` and
   written by `update_sort`. **The repository never applies it**: reads always come back ordered by
   `position`. It is a persisted preference, not a query parameter.
3. **The client-side sort application** — `sortSecurities(securities, sortKey)` in
   `frontend/src/lib/components/watchlist/watchlist-utils.ts` is what actually renders the mode.
   `normalizeWatchlistSort` narrows the persisted (or absent, or stale) string to the known union,
   falling back to `custom`; `sortSecurities` then switches on it, with an unrecognised key also
   falling back to position order. `date_added`/`date_added_asc` compare `added_at` strings,
   `price_change_*` sorts on `daily_price_change_percent` with nulls pushed last.

This split is why `PUT .../securities/order` only makes sense in `custom` mode: the page gates the
per-list security reorder handle on `normalizeWatchlistSort(watchlist.sort) === 'custom'`, since
only then does row order map onto `position`. Changing the sort mode away from custom and back does
not disturb the stored positions.

### The reorder invariant

`set_security_order` requires `ordered_security_ids` to be an **exact permutation** of the current
membership, and validates before writing anything:

```
if len(ordered_security_ids) != len(current_ids) or set(ordered_security_ids) != set(current_ids):
    raise WatchlistOrderIdentityError
```

`set` collapses duplicates, so it is the *length* check that rejects a payload repeating a member
id. A missing id, a foreign id, or a superset all fail the set comparison. On acceptance the
positions are rewritten to `0..n-1` in one UPDATE per membership; a payload equal to the current
order skips the write entirely but still returns the read. `[]` is the valid permutation of an empty
watchlist.

## WatchlistService: the client state owner

`frontend/src/lib/components/watchlist/watchlistService.svelte.ts` defines a runes-based
`WatchlistService`, instantiated exactly once: the root `+layout.svelte` calls
`setWatchlistService()`, which puts it in Svelte context under a `Symbol` key;
`getWatchlistService()` reads it back (passing a `customFetch` instead constructs a detached
instance, used by tests).

State shape:

- `watchlists` — the array returned by `GET /market/watchlists`, i.e. every list with its enriched
  securities already embedded. There is no separate per-list fetch on the happy path.
- Derived: `defaultWatchlist` (by name), `defaultWatchlistSecurities`, `activeWatchlist` (by
  `activeWatchlistId`, set by `selectWatchlist`).
- `isLoading` / `error` — `error` is a single shared string, and every mutation starts by clearing
  it, so a successful call always wipes a stale message.

Caught errors are reported in two different styles. `loadWatchlists` **returns** the caught error
(after storing its message in `error`) so the layout can route a 401 through the shared
`redirectOn401` seam and stop; it returns `null` on success. Every other method swallows its error
into `handleError`, which sets `error` and `console.error`s. Three methods —
`removeSecurityFromWatchlist`, `reorderSecurities`, `toggleSecurity` — **resync first** and record
the error afterwards, because `loadWatchlists` clears `error` at its start and would otherwise erase
the message they just set.

Mutations are server-authoritative: each returns the updated `WatchlistRead` and
`replaceWatchlist` swaps it into the array. Reorder is the one optimistic case —
`reorderSecurities` rebuilds the local array in the given id order with each `position` rewritten to
its index before the `PUT` resolves, then replaces it with the server payload; `setSort` deliberately
applies *no* optimistic update.

`addSecurity(watchlistId, result)` is the search-result entry point and encodes the dedupe rule:
it returns immediately if the target list already holds a security with the same symbol *and*
exchange, otherwise it searches *all* loaded lists for a matching security id so an existing
security is reused, and only calls `createOrUpdateSecurity` when none is found.

## The `/watchlists` page

`frontend/src/routes/watchlists/+page.server.ts` returns `{ watchlists: [] }` and awaits nothing —
the layout owns the initial fetch, so the page paints its header, actions and skeleton rows
immediately. The `data.watchlists` prop exists only for the page's seeding guard (copy server data
into the service if the service is empty), which is inert while the loader stays empty.

The page (`+page.svelte`) is the full editing surface:

- **List order** — `watchlistOrder` comes from the `initialWatchlistOrder` context or
  `$page.data.watchlist_order`, and `sortWatchlistsByOrder` reorders the service array to match,
  appending lists absent from the stored order at the end. The optimistic reorder is applied
  locally, announced through an `aria-live` status region, then persisted with
  `userPreferencesService.patchPreferences({ watchlist_order })`; on failure both the local
  snapshot and the order are restored and the message lands in the shared alert. Drag-and-drop and
  the keyboard path (`ArrowUp`/`ArrowDown` on the grab handle) both funnel through `moveWatchlist`
  so the two stay in lockstep.
- **Rename / delete / per-list add** — inline rename with Enter/Escape, a confirmation modal for
  delete, and a plus button that opens global search *targeted at that list*
  (`openGlobalSearch(watchlist)`).
- **Per-list sort** — a six-option dropdown mirroring `WatchlistSortMode`, where the active option
  shows a direction chevron; each selection calls `watchlistService.setSort`.
- **Per-list security reorder** — a grab handle shown only for `custom`-sorted lists, toggled one
  list at a time and disabled while list reorder mode is on. Keyboard moves keep focus on the
  handle: Svelte's keyed `{#each}` reconciliation detaches the row when it shifts to a later index,
  dropping focus to `<body>` and making the list unwalkable after the first reverse move, so
  `restoreHandleFocus` re-focuses the same (still-connected) node after `tick()` — but only if the
  DOM move actually dropped it.
- **Rows** — a shared static Tailwind grid literal (`WATCHLIST_ROW_DATA_TRACKS`) keeps every row's
  column tracks identical; the date track is dropped below `md` while its cell still renders a dash,
  so price and change pill never shift. Prices and percentages go through `formatPrice` /
  `formatPriceChangePercent` (sign-prefixed, `-` when absent) and `formatDateAdded` (fixed `en-US` +
  UTC so output is deterministic).
- **Row selection** is focus-driven and keyed by *security id*, not row index, so the highlight
  follows a security through reorder and sort changes; a removed security's selection is cleared.

## Sidebar

`frontend/src/lib/components/layout/app-sidebar.svelte` is a thin shell: `Sidebar.Root
collapsible="icon"` containing `AppSidebarHeader`, then `AppSidebarActions` and
`AppSidebarWatchlist` inside `Sidebar.Content`, then `AppSidebarProfile` and a `Sidebar.Rail`
toggle.

### Group rendering

`app-sidebar-watchlist.svelte` reads `getWatchlistService()` and renders one `Sidebar.Group` per
watchlist, in `sortWatchlistsByOrder` order from the `initialWatchlistOrder` context or
`$page.data.watchlist_order`. Each group has a collapse caret backed by a `SvelteSet` of collapsed
ids, seeded from the `initialCollapsedWatchlistIds` context or `$page.data.collapsed_watchlist_ids`
and written back with a fire-and-forget
`patchPreferences({ collapsed_watchlist_ids })` (`.catch(console.error)` — no rollback, unlike list
order on the page).

The Default list is privileged in the collapsed rail: groups for non-default watchlists carry
`group-data-[collapsible=icon]:hidden!`, and the group header always hides, so only the Default
list's tickers survive icon-collapse mode. Ticker glyphs are sized by symbol length
(`getTickerFontSize`), and the collapsed tooltip includes the numeric shortcut.

The sidebar renders `watchlist.securities` in server order (position order) and does **not** apply
`sortSecurities` — the sort mode is a `/watchlists` page presentation.

### Numeric shortcuts and the 1–9/0 convention

`getTickerShortcut(index)` maps the *nth security of the Default watchlist* to a hint: `1`–`9` for
indices 0–8 and `0` for index 9. Indices beyond 9 get no hint. The keys themselves are handled by
the root layout, which reads the same `defaultWatchlistSecurities` array:

- `1`–`9` → index `Number(key) - 1`; `0` → index `9`; out-of-range is a silent no-op. On a hit it
  prefetches then `goto`s `/security/{id}`.
- `w` / `W` → prefetch then navigate to `/watchlists`; `h` / `H` → `/holdings`.
- `/` → toggles the global-search dialog.
- Shortcuts are skipped for any modifier-held key and whenever the event target is an
  `INPUT`/`TEXTAREA`/`SELECT`/`contentEditable`.

Because the sidebar hints are rendered from a per-group render index while the layout navigates by
the Default list's index, the two only agree for the Default list — which is exactly why
`getTickerShortcut` is only passed for it.

### Prefetch

Once `loadWatchlists()` resolves, the layout warms the shortcut targets with `preloadData`:
`/watchlists`, `/holdings`, then the first ten default-watchlist securities. Prefetches are
fire-and-forget, and `prefetchedUrls` (a per-layout-instance `SvelteSet`, deliberately not module
scope) guarantees each URL is warmed at most once even across repeated key presses; rejected
prefetches are swallowed since the real navigation load still runs.

## Global search

`frontend/src/lib/components/global-search.svelte` is a command dialog. It reads the watchlist
service and behaves in two modes:

- **Targeted** (`targetWatchlist` set, opened from a list's plus button) — the placeholder names the
  list and the star toggles membership *of that list*, resolving a new security via
  `createOrUpdateSecurity` when the search hit is unknown.
- **Untargeted** (`/` or the sidebar Search button) — the star toggles the *default* list through
  `WatchlistService.toggleSecurity` (i.e. the `POST|DELETE /market/watchlists/securities/{id}`
  shortcuts), and the star's filled state is derived by matching `symbol` + `exchange` against the
  relevant list's securities.

Search input is debounced (300 ms) into `marketService.search`, results are grouped by
`security_type`, and selecting a row resolves the security then navigates to `/security/{id}`.

## Failure and lifecycle notes

- `loadWatchlists` runs from a `$effect` in `+layout.svelte`, which never executes during SSR — the
  fetch is browser-only. A 401 is routed through `redirectOn401(err)`; any other error returns
  `false` and is surfaced by the caller/page alert.
- `error` is a single shared slot: concurrent failures overwrite each other, and any successful
  mutation clears it. The intentional `loadWatchlists()`-then-`handleError` ordering in the three
  resyncing methods exists to survive that clear.
- Cross-user isolation is enforced at the repository, verified end to end: `GET /watchlists` never
  returns another user's lists, and membership/rename/reorder/sort writes against another user's
  watchlist return 404 with the target untouched.

## Focused tests

| Test | What it pins down |
| --- | --- |
| `tests/routers/test_market.py` | Full watchlist router surface: list/embed securities, `"Default"` naming on the shortcuts, membership add/remove idempotence, rename + duplicate-name 409, sort PATCH (including invalid-sort 422 leaving `custom` stored), combined and empty PATCH, reorder acceptance and four rejected non-permutation payloads, delete 204, unauthenticated 401s, and 404 + untouched state for every not-owned case |
| `tests/repositories/test_repository_sqlalchemy.py` | Repository-level create/duplicate, rename, delete cascade, membership position/`added_at`, the `WatchlistRead` contract with `sort` and ordered metadata, `update_sort` persistence, `set_security_order` (rewrite, idempotence, empty list, rejection before any write), and price enrichment across 0/1/2/3+ prices and a zero previous close |
| `frontend/src/lib/components/watchlist/watchlistService.test.ts` | Service state transitions: default-list derivation, 401 seam return value, local append/replace per mutation, dedupe in `addSecurity`, cross-list security-id reuse, and the error lifecycle (set on failure, cleared on the next success) |
| `frontend/src/lib/components/watchlist/watchlist-utils.test.ts` | `normalizeWatchlistSort` fallback, `sortWatchlistsByOrder` partial-order append, `moveItem` no-ops, `handleReorderKeydown`, `sortSecurities` per mode, and the formatters |
| `frontend/src/routes/watchlists/page.svelte.test.ts` | The page's rename/delete/sort/reorder flows and that `watchlist_order` drives `sortWatchlistsByOrder` and is patched on reorder |
| `frontend/src/lib/components/layout/app-sidebar.test.ts` | Group order from `initialWatchlistOrder` (including partial), per-list collapse persisted to `collapsed_watchlist_ids`, initial collapsed ids, collapsed-rail ticker sizing, and the Default group surviving icon collapse |
| `frontend/src/routes/layout.test.ts` | The shortcuts (`/`, `w`, `h`, `1`–`9`/`0`), modifier/typing suppression, the once-per-URL prefetch of `/watchlists`, `/holdings` and the first ten default tickers, swallowed prefetch failures, and the 401 redirect through the shared seam |

See also [User Preferences](../concepts/user-preferences.md) for how `collapsed_watchlist_ids` and
`watchlist_order` are stored and loaded, and [Security Detail Page Surfaces](./security-detail-page-surfaces.md)
for the destination of the ticker shortcuts.
