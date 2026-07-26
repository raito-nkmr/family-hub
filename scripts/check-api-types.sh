#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
temporary_directory="$(mktemp -d)"
trap 'rm -rf "$temporary_directory"' EXIT

bash "$project_root/scripts/generate-api-types.sh" "$temporary_directory/generated"

if ! diff -ru "$project_root/frontend/src/shared/api/generated" "$temporary_directory/generated"; then
  echo "Generated API types are stale. Run: npm --prefix frontend run api:generate" >&2
  exit 1
fi
