## Why

The current authentication implementation uses `sessionStorage` to store tokens, exposing them to potential Cross-Site Scripting (XSS) attacks. Additionally, relying on client-side state for authorization can cause "content flashing" where protected pages briefly appear before the user is redirected. Moving to `HttpOnly` cookies and server-side validation enhances security and provides a seamless user experience.

## What Changes

- **BREAKING**: Replace client-side `sessionStorage` token storage with secure `HttpOnly` cookies set by the backend.
- Introduce `src/hooks.server.ts` in SvelteKit to validate tokens and populate `event.locals.user` on every server request.
- Perform server-side redirects for unauthorized users attempting to access protected routes.
- **BREAKING**: Remove the custom `userStore.ts` store and replace it with SvelteKit's native `$page.data.user` derived from the server hook.

## Capabilities

### New Capabilities
- `authentication`: Secure, cookie-based authentication, token validation, and server-side route protection.

### Modified Capabilities
None

## Impact

- **Backend Auth API**: FastAPI login/logout routes must set and clear the `HttpOnly` cookie. `oauth2_scheme` must read from the cookie.
- **Frontend API Client**: The SvelteKit `apiClient.ts` will rely on `credentials: 'include'` instead of manually injecting the `Authorization: Bearer` header.
- **Frontend State**: All components using `userStore` will need to be refactored to use `$page.data.user`.
- **CORS**: FastAPI must be configured with `allow_credentials=True` and specific allowed origins.
