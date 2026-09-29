# HyperDX saved queries & dashboard (F-OBS-T20)

Version-controlled copy of the analysis workflow described in `docker/observability/README.md`
section 8. Everything in this directory is optional tooling: the overlay (§1) is the only
requirement, and the raw ClickHouse SQL in each file is runnable with
`docker compose exec clickstack clickhouse-client` even when the HyperDX UI is empty.

This directory exists because the HyperDX team state lives in the `clickstack_mongo_data` volume:
a `docker compose ... down -v` wipe (README §7) removes users, saved searches and dashboards.
The files here are the recovery path.

## Contents

| File | What it is |
| --- | --- |
| `saved-queries/01-deploy-verification.json` | Deploy verification search over `portfolio.sync.completed` (`trigger`, `user_id`, `deploy_id`). |
| `saved-queries/02-anomaly-cohorts.json` | Anomaly cohort search over `market.data.fetched` (`provider` × `cache_state` × `freshness_lag_ms`). |
| `saved-queries/03-cross-process-failure-tracing.json` | `huey.task` failure search by `error_slug` plus the `trace_id` lookup that opens the whole trace. |
| `saved-queries/04-frontend-error-correlation.json` | Error-inbox search over `exception.type` plus the toast `correlation_id` trace lookup. |
| `dashboard.json` | Minimal three-panel dashboard in the HyperDX UI export format (p95 sync duration by broker, sync error rate, queue-depth signpost). |

Naming convention: `<NN>-<scenario-slug>.json`, numbered so the directory lists the scenarios in
workflow order.

## Saved searches: what a file carries

HyperDX's saved-search documents are `{name, sourceId, select, where, whereLanguage, orderBy, tags,
filters}` (see the pinned build's OpenAPI docs). The pinned ClickStack image (`2.39.1`) has **no UI
"export saved search" action**, so there is nothing to copy verbatim: each file here is the
reviewable source of truth and carries

- `purpose` — the operator question it answers,
- `hyperdx` — the exact search fields (`where` in Lucene attribute syntax from
  `docs/field-dictionary.md` §Querying, plus `select`, `orderBy`, `tags`),
- `operator_notes` — filters to add while investigating, and the waiting/caveat steps,
- `clickhouse_sql` — the same question as plain SQL over `default.otel_traces`, so results can be
  confirmed without the UI,
- `expected_result` and `sampling_and_retention` — what a result looks like and how sampling/TTL
  (README §5 and §6) qualify it.

### Recreate a saved search in the UI

1. Open the search page (`/search`) on the trace source, set the time range, and paste `where`
   into the WHERE box (switch it to Lucene).
2. Add the `select` columns and `orderBy` from the same file.
3. **Save** the search under the file's `name` and tag it with the file's `tags`.
4. Confirm the result with the file's `clickhouse_sql`; the two must agree.

### Create it through the REST API (optional)

The pinned build also serves an external API at `/api/v2` (Swagger UI at `/api/v2/docs`) with
`POST /api/v2/saved-searches`. It authenticates with a **Personal API Access Key** (HyperDX →
Team Settings → API & Agents), not the team ingestion `HYPERDX_API_KEY`. The request body is the
file's `hyperdx` fields plus the team's `sourceId`:

```bash
# sourceId: Team Settings -> Sources, or GET /api/v2/sources
jq '.hyperdx + {name: .name, sourceId: "<source-id>"}' \
  docker/observability/hyperdx/saved-queries/01-deploy-verification.json | \
  curl -sS -X POST http://localhost:8080/api/v2/saved-searches \
    -H "Authorization: Bearer <personal-access-key>" \
    -H "Content-Type: application/json" --data-binary @-
```

The descriptive keys (`scenario`, `purpose`, `clickhouse_sql`, ...) are ignored by the API; the
`hyperdx` block plus `name` is the import payload.

## Dashboard: export format and import

`dashboard.json` is written in HyperDX's own dashboard export format (`"version": "0.1.0"`), the
same document produced by **Export Dashboard** and consumed by **Import Dashboard**
(`/dashboards/import`). In that format `source` and `connection` are referenced **by name**; the
import flow shows a mapping step where each unresolved name is pointed at this instance's data
source/connection. The two `"<clickhouse-connection-name>"` placeholders must be mapped there
(or replaced with the real name before import).

Export it from the UI again after changing a tile (`Dashboards → ⋯ → Export Dashboard`) and keep
the diff to the query text: the UI always emits server-assigned tile ids and its own ordering, so
byte-level equality with a fresh export is not achievable. The tile ids committed here
(`000000000000000000000001`, ...) are deterministic placeholders so this file stays reviewable.

The dashboard is deliberately minimal (README §8.3). Queue depth has no wide event by design —
it is the Prometheus `queue_depth` gauge and the Huey dashboard at `/worker/api` (README §4) — so
the third panel is a signpost instead of a fabricated query.

## Verification status

- Every `clickhouse_sql` / `sqlTemplate` in this directory was parsed and executed against a
  minimal `default.otel_traces` schema (`Timestamp`, `ServiceName`, `SpanAttributes`,
  `ResourceAttributes`) in the pinned image via `clickhouse-local`, with zero rows: the queries
  are valid ClickHouse, and they return rows once dev data exists (README §6 burst or normal
  usage).
- `dashboard.json` was validated against the pinned build's own dashboard import schema
  (`@hyperdx/common-utils` `dashboardSchema`, `version 0.1.0`), which is what the import page uses.
- The repo-level docs-consistency test (`tests/observability/test_field_dictionary.py`) pins the
  dictionary and these files together; it needs no network or containers.