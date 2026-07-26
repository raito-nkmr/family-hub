#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -x "$project_root/backend/.venv/bin/ruff" && -x "$project_root/backend/.venv/bin/pytest" ]]; then
  ruff="$project_root/backend/.venv/bin/ruff"
  pytest="$project_root/backend/.venv/bin/pytest"
else
  ruff="ruff"
  pytest="pytest"
fi

(
  cd "$project_root/backend"
  "$ruff" check .
  "$ruff" format --check .
  "$pytest"
)

npm --prefix "$project_root/frontend" run check
