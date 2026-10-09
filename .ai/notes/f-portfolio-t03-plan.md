## Plan

**Approach:** Implement `PATCH /portfolios/{portfolio_id}` in FastAPI with `PortfolioUpdateRequest` schema, service, and SQLAlchemy repository methods with ownership checks; add `updatePortfolio` and `deletePortfolio` to frontend `PortfolioClient` with unit tests; and redesign `/portfolios` into a row-based list using `EditableTitle`, an actions dropdown menu, and `ConfirmationModal` matching `accounts-list-item`, while fixing the missing `expanded_account_ids` in `page.svelte.test.ts`.

**Files:**
- `src/account/schema.py` — modify: Add `PortfolioUpdateRequest` schema with non-empty `name` validation (`min_length=1`).
- `src/account/repository.py` — modify: Add abstract `update` method on `PortfolioRepository`.
- `src/account/repository_sqlalchemy.py` — modify: Implement `update` on `SqlAlchemyPortfolioRepository` updating name and returning `PortfolioRead`.
- `src/account/service/portfolio.py` — modify: Add `update_portfolio` to `PortfolioService` checking existence and delegating to repository.
- `src/account/router.py` — modify: Add `PATCH /portfolios/{portfolio_id}` endpoint with user ownership verification.
- `tests/routers/test_portfolios.py` — modify: Add unit tests for successful rename, 404 for not found/unowned, and 422 validation error.
- `frontend/src/lib/types/portfolio.ts` — modify: Add `PortfolioUpdatePayload` interface.
- `frontend/src/lib/api/portfolioClient.ts` — modify: Add `updatePortfolio` and `deletePortfolio` methods.
- `frontend/src/lib/api/portfolioClient.test.ts` — modify: Add unit tests for `updatePortfolio` and `deletePortfolio` (headers, methods, payloads, errors).
- `frontend/src/routes/portfolios/portfolio-list-item.svelte` — create: Component for row-based portfolio item with `EditableTitle`, dropdown menu, and `ConfirmationModal`.
- `frontend/src/routes/portfolios/+page.svelte` — modify: Redesign to row-based list container using `PortfolioListItem`, managing rename and delete state.
- `frontend/src/routes/portfolios/page.svelte.test.ts` — modify: Add `expanded_account_ids: []` to `makeData`, update and add unit tests for list rendering, title link, inline rename, and delete confirmation.

**Steps:**
1. In `src/account/schema.py`, add `PortfolioUpdateRequest` with `name: str = Field(..., min_length=1)`.
2. In `src/account/repository.py` and `src/account/repository_sqlalchemy.py`, add `update(portfolio_id: PortfolioId, name: str) -> PortfolioRead` on `PortfolioRepository` and `SqlAlchemyPortfolioRepository`.
3. In `src/account/service/portfolio.py`, add `update_portfolio(portfolio_id, portfolio_update)` verifying existence with `get_portfolio`.
4. In `src/account/router.py`, add `@portfolio_router.patch("/{portfolio_id}")` with `current_user`, fetching portfolio, checking ownership via `authorization_api.check_entity_owned_by_user(user, portfolio)`, and calling `update_portfolio`.
5. In `tests/routers/test_portfolios.py`, add router tests covering:
   - successful rename (200 OK, updated name in response and subsequent list),
   - non-existent portfolio (404),
   - unowned portfolio (404),
   - invalid payload with empty or missing name (422).
6. In `frontend/src/lib/types/portfolio.ts`, export `PortfolioUpdatePayload` interface with `name: string`.
7. In `frontend/src/lib/api/portfolioClient.ts`, add `updatePortfolio(id, payload, token)` using `this.patch` and `deletePortfolio(id, token)` using `this.delete`.
8. In `frontend/src/lib/api/portfolioClient.test.ts`, add test cases for `updatePortfolio` (correct URL, PATCH method, payload, auth header, ApiError) and `deletePortfolio` (correct URL, DELETE method, auth header, ApiError).
9. Create `frontend/src/routes/portfolios/portfolio-list-item.svelte` mirroring `accounts-list-item.svelte`:
   - Row container styled with `rounded-lg bg-muted p-4`.
   - `EditableTitle` component bound to `portfolio.name`, `href={'/holdings?portfolio_id=' + portfolio.id}`, `showEditButton={false}`, and `isEditing` bound to local state.
   - Metadata showing account count (`{count} {account/accounts}`) and created date (`Created {formatDate(created_at)}`).
   - Actions dropdown (`DropdownMenu`) with `EllipsisVertical` trigger, containing "Rename" (activates title editing) and destructive "Delete portfolio" (opens `ConfirmationModal`).
   - `ConfirmationModal` prompting before deletion.
10. Update `frontend/src/routes/portfolios/+page.svelte` to use a vertical list layout (`space-y-3`) rendering `PortfolioListItem` for each item, wired to `handleRename` and `handleDelete` calling `portfolioClient`, preserving the empty state.
11. In `frontend/src/routes/portfolios/page.svelte.test.ts`:
   - Add `expanded_account_ids: []` in `makeData` to fix Gate 0 svelte-check failure.
   - Mock `portfolioClient` (`updatePortfolio`, `deletePortfolio`).
   - Update tests for title link to `/holdings?portfolio_id={id}`.
   - Add tests for triggering rename (via dropdown/EditableTitle), asserting API call and UI update.
   - Add tests for opening delete confirmation modal, confirming deletion, asserting API call and item removal, and cancelling without deletion.
12. Run `./scripts/agent-test` to verify Gate 0 passes and all backend and frontend test suites pass.

**Verification:**
- Backend tests: `./scripts/agent-test tests/routers/test_portfolios.py` — verify all portfolio router tests pass, including rename 200, 404, and 422.
- Frontend API client tests: `./scripts/agent-test frontend/src/lib/api/portfolioClient.test.ts` — verify all client unit tests pass for GET, POST, PATCH, and DELETE.
- Frontend UI tests: `./scripts/agent-test frontend/src/routes/portfolios/page.svelte.test.ts` — verify list rendering, title link, inline rename, and delete confirmation pass.
- Pre-flight Gate 0: `./scripts/agent-test --gate0-only` — verify svelte-check and ruff/mypy pass without errors.
- Full suite: `./scripts/agent-test` — verify full regression passes.

**Risks / watch-outs:**
- `page.svelte.test.ts` currently fails Gate 0 svelte-check due to missing `expanded_account_ids` in `makeData`; updating `makeData` immediately unblocks frontend Gate 0.
- Ensure `EditableTitle`'s `isEditing` toggle works smoothly from the dropdown item action without blur/click collision.
