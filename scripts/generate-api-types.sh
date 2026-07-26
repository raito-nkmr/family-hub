#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
output_directory="${1:-$project_root/frontend/src/shared/api/generated}"
schema_file="$(mktemp)"
trap 'rm -f "$schema_file"' EXIT

if [[ -x "$project_root/backend/.venv/bin/python" ]]; then
  python="$project_root/backend/.venv/bin/python"
else
  python="python"
fi

(
  cd "$project_root/backend"
  "$python" -m app.commands.export_openapi --output "$schema_file"
)

"$project_root/frontend/node_modules/.bin/openapi-ts" \
  --input "$schema_file" \
  --output "$output_directory" \
  --client @hey-api/client-fetch \
  --plugins @hey-api/typescript @hey-api/sdk \
  --silent

"$project_root/frontend/node_modules/.bin/prettier" \
  --config "$project_root/frontend/prettier.config.js" \
  --write "$output_directory" >/dev/null
