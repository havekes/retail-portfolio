#!/usr/bin/env python3
"""Send a deterministic OTLP burst through the tail-sampling gateway (F-OBS-T16).

Manual verification helper for the runbook in
``docker/observability/README.md`` § "Tail Sampling Policy". It sends
single-span traces over OTLP/HTTP so the sampling decision of each cohort can be
counted in ClickHouse afterwards:

* ``--success`` ``http.request`` spans carrying an int ``status=200`` -- the
  successful bulk that the probabilistic policy must reduce to the configured
  5-10% band.
* ``--errors`` ``http.request`` spans carrying an int ``status=500`` -- the
  failure cohort that must be retained in full (an int status is invisible to
  the application-side ``_error_reason()`` heuristic; the gateway's
  ``transform/error_marking`` processor promotes it to span status ERROR).
* ``--failures`` ``auth.event`` spans with ``outcome=failure`` and an
  ``error_slug`` -- same full-retention requirement, marked on the application
  side already.
* ``--slug-only`` ``market.cache.accessed`` spans that carry only an
  ``error_slug`` (no failure ``outcome``) -- exercises the gateway's
  ``error-slug-present`` retention policy.

Stdlib only, so it runs inside any dev container:

    docker compose exec -T backend python docker/observability/send-sampling-burst.py

Live-stack invocation is a documented manual step; the automated test suite
never executes this script.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
import uuid

DEFAULT_ENDPOINT = "http://otel-sampler:4318/v1/traces"
DEFAULT_SERVICE_NAME = "backend"


def _attribute(key: str, value: object) -> dict:
    if isinstance(value, bool):
        encoded = {"boolValue": value}
    elif isinstance(value, int):
        encoded = {"intValue": str(value)}
    else:
        encoded = {"stringValue": str(value)}
    return {"key": key, "value": encoded}


def _trace(span_name: str, attributes: list[dict], service_name: str) -> dict:
    start = time.time_ns()
    return {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": [
                        _attribute("service.name", service_name),
                        _attribute("deployment.environment", "dev"),
                    ]
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "observability.events"},
                        "spans": [
                            {
                                # One span per trace: the tail sampler decides
                                # per trace, so this keeps the cohorts disjoint.
                                "traceId": uuid.uuid4().hex,
                                "spanId": uuid.uuid4().hex[:16],
                                "name": span_name,
                                "kind": 1,
                                "startTimeUnixNano": str(start),
                                "endTimeUnixNano": str(start + 1_000_000),
                                "attributes": attributes,
                                "status": {},
                            }
                        ],
                    }
                ],
            }
        ]
    }


def _cohorts(
    args: argparse.Namespace,
) -> list[tuple[str, str, list[dict], int]]:
    return [
        (
            "http.request status=200",
            "http.request",
            [
                _attribute("event.name", "http.request"),
                _attribute("status", 200),
            ],
            args.success,
        ),
        (
            "http.request status=500",
            "http.request",
            [
                _attribute("event.name", "http.request"),
                _attribute("status", 500),
            ],
            args.errors,
        ),
        (
            "auth.event outcome=failure",
            "auth.event",
            [
                _attribute("event.name", "auth.event"),
                _attribute("outcome", "failure"),
                _attribute("error_slug", "invalid_credentials"),
            ],
            args.failures,
        ),
        (
            "market.cache.accessed error_slug only",
            "market.cache.accessed",
            [
                _attribute("event.name", "market.cache.accessed"),
                _attribute("outcome", "hit"),
                _attribute("error_slug", "cache_backend_error"),
            ],
            args.slug_only,
        ),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--service-name", default=DEFAULT_SERVICE_NAME)
    parser.add_argument("--success", type=int, default=100)
    parser.add_argument("--errors", type=int, default=20)
    parser.add_argument("--failures", type=int, default=20)
    parser.add_argument("--slug-only", type=int, default=0)
    args = parser.parse_args(argv)

    for label, span_name, attributes, count in _cohorts(args):
        for _ in range(count):
            body = json.dumps(_trace(span_name, attributes, args.service_name)).encode()
            request = urllib.request.Request(  # noqa: S310
                args.endpoint,
                data=body,
                headers={"content-type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request) as response:  # noqa: S310
                response.read()
        sys.stdout.write(f"sent {count}x {label}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
