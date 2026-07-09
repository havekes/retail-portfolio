# Frontend Architecture

The frontend is a SvelteKit 2 / Svelte 5 application using SSR (`@sveltejs/adapter-node`), Vite, Tailwind 4, shadcn-svelte primitives, and lightweight-charts.

## Project structure

| Path | Purpose |
|------|---------|
| `frontend/src/routes/` | SvelteKit route pages and server loads |
| `frontend/src/lib/api/` | Domain-oriented API clients |
| `frontend/src/lib/components/` | Domain and presentational components |
| `frontend/src/lib/types/` | Shared domain types |
| `frontend/src/lib/utils/` | Date/money helpers |
| `frontend/src/hooks.server.ts` | JWT cookie validation and auth redirects |
| `frontend/src/app.css` | Tailwind theme tokens |
| `frontend/src/setupTest.ts` | Vitest setup |

## Route structure

Routes use SvelteKit file-based routing. Most authenticated pages are thin shells that fetch data in `+page.server.ts` and render domain components.

| Route | Server (`+page.server.ts`) | Page (`+page.svelte`) | Feature |
|-------|----------------------------|------------------------|---------|
| `/` | `load` → `AccountClient.getAccounts()`; action `renameAccount` | `AccountsList` | Dashboard / portfolio overview |
| `/accounts/[id]` | `load` → account holdings; action `renameAccount` | `HoldingsTable`, `EditableTitle`, totals | Account detail |
| `/brokers` | `load` → broker users via `BrokerService` | `BrokersList` | Connected broker management |
| `/security/[security_id]` | `load` → security + price history | `security-chart`, actions sidebar groups | Security chart / analysis |
| `/auth/login` | action: validate, set cookie | `LoginForm` | Auth |
| `/auth/signup` | action: signup | `SignupForm` | Auth |
| `/auth/logout` | action: clear cookie | tiny page | Auth |
| `/auth/verify-email` | `load` verifies token query param | status display | Email verification |

The root `+layout.server.ts` exposes `user: locals.user` and `+layout.svelte` wraps authenticated pages in `Sidebar.Provider` + `AppSidebar`.

## Server patterns

### Authentication

`frontend/src/hooks.server.ts` validates the `auth_token` JWT cookie on every request using `jose`. Unauthenticated users are redirected to `/auth/login`. Authenticated users hitting `/auth/login` or `/auth/signup` are redirected to `/`.

### Load pattern

`+page.server.ts` fetches data from the backend using SSR `fetch` and a client factory that accepts a custom `fetch`:

```ts
export const load: PageServerLoad = async ({ params, fetch, cookies }) => {
    const token = cookies.get('auth_token');
    const client = getAccountClient(fetch);
    // client may pass token override for SSR
    ...
};
```

On `ApiError` with status `401`, the cookie is deleted and the user is redirected to login.

### Form actions

Mutations use SvelteKit form actions:

```ts
export const actions: Actions = {
    renameAccount: async ({ request, fetch }) => {
        const data = await request.formData();
        // validate
        const client = getAccountClient(fetch);
        await client.renameAccount(id, name);
        return { success: true };
    }
};
```

Some pages use `use:enhance` for optimistic UI while the server action runs.

## API client layer

All clients extend `ApiClient` in `frontend/src/lib/api/apiClient.ts`. It handles base URL selection, cookie credentials, JSON parsing, and `ApiError` throwing.

| Client | File | Backend area |
|--------|------|--------------|
| `AccountClient` | `accountClient.ts` | `/api/accounts`, `/api/portfolios` |
| `AuthService` | `authService.ts` | `/api/auth`, WebSocket ticket |
| `BrokerClient` | `brokerClient.ts` | `/api/integration`, `/api/external` |
| `MarketService` | `marketService.ts` | `/api/market` search/prices/securities |
| `IndicatorsService` | `indicatorsService.ts` | technical indicators |
| `AlertsService` | `alertsService.ts` | price alerts |
| `NotesService` | `notesService.ts` | security notes |
| `DocumentsService` | `documentsService.ts` | security documents |
| `AIService` | `aiService.ts` | AI endpoints |

Each service has a factory (`getXxxService(customFetch?)`) and a default singleton. During SSR the custom `fetch` from `+page.server.ts` is passed so cookies are preserved.

Base URL rules:

- Browser: `VITE_API_BASE_URL` + `/api`
- Server: `VITE_INTERNAL_API_URL` fallback to `VITE_API_BASE_URL` + `/api`

All requests use `credentials: 'include'`. An optional `Authorization: Bearer` override is provided for SSR.

## Component domains

### Accounts

`frontend/src/lib/components/accounts/`

- `accounts-list.svelte`/`accounts-list.svelte.ts` — class-based `AccountsListState` using runes; groups accounts, selection mode, sync via WebSocket, create-portfolio flow.
- `accounts-list-item.svelte`/`accounts-list-item.svelte.ts` — per-item totals cache, sync spinner, `EditableTitle`.
- `holdings-table.svelte` — sortable holdings table with currency display and P/L color coding.

### Brokers

`frontend/src/lib/components/brokers/`

- `brokers-list.svelte`/`brokers-list.svelte.ts` — broker users list / empty state.
- `brokerService.svelte.ts` — Svelte context `BrokerService` factory.
- `connect-broker-modal.svelte.ts`, `sync-accounts-modal.svelte.ts` — modal state classes.

### Actions sidebar

`frontend/src/lib/components/actions-sidebar/` groups live on the `/security/[id]` page.

- `indicator/` — toggle technical indicators, call `IndicatorsService`
- `price-alert/` — create/delete price alerts
- `note/` — security notes list/create/view/delete
- `document/` — security document upload/download
- `ai/` — AI fundamentals, notes summary, portfolio debate
- `holding-group/` — user holdings for the current security

Each group uses:

- `$state` for list/error/loading
- `ModalState<T>` helper (`frontend/src/lib/utils/modal-state.svelte.ts`) for create/view/delete modals
- `SidebarError` for retry UI
- `GroupTitle` shared accordion title

### Charts

`frontend/src/lib/components/charts/`

- `security-chart.svelte` — `lightweight-charts` wrapper: two-pane chart, Heikin-Ashi candlestick, add/remove indicators, average-price line, custom price-alert primitives.
- `plugins/bands-indicator.ts` — Bollinger Bands drawing plugin.
- `plugins/user-price-alerts/*` — lightweight-charts primitive for alert lines with add/remove interactions.

## State management

- **Runes-based:** `$props()`, `$state()`, `$state(new SvelteSet())`, `$derived()`, `$effect()`.
- **Class modules:** `*.svelte.ts` files export state classes (e.g., `AccountsListState`, `ModalState`).
- **Svelte context:** `BrokerService` is provided in root layout and consumed by broker components.
- **WebSocket:** `AccountsListState` gets a signed ticket, opens a WebSocket, and listens for `sync_started/finished/failed`, reconnecting every 5 seconds.

## Type conventions

- Backend fields are mirrored as snake_case (e.g., `account_id`, `security_symbol`, `average_cost`).
- Domain enums in `frontend/src/lib/types/account.ts` provide label helpers.
- Money is represented as `Money = { units: number; nanos: number }` with a `money()` helper for CAD formatting.
- Chart/finance types live in `frontend/src/lib/types/` and `frontend/src/lib/utils/finance/`.

## Style and UI

- Tailwind 4 with custom tokens in `frontend/src/app.css`.
- shadcn-svelte primitives in `frontend/src/lib/components/ui/`.
- Icons from `@lucide/svelte`.
- Dark/light mode via `mode-watcher`.

## Testing

Frontend tests use Vitest with `jsdom`, `@testing-library/svelte`, and `@testing-library/user-event`.

- `vite.config.ts`: test environment is `jsdom`, setup file is `./src/setupTest.ts`.
- Existing tests: `login-form.test.ts`, `signup-form.test.ts`, `apiClient.test.ts`.
- SvelteKit runtime modules (`$app/forms`, `$app/paths`) are manually mocked.

Commands:

```bash
npm run test:run
npm run check
npm run lint
```

## Notable conventions

- Two aliases coexist: SvelteKit `$lib/...` and shadcn-style `@/...`.
- Browser guards (`browser` from `$app/environment`) are used before `WebSocket`, `window`, etc.
- Global search shortcut `Cmd/Ctrl+P` is registered in `+layout.svelte` via `setContext('toggleGlobalSearch', ...)`.
- `EditableTitle` is a reusable inline-edit component that can post to a SvelteKit form action or call `onSave` callback.
