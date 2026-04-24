## 1. Core API Layer Consolidation

- [x] 1.1 Rename `src/lib/api/baseClient.ts` to `src/lib/api/apiClient.ts` and rename the class to `ApiClient`
- [x] 1.2 Update `ApiClient` to include robust 401 handling and standardized error parsing
- [x] 1.3 Ensure `ApiClient` throws a unified `ApiError` (merged from `ApiError` and `APIError`)
- [x] 1.4 Update `accountClient.ts` and `brokerClient.ts` to extend `ApiClient`

## 2. Service Migration

- [x] 2.1 Migrate `src/lib/services/accountService.ts` to `src/lib/api/accountService.ts` and update it to extend `ApiClient`
- [x] 2.2 Migrate `src/lib/services/aiService.ts` to `src/lib/api/aiService.ts` and update it to extend `ApiClient`
- [x] 2.3 Migrate `src/lib/services/alertsService.ts` to `src/lib/api/alertsService.ts` and update it to extend `ApiClient`
- [x] 2.4 Migrate `src/lib/services/authService.ts` to `src/lib/api/authService.ts` and update it to extend `ApiClient`
- [x] 2.5 Migrate `src/lib/services/documentsService.ts` to `src/lib/api/documentsService.ts` and update it to extend `ApiClient`
- [x] 2.6 Migrate `src/lib/services/indicatorsService.ts` to `src/lib/api/indicatorsService.ts` and update it to extend `ApiClient`
- [x] 2.7 Migrate `src/lib/services/marketService.ts` to `src/lib/api/marketService.ts` and update it to extend `ApiClient`
- [x] 2.8 Migrate `src/lib/services/notesService.ts` to `src/lib/api/notesService.ts` and update it to extend `ApiClient`

## 3. Consumer Updates and Cleanup

- [x] 3.1 Search and update all imports of `BaseService` or `APIError` to use `ApiClient` or `ApiError` from `$lib/api`
- [x] 3.2 Search and update all imports from `$lib/services/*` to `$lib/api/*`
- [x] 3.3 Verify that 401 handling works as expected across all migrated clients
- [x] 3.4 Delete `src/lib/services/` directory
- [x] 3.5 Run tests and linting to ensure no regressions
