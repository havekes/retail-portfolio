## Plan

**Approach:**
Implement the dedicated `/portfolios` route using SvelteKit's standard SSR server loader pattern backed by a new `getPortfolios()` method on `PortfolioClient` (which queries backend `GET /portfolios/`). Render the portfolios on `/portfolios` using `PageHeader`, responsive portfolio cards displaying name, account count, and creation date, and an empty state when no portfolios exist. Wire the "Portfolios" item into `app-sidebar-actions.svelte` (with `Briefcase` icon and `p` badge) and add the global `p`/`P` shortcut and eager prefetching in `+layout.svelte`, matching the existing `w`/`h` navigation patterns.

**Files:**
- `frontend/src/lib/types/portfolio.ts` — modify: extend `Portfolio` interface with `user_id?: string`, `created_at?: string | null`, and `deleted_at?: string | null` matching backend `PortfolioRead`.
- `frontend/src/lib/api/portfolioClient.ts` — modify: add `getPortfolios(token?: string | null): Promise<Portfolio[]>` method to `PortfolioClient`.
- `frontend/src/lib/api/portfolioClient.test.ts` — create: unit tests for `PortfolioClient` covering `getPortfolios` and `createPortfolio` endpoints, token headers, and error handling.
- `frontend/src/routes/portfolios/+page.server.ts` — create: server load function calling `getPortfolioClient(fetch).getPortfolios(token)`, handling 401 redirect via `deleteAuthCookie` to `/auth/login?clear_session=true` and error re-throw.
- `frontend/src/routes/portfolios/page.server.test.ts` — create: unit tests for `+page.server.ts` load function covering successful load, 401 auth redirect, and error propagation.
- `frontend/src/routes/portfolios/+page.svelte` — create: portfolio list page rendering `PageHeader`, responsive portfolio cards (name, account count, formatted created date), and empty state.
- `frontend/src/routes/portfolios/page.svelte.test.ts` — create: component unit tests for `/portfolios` page covering rendering cards with name, account count, created date, and empty state.
- `frontend/src/lib/components/layout/app-sidebar-actions.svelte` — modify: add "Portfolios" item with `Briefcase` icon, shortcut hint `p`, and link to `resolve('/portfolios')`.
- `frontend/src/lib/components/layout/app-sidebar.test.ts` — modify: add tests asserting "Portfolios" action link renders with 'p' shortcut hint, links to `/portfolios`, and hides shortcut badge in collapsed rail.
- `frontend/src/routes/+layout.svelte` — modify: add 'p' / 'P' shortcut handling in `handleKeydown` to prefetch and navigate to `/portfolios`, and prefetch `/portfolios` during initial mounted pass.
- `frontend/src/routes/layout.test.ts` — modify: add tests for pressing 'p' navigating to `/portfolios` and verifying prefetch behavior.

**Steps:**
1. Update `frontend/src/lib/types/portfolio.ts` to include `user_id?: string`, `created_at?: string | null`, and `deleted_at?: string | null` on `Portfolio`.
2. Add `getPortfolios(token?: string | null): Promise<Portfolio[]>` to `PortfolioClient` in `frontend/src/lib/api/portfolioClient.ts` querying `GET /portfolios/`, and add tests in `frontend/src/lib/api/portfolioClient.test.ts`.
3. Create `frontend/src/routes/portfolios/+page.server.ts` implementing `PageServerLoad` to read `auth_token` from cookies, call `portfolioClient.getPortfolios(token)`, handle 401 redirect, and return `{ portfolios }`. Add tests in `frontend/src/routes/portfolios/page.server.test.ts`.
4. Create `frontend/src/routes/portfolios/+page.svelte` with `PageHeader`, list/grid of portfolio cards (`Card.Root` from `$lib/components/ui/card`) showing portfolio name, account count (`${portfolio.accounts.length} ${portfolio.accounts.length === 1 ? 'account' : 'accounts'}`), and created date (`formatDate(portfolio.created_at)` from `$lib/utils/date`), plus an empty state when `portfolios.length === 0`. Add tests in `frontend/src/routes/portfolios/page.svelte.test.ts`.
5. Update `frontend/src/lib/components/layout/app-sidebar-actions.svelte` to include the "Portfolios" MenuItem with `Briefcase` icon from `@lucide/svelte/icons/briefcase`, link `/portfolios`, and shortcut indicator `p`. Update `frontend/src/lib/components/layout/app-sidebar.test.ts` to assert the item and its shortcut indicator.
6. Update `frontend/src/routes/+layout.svelte` to add 'p' / 'P' keyboard shortcut navigation in `handleKeydown` (which already verifies `!isTypingTarget(e.target)` and no modifier keys) and eager prefetching in `onMount`. Update `frontend/src/routes/layout.test.ts` to assert pressing 'p' triggers navigation to `/portfolios`.
7. Run frontend checks and unit test suites (`pnpm check` and `pnpm test:unit`) to confirm build and all tests pass.

**Verification:**
- AC1 (/portfolios renders portfolios with name, account count, created date): Run `pnpm --filter frontend test:unit src/routes/portfolios/page.svelte.test.ts` to verify cards render portfolio name, account count, and formatted created date.
- AC2 (Empty state displayed when no portfolios exist): Run `pnpm --filter frontend test:unit src/routes/portfolios/page.svelte.test.ts` to verify empty state renders when `portfolios` is empty.
- AC3 (App sidebar includes "Portfolios" item with "p" shortcut indicator): Run `pnpm --filter frontend test:unit src/lib/components/layout/app-sidebar.test.ts` to verify "Portfolios" link renders with 'p' shortcut hint and hides badge in collapsed rail.
- AC4 (Pressing "p" navigates to /portfolios): Run `pnpm --filter frontend test:unit src/routes/layout.test.ts` to verify pressing 'p' triggers `goto('/portfolios')` and ignores typing in inputs.
- AC5 (Unit tests for page and sidebar navigation pass): Run `pnpm --filter frontend test:unit src/routes/portfolios/ src/lib/components/layout/app-sidebar.test.ts src/routes/layout.test.ts src/lib/api/portfolioClient.test.ts` and confirm all tests pass.
- AC6 (Build passes and relevant tests pass): Run `pnpm --filter frontend check` and `pnpm --filter frontend test:unit`.

**Risks / watch-outs:**
- Route type generation: SvelteKit route types (`./$types`) for `/portfolios` are generated during build/check (`pnpm check` runs `svelte-kit sync`); ensure new route directory exists before running check.
- Co-implementation with Issue 551: Issue 550 and Issue 551 are planned and executed together on branch `feat/f-portfolio-t01-t02-portfolios-holdings`. The portfolio card layout in 550 should structure the card/links cleanly so Issue 551 can easily make the portfolio card link to `/holdings?portfolio_id=${portfolio.id}`.
