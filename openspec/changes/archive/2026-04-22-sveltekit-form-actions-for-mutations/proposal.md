## Why

Currently, many mutations (like renaming an account or logging in) are handled via direct client-side API calls within components or state classes. This couples the UI tightly to implementation details, makes error handling repetitive, and breaks when JavaScript is disabled. SvelteKit Form Actions provide a standardized, progressively enhanced way to handle mutations that simplifies state management and improves reliability.

## What Changes

- Refactor client-side API calls into SvelteKit Form Actions in `+page.server.ts` files.
- Replace `accountClient.renameAccount` with a form submission in `frontend/src/routes/accounts/[id]`.
- Refactor login, signup, and logout forms to use SvelteKit Form Actions instead of custom state classes and direct service calls.
- Use the `use:enhance` directive to maintain a smooth SPA-like experience while ensuring functionality without JavaScript.
- Standardize error handling and validation messaging using SvelteKit's `fail` and `form` data.

## Capabilities

### New Capabilities
- `sveltekit-form-mutations`: Standardize mutation patterns across the application using SvelteKit Form Actions to ensure progressive enhancement and decoupled API logic.

### Modified Capabilities
- `authentication`: Update the authentication flow (login, signup, logout) to leverage server-side Form Actions instead of client-side service calls.

## Impact

- `frontend/src/routes/accounts/[id]/+page.svelte` and `+page.server.ts`
- `frontend/src/routes/auth/login/+page.svelte`, `+page.server.ts`, and `login-form.svelte`
- `frontend/src/routes/auth/signup/+page.svelte` and `+page.server.ts`
- `frontend/src/routes/auth/logout` logic.
- API client usage in frontend components (reduction).
