#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker was not found. Install Docker or run backend:dev and frontend:dev in separate terminals." >&2
  exit 1
fi

docker compose up --build
