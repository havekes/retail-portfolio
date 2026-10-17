-- Per-event-class retention TTL policy for the ClickStack telemetry tables.
-- Applied to the default ClickHouse database. Introduced in F-OBS-T16, replacing
-- the coarse 30-day defaults from F-OBS-T01.
--
-- `default.otel_traces` uses a row-level TTL expression keyed on the wide-event
-- name (`SpanAttributes['event.name']`, stamped by every emitter -- see
-- docs/field-dictionary.md), so each event class expires on its own tier:
--   market.cache.accessed     7d   high-volume cache probes, cheapest to lose
--   http.request             14d   HTTP request boundaries
--   market.data.fetched      14d   upstream provider fetches
--   ws.delivery              14d   websocket deliveries
--   alert.evaluated          30d   alert evaluation history
--   auth.event               30d   security/audit trail
--   huey.task                30d   background task outcomes
--   portfolio.sync.completed 30d   sync history
--   portfolio.sync.failed    30d   sync failures
--   <anything else>          30d   fallback tier
-- Logs keep 30 days; metrics keep 14 days. Tiers are deliberately explicit and
-- tunable; keep them in sync with docker/observability/README.md
-- § "Retention & TTL Policy".

ALTER TABLE default.otel_traces MODIFY TTL toDateTime(Timestamp) + toIntervalDay(
    multiIf(
        SpanAttributes['event.name'] = 'market.cache.accessed', 7,
        SpanAttributes['event.name'] IN ('http.request', 'market.data.fetched', 'ws.delivery'), 14,
        30
    )
);

ALTER TABLE default.otel_logs MODIFY TTL toDateTime(Timestamp) + INTERVAL 30 DAY;

ALTER TABLE default.otel_metrics_gauge MODIFY TTL toDateTime(TimeUnix) + INTERVAL 14 DAY;
ALTER TABLE default.otel_metrics_histogram MODIFY TTL toDateTime(TimeUnix) + INTERVAL 14 DAY;
ALTER TABLE default.otel_metrics_sum MODIFY TTL toDateTime(TimeUnix) + INTERVAL 14 DAY;
ALTER TABLE default.otel_metrics_summary MODIFY TTL toDateTime(TimeUnix) + INTERVAL 14 DAY;
ALTER TABLE default.otel_metrics_exponential_histogram MODIFY TTL toDateTime(TimeUnix) + INTERVAL 14 DAY;
