## ADDED Requirements

### Requirement: Secure Cookie Authentication
The system SHALL use HttpOnly cookies to store authentication tokens instead of client-side storage.

#### Scenario: Successful login
- **WHEN** user successfully logs in
- **THEN** system responds with an HttpOnly, Secure cookie containing the auth token

#### Scenario: SSR Authenticated State
- **WHEN** user requests a protected page
- **THEN** SvelteKit server hook extracts user details from the cookie before rendering

### Requirement: Protected Route Redirects
The system SHALL prevent unauthorized access to protected routes without content flashing.

#### Scenario: Unauthorized access attempt
- **WHEN** an unauthenticated user attempts to load a protected route (e.g., /account)
- **THEN** system immediately redirects them to /login with a 302 status code during server-side rendering
