## Plan

**Approach:** Implement dedicated persistence for chart snapshots following the established layered domain pattern in `src/market/`. Define `ChartSnapshotModel` with cascade FK to `market_securities` and composite index `(security_id, user_id, captured_at)` alongside an Alembic revision. Expose Pydantic schemas, abstract and SQLAlchemy repositories with ascending sort by `captured_at` and user isolation on delete, DI registration via `svcs`, and authenticated FastAPI endpoints in `src/market/router.py`.

**Files:**
- `src/market/model.py` — modify: Add `ChartSnapshotModel` mapped to `market_chart_snapshots` with columns `id`, `security_id` (FK with CASCADE delete), `user_id`, `drawings` (JSON), `data_window` (JSON), `captured_at`, `created_at`, and composite index `(security_id, user_id, captured_at)`.
- `migrations/versions/<hash>_add_market_chart_snapshots.py` — create: Alembic revision creating `market_chart_snapshots` with foreign key CASCADE, primary key, and composite index on `(security_id, user_id, captured_at)`, revising `62e7d900926e`.
- `src/market/schema.py` — modify: Add `ChartSnapshotCreate` and `ChartSnapshotRead` with `model_config = ConfigDict(from_attributes=True)`.
- `src/market/repository.py` — modify: Add abstract `ChartSnapshotRepository` interface defining `get_by_security_and_user`, `create`, and `delete`.
- `src/market/repository_sqlalchemy.py` — modify: Implement `SqlAlchemyChartSnapshotRepository` and `sqlalchemy_chart_snapshot_repository_factory`.
- `src/market/__init__.py` — modify: Register `ChartSnapshotRepository` factory in `register_market_services`.
- `src/market/router.py` — modify: Add endpoints `GET /securities/{security_id}/snapshots`, `POST /securities/{security_id}/snapshots` (status 201), and `DELETE /securities/{security_id}/snapshots/{snapshot_id}` (status 204).
- `tests/routers/test_chart_snapshots.py` — create: Router and integration tests covering CRUD operations, sorting by `captured_at`, user isolation, and unauthenticated rejection.

**Steps:**
1. In `src/market/model.py`, add `ChartSnapshotModel` mapped to table `market_chart_snapshots` with `id: Mapped[UUID]` (primary key, default `uuid4`), `security_id: Mapped[SecurityId]` (`ForeignKey("market_securities.id", ondelete="CASCADE")`), `user_id: Mapped[UserId]`, `drawings: Mapped[dict[str, Any]]` (`JSON`), `data_window: Mapped[dict[str, Any]]` (`JSON`), `captured_at: Mapped[datetime]` (`DateTime(timezone=True)`, default `func.now()`), `created_at: Mapped[datetime]` (`DateTime(timezone=True)`, default `func.now()`), and `__table_args__ = (Index("ix_market_chart_snapshots_security_user_captured", "security_id", "user_id", "captured_at"),)`.
2. Create Alembic migration `migrations/versions/<hash>_add_market_chart_snapshots.py` revising `62e7d900926e` that creates table `market_chart_snapshots` with the schema above, creates index `ix_market_chart_snapshots_security_user_captured`, and provides corresponding downgrade drops.
3. In `src/market/schema.py`, add `ChartSnapshotCreate(BaseModel)` with fields `drawings: dict[str, Any]`, `data_window: dict[str, Any]`, `captured_at: datetime | None = None`, and `ChartSnapshotRead(BaseModel)` with fields `id: UUID`, `security_id: SecurityId`, `user_id: UserId`, `drawings: dict[str, Any]`, `data_window: dict[str, Any]`, `captured_at: datetime`, `created_at: datetime`, both configured with `model_config = ConfigDict(from_attributes=True)`.
4. In `src/market/repository.py`, define abstract class `ChartSnapshotRepository(ABC)` with methods `get_by_security_and_user(self, security_id: SecurityId, user_id: UserId) -> list[ChartSnapshotRead]`, `create(self, snapshot: ChartSnapshotCreate, security_id: SecurityId, user_id: UserId) -> ChartSnapshotRead`, and `delete(self, snapshot_id: UUID, user_id: UserId) -> None`.
5. In `src/market/repository_sqlalchemy.py`, implement `SqlAlchemyChartSnapshotRepository`:
   - `get_by_security_and_user`: query `ChartSnapshotModel` filtered by `security_id` and `user_id`, ordered by `ChartSnapshotModel.captured_at.asc()`.
   - `create`: persist `ChartSnapshotModel` using `snapshot.captured_at or datetime.now(UTC)` for `captured_at`, commit, refresh, and return validated `ChartSnapshotRead`.
   - `delete`: execute `delete(ChartSnapshotModel).where(ChartSnapshotModel.id == snapshot_id).where(ChartSnapshotModel.user_id == user_id)` and commit.
   - Implement `sqlalchemy_chart_snapshot_repository_factory(container: Container) -> SqlAlchemyChartSnapshotRepository`.
6. In `src/market/__init__.py`, import `ChartSnapshotRepository` and `sqlalchemy_chart_snapshot_repository_factory`, then register the factory in `register_market_services`.
7. In `src/market/router.py`, add routes under `market_router`:
   - `GET /securities/{security_id}/snapshots`: returns `list[ChartSnapshotRead]` from `repo.get_by_security_and_user`.
   - `POST /securities/{security_id}/snapshots`: accepts `ChartSnapshotCreate`, status code 201, returns `ChartSnapshotRead` from `repo.create`.
   - `DELETE /securities/{security_id}/snapshots/{snapshot_id}`: status code 204, calls `repo.delete(snapshot_id, user.id)`, returns `Response(status_code=204)`.
   Ensure all three endpoints require `user: Annotated[User, Depends(current_user)]`.
8. In `tests/routers/test_chart_snapshots.py`, implement integration tests using `auth_client`, `other_user`, `client`, and `db_session`:
   - `test_create_chart_snapshot_success`: POST returns 201 with generated UUID `id` and timestamps.
   - `test_get_chart_snapshots_ordered_by_captured_at`: GET returns snapshots sorted ascending by `captured_at`.
   - `test_delete_chart_snapshot_success`: DELETE returns 204 and removes snapshot from subsequent GET.
   - `test_chart_snapshots_user_isolation`: User B cannot access User A's snapshots via GET or delete User A's snapshots via DELETE.
   - `test_chart_snapshots_unauthenticated_rejection`: Unauthenticated requests to GET, POST, and DELETE return 401 Unauthorized.
   - `test_chart_snapshots_security_cascade_delete`: Deleting `SecurityModel` cascades to remove its snapshots.

**Verification:**
- Migration & Schema: Run `docker compose exec backend uv run alembic upgrade head` to verify migration applies cleanly; verify table and composite index creation.
- POST endpoint: Run `docker compose exec backend uv run pytest tests/routers/test_chart_snapshots.py -k test_create_chart_snapshot_success` to observe 201 status, valid UUID, and timestamp persistence.
- GET endpoint ordering: Run `docker compose exec backend uv run pytest tests/routers/test_chart_snapshots.py -k test_get_chart_snapshots_ordered_by_captured_at` to observe snapshots returned ascending by `captured_at`.
- DELETE endpoint: Run `docker compose exec backend uv run pytest tests/routers/test_chart_snapshots.py -k test_delete_chart_snapshot_success` to observe 204 status and snapshot removal.
- User isolation: Run `docker compose exec backend uv run pytest tests/routers/test_chart_snapshots.py -k test_chart_snapshots_user_isolation` to observe that snapshots cannot be retrieved or deleted across users.
- Unauthenticated rejection: Run `docker compose exec backend uv run pytest tests/routers/test_chart_snapshots.py -k test_chart_snapshots_unauthenticated_rejection` to observe 401 Unauthorized across all snapshot endpoints.
- Quality gates:
  - `docker compose exec backend uv run ruff check` -> 0 lint warnings
  - `docker compose exec backend uv run ty check` -> 0 type errors
  - `docker compose exec backend uv run ruff format --check` -> code formatting passes
  - `docker compose exec backend uv run pytest tests/routers/test_chart_snapshots.py` -> all tests pass

**Risks / watch-outs:**
- Migration head alignment: Revision must specify `down_revision = '62e7d900926e'` to prevent branched migration history.
- Timezone-aware timestamps: Ensure `captured_at` is always stored as timezone-aware UTC (`DateTime(timezone=True)`) whether provided in request payload or defaulted via `datetime.now(UTC)`.
- Isolation in repository delete: The DELETE query must filter on both `id == snapshot_id` and `user_id == user_id` to guarantee cross-user deletion is impossible.
