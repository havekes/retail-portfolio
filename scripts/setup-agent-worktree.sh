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

# Generate a safe compose project name based on the path
PROJECT_NAME=$(basename "$WORKTREE_PATH" | tr -cd 'a-zA-Z0-9_-' | tr 'A-Z' 'a-z')

# 3. Create .env
echo "Generating .env in $WORKTREE_PATH..."
cat <<EOF > .env
COMPOSE_PROJECT_NAME=${PROJECT_NAME}
BACKEND_PORT=${BACKEND_PORT}
FRONTEND_PORT=${FRONTEND_PORT}
BACKEND_DEBUG_PORT=${BACKEND_DEBUG}
WORKER_DEBUG_PORT=${WORKER_DEBUG}
POSTGRES_PORT=${POSTGRES_PORT}
MAILCRAB_PORT=${MAILCRAB_PORT}
EOF

# 4. Copy untracked .env files from main repo to worktree
echo "Copying untracked .env files from main repo..."
if [ -f "$MAIN_REPO_PATH/src/.env" ]; then
    cp "$MAIN_REPO_PATH/src/.env" "./src/.env"
elif [ -f "./src/.env.example" ]; then
    cp "./src/.env.example" "./src/.env"
fi

if [ -f "$MAIN_REPO_PATH/.env" ]; then
    # We don't overwrite the generated root .env, but we can append to it or just leave it
    # The root .env we just created is for compose overrides. The main repo .env might have other things.
    # Let's assume root .env for compose is sufficient, and we only really needed src/.env
    :
fi

echo "Done! Worktree is ready at $WORKTREE_PATH."
echo "Ports assigned:"
cat .env
