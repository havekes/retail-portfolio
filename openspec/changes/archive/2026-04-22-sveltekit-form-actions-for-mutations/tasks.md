## 1. Authentication Refactoring

- [x] 1.1 Implement `login` action in `frontend/src/routes/auth/login/+page.server.ts`
- [x] 1.2 Refactor `frontend/src/lib/components/auth/login-form.svelte` to use SvelteKit form actions and `use:enhance`
- [x] 1.3 Remove `frontend/src/lib/components/auth/login-form.svelte.ts` and its direct `authService` call
- [x] 1.4 Implement `signup` action in `frontend/src/routes/auth/signup/+page.server.ts`
- [x] 1.5 Refactor signup form to use SvelteKit form actions and `use:enhance`
- [x] 1.6 Implement `logout` action in `frontend/src/routes/auth/logout/+page.server.ts` or a global action

## 2. Account Mutations Refactoring

- [x] 2.1 Implement `renameAccount` action in `frontend/src/routes/accounts/[id]/+page.server.ts`
- [x] 2.2 Modify `frontend/src/lib/components/forms/editable-title.svelte` to support form-based submissions or optional action-based save
- [x] 2.3 Refactor `frontend/src/routes/accounts/[id]/+page.svelte` to use the new action for renaming accounts
- [x] 2.4 Verify progressive enhancement by testing renaming with JavaScript disabled

## 3. Standardization and Validation

- [x] 3.1 Standardize error responses using SvelteKit's `fail()` function in all newly created actions
- [x] 3.2 Ensure validation and API error messages are displayed correctly in the UI using the `form` prop
- [x] 3.3 Audit the application for any other remaining client-side mutations and refactor them to use Form Actions
