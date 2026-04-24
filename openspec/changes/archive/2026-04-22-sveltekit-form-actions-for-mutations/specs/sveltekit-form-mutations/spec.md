## ADDED Requirements

### Requirement: Progressive Enhancement for Mutations
The system SHALL use SvelteKit's `use:enhance` directive for all form-based mutations to provide a smooth user experience with JavaScript while maintaining core functionality without it.

#### Scenario: Mutation with JavaScript enabled
- **WHEN** user submits a form with `use:enhance`
- **THEN** the browser performs an asynchronous fetch to the server action
- **AND** the page state updates without a full reload

#### Scenario: Mutation with JavaScript disabled
- **WHEN** user submits a form
- **THEN** the browser performs a standard POST request to the server action
- **AND** the server responds with a full page reload or redirect

### Requirement: Standardized Action Failure Handling
The system SHALL use SvelteKit's `fail` function to return validation errors or operation failures from server actions.

#### Scenario: Validation error in server action
- **WHEN** a server action receives invalid data
- **THEN** it returns a `fail` response with a status code and error details
- **AND** the frontend displays these errors using the `$form` or `form` property

### Requirement: Account Renaming via Form Action
The system SHALL allow users to rename an account using a SvelteKit Form Action.

#### Scenario: Successful account rename
- **WHEN** the user submits the rename form with a new name
- **THEN** the server action calls the backend API to update the account name
- **AND** the page reflects the new name upon success
