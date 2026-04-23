## ADDED Requirements

### Requirement: Authentication via Form Actions
The system SHALL use SvelteKit Form Actions for all authentication mutations (login, signup, logout) to ensure reliable state management and progressive enhancement.

#### Scenario: User submits login form
- **WHEN** user submits the login form
- **THEN** the request is handled by a server-side action in `+page.server.ts`
- **AND** the session cookie is set on the server upon success

#### Scenario: User logs out
- **WHEN** user clicks the logout button or submits a logout form
- **THEN** the request is handled by a server-side action
- **AND** the session cookie is cleared on the server
