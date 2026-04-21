## ADDED Requirements

### Requirement: Unified HTTP Request Interface
The `ApiClient` SHALL provide standardized methods for GET, POST, PATCH, and DELETE requests.

#### Scenario: Successful GET request
- **WHEN** a client calls `get('/endpoint')`
- **THEN** it SHALL include the `Authorization` bearer token from `userStore`
- **AND** it SHALL return the parsed JSON response

### Requirement: Standardized Error Handling
All API interactions SHALL throw a unified `ApiError` when the response is not OK (status code >= 400).

#### Scenario: Handling 404 Not Found
- **WHEN** an API call returns a 404 status
- **THEN** it SHALL throw an `ApiError` with `status: 404` and the error message from the response body

### Requirement: Automatic Session Invalidation
The system SHALL automatically clear the user session when a 401 Unauthorized response is received.

#### Scenario: Token Expiration
- **WHEN** an API call returns a 401 status
- **THEN** it SHALL call `userStore.clearUser()`
- **AND** it SHALL throw an `ApiError` with `status: 401`
