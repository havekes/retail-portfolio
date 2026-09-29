-- Coarse 30-day retention TTL policy for ClickStack telemetry tables.
-- Applied to the default ClickHouse database. Refined in F-OBS-T16.

ALTER TABLE default.otel_logs MODIFY TTL toDateTime(Timestamp) + INTERVAL 30 DAY;
ALTER TABLE default.otel_traces MODIFY TTL toDateTime(Timestamp) + INTERVAL 30 DAY;
ALTER TABLE default.otel_metrics_gauge MODIFY TTL toDateTime(TimeUnix) + INTERVAL 30 DAY;
ALTER TABLE default.otel_metrics_histogram MODIFY TTL toDateTime(TimeUnix) + INTERVAL 30 DAY;
ALTER TABLE default.otel_metrics_sum MODIFY TTL toDateTime(TimeUnix) + INTERVAL 30 DAY;
ALTER TABLE default.otel_metrics_summary MODIFY TTL toDateTime(TimeUnix) + INTERVAL 30 DAY;
ALTER TABLE default.otel_metrics_exponential_histogram MODIFY TTL toDateTime(TimeUnix) + INTERVAL 30 DAY;
