#!/usr/bin/env bash
set -e

if [ -z "$1" ] || [ -z "$2" ]; then
    echo "Usage: $0 <worktree-path> <branch-name>"
    echo "Example: $0 ../rp-task-123 feature/task-123"
    exit 1
fi

WORKTREE_PATH="$1"
BRANCH_NAME="$2"

MAIN_REPO_PATH=$(cd "$(dirname "$0")/.." && pwd)

# 1. Create the worktree
echo "Creating git worktree at $WORKTREE_PATH for branch $BRANCH_NAME..."
if git show-ref --verify --quiet refs/heads/"$BRANCH_NAME"; then
    git worktree add "$WORKTREE_PATH" "$BRANCH_NAME"
else
    git worktree add -b "$BRANCH_NAME" "$WORKTREE_PATH" origin/main
fi

cd "$WORKTREE_PATH"

# 2. Find available ports dynamically using python
echo "Assigning unique ports..."
BACKEND_PORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("", 0)); print(s.getsockname()[1]); s.close()')
FRONTEND_PORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("", 0)); print(s.getsockname()[1]); s.close()')
BACKEND_DEBUG=$(python3 -c 'import socket; s=socket.socket(); s.bind(("", 0)); print(s.getsockname()[1]); s.close()')
WORKER_DEBUG=$(python3 -c 'import socket; s=socket.socket(); s.bind(("", 0)); print(s.getsockname()[1]); s.close()')
POSTGRES_PORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("", 0)); print(s.getsockname()[1]); s.close()')
MAILCRAB_PORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("", 0)); print(s.getsockname()[1]); s.close()')
INDICATOR_SERVICE_PORT=$(python3 -c 'import socket; s=socket.socket(); s.bind(("", 0)); print(s.getsockname()[1]); s.close()')

# Generate a safe compose project name based on the path
PROJECT_NAME=$(basename "$WORKTREE_PATH" | tr -cd 'a-zA-Z0-9_-' | tr 'A-Z' 'a-z')

DOCKER_GID=$("$MAIN_REPO_PATH/scripts/docker-gid.sh")

# 3. Build the worktree root .env: seed it with the main repo config, then
# deterministically override the compose project name and all published ports so
# the discovered values always win (and re-runs leave no duplicate/stale entries).
echo "Generating .env in $WORKTREE_PATH..."
if [ -f "$MAIN_REPO_PATH/.env" ]; then
    cp "$MAIN_REPO_PATH/.env" "./.env"
elif [ -f "./.env.example" ]; then
    cp "./.env.example" "./.env"
else
    echo "Error: no $MAIN_REPO_PATH/.env and no ./.env.example to seed a worktree .env." >&2
    exit 1
fi

set_env() {
    local key="$1" value="$2"
    grep -v "^${key}=" "./.env" > "./.env.tmp" || true
    mv "./.env.tmp" "./.env"
    printf '%s=%s\n' "$key" "$value" >> "./.env"
}

set_env COMPOSE_PROJECT_NAME "$PROJECT_NAME"
set_env DOCKER_GID "$DOCKER_GID"
set_env BACKEND_PORT "$BACKEND_PORT"
set_env FRONTEND_PORT "$FRONTEND_PORT"
set_env BACKEND_DEBUG_PORT "$BACKEND_DEBUG"
set_env WORKER_DEBUG_PORT "$WORKER_DEBUG"
set_env POSTGRES_PORT "$POSTGRES_PORT"
set_env MAILCRAB_PORT "$MAILCRAB_PORT"
set_env INDICATOR_SERVICE_PORT "$INDICATOR_SERVICE_PORT"

echo "Done! Worktree is ready at $WORKTREE_PATH."
echo "Ports assigned:"
cat .env
