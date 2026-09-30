---
title: Instant page navigation (instant shell, async content)
slug: instant-page-navigation
status: ready
date: 2026-09-21
---

# Instant page navigation

## Problem

The app now has keyboard shortcuts (`w`, `h`, `0–9` in `frontend/src/routes/+layout.svelte`) that jump between pages via `goto()`. But every navigation fully blocks until the target page's `+page.server.ts` resolves. The heaviest loads sit on exactly the shortcut paths — e.g. `frontend/src/routes/holdings/+page.server.ts` sequentially pages through *all* holdings (up to 100 pages of 50) plus a preferences request before rendering anything. So "instant" shortcut switching feels slow: the whole UI (including the already-rendered shell) freezes on the old page until the new page's data is ready.

## Goal

Pressing a shortcut (or clicking a sidebar link on the shortcut pages) switches the page immediately: the titlebar, page structure, and static chrome render instantly, with skeleton placeholders where data goes, and real data fills in asynchronously.

## User-facing behavior

- User presses `w` on any page → the watchlists page shell (titlebar "Watchlists", tabs, empty-state structure) appears instantly; the watchlist grid shows skeletons and populates shortly after.
- User presses `h` → same for holdings: table headers and toolbar render immediately, rows arrive asynchronously as the paginated fetch completes.
- User presses `1–9`/`0` → security page shell renders instantly; prices/chart data load async.
- Error/empty states: if the async data fetch fails after navigation, the page shows its normal error state (existing `errorMessage` handling) rather than a SvelteKit error page — authentication errors (401) must still behave as today (redirect to login).
- Hovering/clicking sidebar and command-palette links behaves as it already does (hover prefetch, unchanged).

## Scope

**In scope:**
- The pages reachable via keyboard shortcuts today: watchlists (`/watchlists`), holdings (`/holdings`), and security detail (`/security/[id]`).
- Making navigation to these pages non-blocking (cheap-load-first / streaming pattern) and rendering shell + skeletons while heavy data loads.
- Prefetching shortcut-target routes and default-watchlist securities so shortcut navigation hits warm cache where possible.
- Preserving today's 401-redirect behavior and error-state rendering.

**Out of scope:**
- A client-side data cache with stale-while-revalidate re-rendering (chosen against: skeletons are simpler and no staleness concerns).
- Other pages (brokers, accounts, settings) — they can adopt the same pattern later.
- Changes to the shortcuts themselves.

## Current state & gap

- `frontend/src/routes/+layout.svelte` mounts the shell (Sidebar + `AppSidebar`) once and only swaps `{@render children()}` — the root layout already survives navigations; the gap is purely in blocking page loads.
- `frontend/src/app.html` sets `data-sveltekit-preload-data="hover"`, so link hover already preloads data; keyboard `goto()` does not prefetch and blocks on server load.
- `frontend/src/routes/holdings/+page.server.ts` fetches all holdings (sequential pagination) plus user preferences before returning — the slowest inhibitor on a shortcut path.
- `frontend/src/routes/holdings/+page.svelte` seeds a page-local `HoldingsService` instance from `data.holdings` and renders from it; no skeleton-driven async path exists yet on these pages.
- `frontend/src/lib/components/layout/app-header.svelte` already renders title skeletons when `isLoading` is passed — reusable for the instant titlebar, but no page currently drives it via streamed/async data.
- SvelteKit server loads currently return plain awaited objects; no streaming (`stream:`/deferred promises) is used anywhere.

## What needs to be done

- Restructure the shortcut pages' server loads so cheap data (titles, persisted table/group config, layout-affecting preferences) resolves immediately and heavy data (holdings rows, security prices, watchlist contents) is delivered as streaming promises (or deferred client-side fetches where a sequential waterfall makes streaming insufficient, e.g. holdings pagination).
- Update pages to render shell + skeletons while streamed values are unresolved, wiring `isLoading`/error paths into the existing services and `app-header`.
- Eagerly prefetch (SPA-level) the default watchlist securities and shortcut-target routes at app start / first keydown.
- Ensure 401s and other `ApiError`s from streamed data still trigger today's redirect/error UX.

## Open questions

- (none — scope and skeleton-first behavior confirmed by the user; the streaming vs. client-fetch split per page is an implementation decision left to ticket planning)

## Definition of done

- [ ] Pressing `w`, `h`, or `1–9`/`0` switches the page immediately (no blank/waiting state on the whole app); titlebar and page structure are visible before data resolves.
- [ ] Real data appears in the page without user action and without re-navigating; skeletons are visible while loading.
- [ ] A failed async data load shows the page's error state (or triggers the 401 login redirect), not a SvelteKit error page.
- [ ] Existing hover-prefetch on sidebar links is unchanged.
