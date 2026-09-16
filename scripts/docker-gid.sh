#!/usr/bin/env bash
# Print the host Docker socket's group id as seen *inside* a container, so the
# backend/worker services (uid 1000) can reach testcontainers' daemon.
#
# Host `stat` is authoritative on Linux. On Docker Desktop/OrbStack the socket
# is remounted with different ownership (e.g. host gid 20 -> container gid 0),
# so ask the daemon itself. Prints nothing when no socket is mounted.
set -euo pipefail

sock=/var/run/docker.sock
[ -S "$sock" ] || exit 0

if [ "$(uname -s)" = "Darwin" ]; then
    docker run --rm -v "$sock:$sock" --entrypoint stat alpine:3 \
        -c '%g' "$sock" 2>/dev/null || true
else
    stat -Lc '%g' "$sock" 2>/dev/null || stat -Lf '%g' "$sock" 2>/dev/null || true
fi
