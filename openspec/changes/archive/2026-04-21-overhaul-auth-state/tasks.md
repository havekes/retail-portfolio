## 1. Backend Changes

- [x] 1.1 Update `src/auth/router.py` `auth_login` endpoint to set an `HttpOnly`, `Secure` cookie named `auth_token`.
- [x] 1.2 Update `src/auth/router.py` to add an `auth_logout` endpoint that clears the `auth_token` cookie.
- [x] 1.3 Update `src/auth/api.py` `oauth2_scheme` (or `current_user`) dependency to extract the token from the `auth_token` cookie.
- [x] 1.4 Update `src/main.py` CORS configuration to allow credentials (`allow_credentials=True`) and specify SvelteKit origins.

## 2. Frontend Core Auth

- [x] 2.1 Update `frontend/src/lib/api/apiClient.ts` to use `credentials: 'include'` instead of manually injecting the `Authorization` header for browser fetch requests.
- [x] 2.2 Update `frontend/src/lib/api/apiClient.ts` SSR handling to manually forward the `auth_token` cookie to the backend during `event.fetch`.
- [x] 2.3 Create `frontend/src/hooks.server.ts` to extract the `auth_token` cookie, parse the user payload, and populate `event.locals.user`.
- [x] 2.4 Update `frontend/src/hooks.server.ts` to enforce server-side redirects (to `/login`) for unauthenticated users accessing protected routes.
- [x] 2.5 Create or update `frontend/src/routes/+layout.server.ts` to expose `event.locals.user` to SvelteKit's `$page.data.user`.

## 3. Frontend State Migration

- [x] 3.1 Update `frontend/src/app.d.ts` to type `Locals` and `PageData` for the `user` object.
- [x] 3.2 Refactor `frontend/src/lib/components/auth/login-form.svelte.ts` and `signup-form.svelte.ts` to remove `userStore` calls.
- [x] 3.3 Refactor `frontend/src/lib/components/layout/app-sidebar.svelte` to read user state from `$page.data.user`.
- [x] 3.4 Refactor `frontend/src/lib/components/accounts/accounts-list.svelte.ts` and other components to use `$page.data.user` instead of `userStore`.
- [x] 3.5 Refactor `frontend/src/routes/auth/logout/+page.svelte` to call the backend logout endpoint.
- [x] 3.6 Delete `frontend/src/lib/stores/userStore.ts` and ensure all references are removed.
