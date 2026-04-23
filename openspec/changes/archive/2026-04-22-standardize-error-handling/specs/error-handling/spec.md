## ADDED Requirements

### Requirement: SvelteKit Error Boundary Display
The frontend application SHALL display a dedicated error boundary page when an API fetch operation fails during server-side load.

#### Scenario: Server-side data fetch fails with 401
- **WHEN** a `+page.server.ts` loader catches an `ApiError` with status 401
- **THEN** the loader clears the `auth_token` cookie
- **AND** throws a SvelteKit `redirect(303, '/auth/login')`
- **AND** the application redirects the user to the login page instead of showing an error boundary.

#### Scenario: Server-side data fetch fails with 500
- **WHEN** a `+page.server.ts` loader catches an `ApiError` with status 500
- **THEN** the loader throws a SvelteKit `error(500, ...)`
- **AND** the application renders the `+error.svelte` UI indicating a server error.

### Requirement: SSR Authentication Forwarding
The frontend application SHALL forward the authentication cookie when fetching data during Server-Side Rendering (SSR).

#### Scenario: SvelteKit loader makes API request
- **GIVEN** a user is authenticated with an `auth_token` cookie
- **WHEN** a `+page.server.ts` loader initializes an API client
- **THEN** the loader MUST read the `auth_token` from SvelteKit's `cookies`
- **AND** pass the token to the API client methods to ensure the backend request is authenticated during SSR.