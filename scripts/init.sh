#!/usr/bin/env sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f ".env" ]; then
  cp ".env.example" ".env"
  echo "Created .env from .env.example"
fi

echo "Installing backend dependencies..."
cd "$ROOT_DIR/backend"
uv sync

echo "Installing frontend dependencies..."
cd "$ROOT_DIR"
pnpm --dir frontend install

echo "Project initialized."
