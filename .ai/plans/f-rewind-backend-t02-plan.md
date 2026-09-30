## Plan

**Approach:** Extend the existing `ApiClient` infrastructure to implement `SnapshotsService`, mirroring the established patterns in `notesService.ts` and `alertsService.ts`. The client communicates with backend endpoints under `/market/securities/${securityId}/snapshots`, ensuring type compatibility between backend responses and `RewindSnapshot`. Vitest unit tests will mock `global.fetch` to thoroughly validate URL construction, HTTP verbs, payload handling, token forwarding, and error states. (Alternative considered: standalone fetch wrapper function without `ApiClient`; rejected to maintain uniform error handling, base URL resolution, credentials forwarding, and consistency with neighboring services).

**Files:**
- `frontend/src/lib/utils/finance/rewind.ts` — modify: add optional backend response fields (`security_id?: string; user_id?: string; created_at?: string;`) to `RewindSnapshot` interface for full backend schema compatibility.
- `frontend/src/lib/api/snapshotsService.ts` — create: implement `SnapshotsService` extending `ApiClient`, define `ChartSnapshotCreateRequest`, and export factory `getSnapshotsService` and singleton `snapshotsService`.
- `frontend/src/lib/api/snapshotsService.test.ts` — create: unit tests for all service methods covering URL construction, HTTP verbs, payload handling, token forwarding, error states, and factory instantiation.

**Steps:**
1. In `frontend/src/lib/utils/finance/rewind.ts`, enhance the `RewindSnapshot` interface with optional fields `security_id?: string`, `user_id?: string`, and `created_at?: string` matching backend `ChartSnapshotRead` attributes while maintaining full backward compatibility.
2. In `frontend/src/lib/api/snapshotsService.ts`, define the `ChartSnapshotCreateRequest` interface (`drawings: RewindDrawings`, `data_window: RewindDataWindow`, `captured_at?: string | null`) and implement the `SnapshotsService` class extending `ApiClient`:
   - `getSnapshots(securityId: string, token?: string | null): Promise<RewindSnapshot[]>` calling `this.get('/market/securities/${securityId}/snapshots', {}, token)`.
   - `createSnapshot(securityId: string, request: ChartSnapshotCreateRequest, token?: string | null): Promise<RewindSnapshot>` calling `this.post('/market/securities/${securityId}/snapshots', request, {}, token)`.
   - `deleteSnapshot(securityId: string, snapshotId: string, token?: string | null): Promise<void>` calling `this.delete<void>('/market/securities/${securityId}/snapshots/${snapshotId}', {}, token)`.
   - Export factory function `getSnapshotsService(customFetch?: typeof fetch)` and singleton instance `snapshotsService = getSnapshotsService()`.
3. In `frontend/src/lib/api/snapshotsService.test.ts`, write a comprehensive Vitest test suite mocking `global.fetch`:
   - Test `getSnapshots`: verify GET request to `/api/v1/market/securities/${securityId}/snapshots`, correct deserialization into `RewindSnapshot[]`, header forwarding when `token` is provided, and error propagation (`ApiError`) on HTTP error status.
   - Test `createSnapshot`: verify POST request to `/api/v1/market/securities/${securityId}/snapshots` with body containing `drawings`, `data_window`, and `captured_at`, return of created snapshot matching `RewindSnapshot`, token forwarding, and error propagation.
   - Test `deleteSnapshot`: verify DELETE request to `/api/v1/market/securities/${securityId}/snapshots/${snapshotId}`, clean resolution on 204 No Content, token forwarding, and error propagation.
   - Test factory and singleton: verify `getSnapshotsService(customFetch)` passes custom fetch to `ApiClient`, and `snapshotsService` is an instance of `SnapshotsService`.
4. Run verification and quality checks:
   - Execute Vitest tests: `docker compose exec frontend npm run test:run -- src/lib/api/snapshotsService.test.ts` (and `src/lib/utils/finance/rewind.test.ts`).
   - Run type checking: `docker compose exec frontend npm run check`.
   - Run linter and formatting checks: `docker compose exec frontend npm run lint` and `docker compose exec frontend npm run format`.

**Verification:**
- GET endpoint: Run `docker compose exec frontend npm run test:run -- src/lib/api/snapshotsService.test.ts` to verify `snapshotsService.getSnapshots(securityId)` sends GET to `/market/securities/${securityId}/snapshots` and resolves with `RewindSnapshot[]`.
- POST endpoint: Run `docker compose exec frontend npm run test:run -- src/lib/api/snapshotsService.test.ts` to verify `snapshotsService.createSnapshot(securityId, data)` sends POST to `/market/securities/${securityId}/snapshots` with `drawings`, `data_window`, and `captured_at` and resolves with the created snapshot.
- DELETE endpoint: Run `docker compose exec frontend npm run test:run -- src/lib/api/snapshotsService.test.ts` to verify `snapshotsService.deleteSnapshot(securityId, snapshotId)` sends DELETE to `/market/securities/${securityId}/snapshots/${snapshotId}` and resolves cleanly on 204.
- Shape compatibility: Run `docker compose exec frontend npm run check` to verify TypeScript confirms returned snapshot shape conforms to `RewindSnapshot` interface (`id`, `captured_at`, `drawings`, `data_window`).
- Unit tests & Quality gates:
  - `docker compose exec frontend npm run test:run -- src/lib/api/snapshotsService.test.ts` -> 100% pass rate across all methods.
  - `docker compose exec frontend npm run check` -> 0 type errors.
  - `docker compose exec frontend npm run lint` -> 0 lint warnings/errors.
  - `docker compose exec frontend npm run test:run` -> full test suite passes.

**Risks / watch-outs:**
- HTTP 204 response handling: `ApiClient.delete` returns `undefined` for 204 No Content responses instead of invoking `response.json()`. Unit tests must mock status 204 to ensure `deleteSnapshot` cleanly resolves without JSON parse errors.
- Token parameter consistency: Ensure optional `token?: string | null` is forwarded to `this.get`, `this.post`, and `this.delete` to support both client-side cookie authentication and server-side SvelteKit token forwarding.
