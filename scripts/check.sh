#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

(
  cd "$project_root/backend"
  uv run --locked ruff check .
  uv run --locked ruff format --check .
  uv run --locked pytest
)

npm --prefix "$project_root/frontend" run check
