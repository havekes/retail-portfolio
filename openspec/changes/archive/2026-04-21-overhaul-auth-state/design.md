## Context

Authentication currently uses `sessionStorage` to hold JWTs, making them accessible to client-side scripts. SvelteKit components manually subscribe to a custom `userStore` for authorization. This approach is vulnerable to XSS and causes content flashing on protected routes because authorization checks happen on the client after the initial HTML delivery.

## Goals / Non-Goals

**Goals:**
- Improve security by storing tokens in `HttpOnly` cookies.
- Prevent content flashing by handling authorization in `src/hooks.server.ts`.
- Simplify frontend state by leveraging SvelteKit's `$page.data.user`.

**Non-Goals:**
- Changing the database schema for users.
- Implementing OAuth or third-party identity providers.

## Decisions

1. **Backend Sets Cookie**: FastAPI will set the `auth_token` as an `HttpOnly` cookie upon successful login. Rationale: It's simpler than building a SvelteKit BFF proxy for all API endpoints.
2. **FastAPI Reads Cookie**: FastAPI's auth dependency will be updated to read the token from the cookie instead of just the `Authorization` header.
3. **Frontend API Client**: `apiClient.ts` will use `credentials: 'include'` for browser fetches. During SSR, `apiClient.ts` will manually forward the cookie in the `Authorization` header since `event.fetch` to an external origin doesn't send cookies automatically by default.
4. **SvelteKit State**: `hooks.server.ts` will parse the cookie and populate `event.locals.user`. `+layout.server.ts` will expose it to `$page.data.user`.

## Risks / Trade-offs

- [CORS issues] → Strict configuration of `allow_credentials=True` and `allowed_origins` in FastAPI.
- [CSRF attacks] → Use `SameSite=Lax` for the auth cookie to mitigate cross-site request forgery while allowing same-site navigation.
