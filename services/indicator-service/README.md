# Indicator Service

A small Go sidecar that computes technical indicators over HTTP on request. The
FastAPI backend owns the candle data and the indicator specs; this service is a
stateless calculator — it receives candles plus a list of indicator specs,
computes the requested series, and returns them keyed by spec.

It is built on [`github.com/cinar/indicator/v2`](https://github.com/cinar/indicator)
and is called by the backend's `IndicatorServiceClient`
(`src/market/service.py`).

> **No authentication.** The service exposes no auth and no rate limiting. It is
> intended for the internal Docker network only — never expose it publicly.

## Endpoints

### `GET /health`

Liveness probe. Returns `200` with:

```json
{ "status": "ok", "service": "indicator-service" }
```

Any other method returns `405` with `Allow: GET` and:

```json
{ "error": "method not allowed" }
```

### `POST /compute`

Computes one or more indicator series from a candle array.

**Request body**

| Field        | Type              | Required | Description                                                       |
| ------------ | ----------------- | -------- | ----------------------------------------------------------------- |
| `interval`   | string            | no       | Chart interval. Defaults to `"1d"` when omitted or empty.         |
| `candles`    | `Candle[]`        | yes      | Input OHLCV candles, oldest first.                                |
| `indicators` | `IndicatorSpec[]` | yes      | Indicator specs to compute.                                       |

`Candle`:

| Field    | Type             | Description                                                             |
| -------- | ---------------- | ----------------------------------------------------------------------- |
| `time`   | any JSON value   | Passed through untouched; echoed back on each output point (string or number). |
| `open`   | number           |                                                                         |
| `high`   | number           |                                                                         |
| `low`    | number           |                                                                         |
| `close`  | number           |                                                                         |
| `volume` | number           |                                                                         |

`IndicatorSpec`:

| Field      | Type              | Description                                                                    |
| ---------- | ----------------- | ------------------------------------------------------------------------------ |
| `id`       | string            | Optional. Used as the output key; when empty the `type` is used instead.       |
| `type`     | string            | Indicator type/alias (see below). Case-insensitive, whitespace-trimmed.        |
| `period`   | integer           | Optional parameter (SMA/EMA/BB/RSI, MA variants).                              |
| `fast`     | integer           | Optional MACD fast period.                                                     |
| `slow`     | integer           | Optional MACD slow period.                                                     |
| `signal`   | integer           | Optional MACD signal period.                                                   |
| `stdDev`   | number            | Optional Bollinger Bands standard-deviation multiplier.                        |
| `settings` | object (optional) | Map fallback for the parameter fields above (`period`, `fast`, `slow`, `signal`, `stdDev`). |

Parameter resolution order for every field is: **top-level field (`> 0`) →
`settings` map entry → built-in default**. Values that are zero, missing, or
non-positive fall through to the next source. Numbers in `settings` may be JSON
numbers or numeric strings.

**Response**

`200` with a map of series keyed by each spec's `ResultKey()` — the spec `id`
when set, otherwise the spec `type`:

```json
{ "indicators": { "my-rsi": [ { "time": "2024-01-03", "value": 61.5, "rsi": 61.5 } ] } }
```

Each series is an array of points aligned with the input candle times (see the
table below for the point shape per indicator). When there are too few candles
to compute an indicator, its series is an **empty array** — not an error.

**Errors**

| Status | Cause                                                                 |
| ------ | --------------------------------------------------------------------- |
| `400`  | Invalid JSON body (`{"error": "invalid json body: ..."}`) or unsupported indicator type (`{"error": "unsupported indicator type: <type>"}`). |
| `405`  | Any method other than `POST` — returns `Allow: POST` and `{"error": "method not allowed"}`. |

The request body is capped at **10MB** (`http.MaxBytesReader`); larger bodies
fail to decode and return `400`.

## Supported indicator types

`type` is matched case-insensitively after trimming whitespace, so `MA_50`,
`ma50`, and `" MA50 "` are equivalent.

| Type                    | Aliases                                      | Parameters (default)                          | Series point shape                          |
| ----------------------- | -------------------------------------------- | --------------------------------------------- | ------------------------------------------- |
| `sma`                   | —                                            | `period` (14)                                 | `{time, value}`                             |
| `ema`                   | —                                            | `period` (14)                                 | `{time, value}`                             |
| `bb`                    | `bollinger`, `bollinger_bands`               | `period` (20), `stdDev` (2.0)                 | `{time, middle, upper, lower}`              |
| `macd`                  | —                                            | `fast` (12), `slow` (26), `signal` (9)        | `{time, macd, signal, histogram}`           |
| `rsi`                   | —                                            | `period` (14)                                 | `{time, value, rsi}`                        |
| `obv`                   | —                                            | none                                          | `{time, value}`                             |
| `ma50` (day MA)         | `ma_50`, `ma_50_day`, `50ma`                 | `period` (50), scaled by interval, day unit   | `{time, value}` (SMA)                       |
| `ma200` (day MA)        | `ma_200`, `ma_200_day`, `200ma`              | `period` (200), scaled by interval, day unit  | `{time, value}` (SMA)                       |
| `ma50w` (week MA)       | `ma_50w`, `ma_50_week`, `50wma`              | `period` (50), scaled by interval, week unit  | `{time, value}` (SMA)                       |
| `ma200w` (week MA)      | `ma_200w`, `ma_200_week`, `200wma`           | `period` (200), scaled by interval, week unit | `{time, value}` (SMA)                       |

Notes:

- The `ma*` variants are convenience aliases that compute an SMA over a
  period scaled from daily/weekly intent to the requested chart interval (see
  below). Supplying `period` overrides the 50/200 default, and the override is
  then scaled too.
- For `rsi`, the point carries both `value` and `rsi` (identical); `rsi` is
  omitted only if it is zero.
- Output points drop `NaN`/`Inf` values, so a series may start after the first
  candle.

## Interval scaling of moving-average periods

The `ma50`/`ma200`/`ma50w`/`ma200w` types rescale their period from daily or
weekly units to the requested `interval` (`ScalePeriod` in `timeframe.go`).
Intervals are matched case-insensitively; unknown intervals are returned
unscaled.

**Day unit** (`ma50`, `ma200`):

| `interval` | Scaled period                |
| ---------- | ---------------------------- |
| `1h`       | `period × 7`                 |
| `4h`       | `period × 2`                 |
| `1d`       | `period`                     |
| `1w`       | `round(period / 5)`, min `1` |
| `1m`       | `round(period / 21)`, min `1`|

**Week unit** (`ma50w`, `ma200w`):

| `interval` | Scaled period                    |
| ---------- | -------------------------------- |
| `1h`       | `period × 35`                    |
| `4h`       | `period × 10`                    |
| `1d`       | `period × 5`                     |
| `1w`       | `period`                         |
| `1m`       | `round(period × 12 / 52)`, min `1`|

Example: `ma50` on an hourly chart computes an SMA over 350 hourly candles
(`50 × 7`). A non-positive period scales to `0` and yields an empty series.

## Running locally

Requires Go 1.24+.

```bash
cd services/indicator-service
go run .
```

The server listens on `PORT` (default `8080`) and shuts down gracefully on
`SIGINT`/`SIGTERM` (10s grace period).

```bash
PORT=9000 go run .
```

## Running with Docker Compose

From the repository root:

```bash
docker compose up indicator-service
```

- Dev compose (`docker-compose.yml`): published on
  `${INDICATOR_SERVICE_PORT:-8085}` on the host, mapped to container port
  `8080`. Override with `INDICATOR_SERVICE_PORT=9090 docker compose up indicator-service`.
- Prod compose (`docker-compose.prod.yml`): fixed `8085:8080`, container name
  `retail-portfolio-indicator-service`, `restart: always`.
- Both compose files healthcheck `GET /health` via `wget` every 30s
  (timeout 5s, 3 retries, 5s start period).

The image is built from `services/indicator-service/Dockerfile`: a
`golang:1.24-alpine` builder produces a statically linked binary, which runs on
`alpine:3.21` as the non-root `appuser`.

## Tests

```bash
cd services/indicator-service
go test ./...
```

Test files: `calculator_test.go`, `handlers_test.go`, `timeframe_test.go`.

## Backend integration

The FastAPI backend is the only intended client.

- **Setting:** `indicator_service_url` in `src/config/settings.py`, default
  `http://localhost:8080`.
- **Environment variable:** `INDICATOR_SERVICE_URL`; `src/.env.example` sets it
  to `http://indicator-service:8080` for Docker Compose (the compose service
  name).
- **Client:** `IndicatorServiceClient` in `src/market/service.py` POSTs
  `{interval, candles, indicators}` as JSON to `<base_url>/compute` and returns
  the `indicators` map. The default client timeout is `10.0`s.
- **Error mapping** (service response → backend `HTTPException`):

  | Service outcome                                              | Backend response |
  | ------------------------------------------------------------ | ---------------- |
  | Request timeout (`httpx.TimeoutException`)                   | `504` "Indicator service timed out" |
  | Connection/network error (`httpx.ConnectError`/`NetworkError`) | `503` "Indicator service unavailable" |
  | `400`                                                        | `400`, with the service's `error` text as detail |
  | `5xx`                                                        | `503` "Indicator service unavailable" |
  | Any other non-`200`                                          | propagated status, response text as detail |

## Examples

Health check:

```bash
curl -s http://localhost:8080/health
# {"status":"ok","service":"indicator-service"}
```

Compute an RSI and a scaled 50-day MA on an hourly chart:

```bash
curl -s -X POST http://localhost:8080/compute \
  -H 'Content-Type: application/json' \
  -d '{
    "interval": "1h",
    "candles": [
      {"time": "2024-01-02T14:30:00Z", "open": 185.1, "high": 186.4, "low": 184.9, "close": 186.0, "volume": 1200000},
      {"time": "2024-01-02T15:30:00Z", "open": 186.0, "high": 187.2, "low": 185.6, "close": 186.9, "volume": 980000},
      {"time": "2024-01-02T16:30:00Z", "open": 186.9, "high": 187.5, "low": 185.8, "close": 186.1, "volume": 1500000}
    ],
    "indicators": [
      {"id": "rsi14", "type": "rsi", "period": 14},
      {"type": "ma50"}
    ]
  }'
```

The response is `{"indicators": {"rsi14": [...], "ma50": [...]}}` — the RSI is
keyed by its `id`, the MA by its `type`. With only three hourly candles both
series come back as `[]` (too few points to compute), which is a valid `200`.
