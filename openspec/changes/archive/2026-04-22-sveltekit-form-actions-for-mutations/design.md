## Context

The application currently uses Svelte 5's `$state` and custom classes (like `LoginFormState`) to manage mutation state and client-side API calls. While functional, this approach duplicates loading and error logic and bypasses SvelteKit's built-in form handling capabilities, which provide better progressive enhancement and simpler server-side integration.

## Goals / Non-Goals

**Goals:**
- Move mutation logic from components and state classes to `+page.server.ts` actions.
- Use SvelteKit's `use:enhance` directive for smooth client-side updates.
- Standardize error handling and validation feedback using SvelteKit's `fail` function.
- Ensure core flows (authentication, renaming accounts) work without client-side JavaScript.

**Non-Goals:**
- Refactoring the backend API endpoints.
- Changing the overall UI design (except where necessary for form integration).
- Refactoring all GET requests (loaders) unless they are affected by the form actions.

## Decisions

### 1. Use SvelteKit Form Actions in `+page.server.ts`
**Rationale:** This is the standard SvelteKit pattern for handling mutations. It decouples the UI from the API implementation and provides a clear separation of concerns by keeping API calls on the server.
**Alternatives:** 
- **Direct client-side calls (current state):** Tightly coupled UI and API logic, no progressive enhancement, and requires manual state management for loading/errors.
- **SvelteKit API routes (+server.ts):** Requires manual fetch calls from the client, similar to direct API calls.

### 2. Implement Progressive Enhancement with `use:enhance`
**Rationale:** Provides a fast, SPA-like experience when JavaScript is available while maintaining reliability when it is not.
**Alternatives:** 
- **Standard form submission:** Causes full page reloads on every mutation, leading to a sub-optimal user experience.

### 3. Standardize Error Handling via `fail()`
**Rationale:** Using SvelteKit's `fail()` function allows us to return structured error data that is automatically populated in the `form` prop of the page. This simplifies UI logic for displaying validation errors.
**Alternatives:** 
- **Custom error state management:** Results in inconsistent error handling across different parts of the application.

## Risks / Trade-offs

- **[Risk]** Refactoring `EditableTitle` might be complex as it currently uses a callback.
  - **Mitigation:** Modify `EditableTitle` to optionally accept a form-based save mechanism or wrap it in a form that submits the new value.
- **[Risk]** Loss of granular loading states in custom classes.
  - **Mitigation:** Use SvelteKit's `$navigating` or the `submitting` state from `use:enhance` to manage UI loading indicators.
