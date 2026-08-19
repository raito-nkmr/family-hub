#!/usr/bin/env bash

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
icon_directory="$project_root/frontend/src/shared/ui/icons/material-symbols"

if rg -n 'fill="#[0-9a-fA-F]+' "$icon_directory"; then
  echo 'Material Symbol SVGs must use fill="currentColor" for theme-aware icon colors.' >&2
  exit 1
fi
