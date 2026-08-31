#!/usr/bin/env bash

set -Eeuo pipefail

script_name="$(basename "$0")"
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<EOF
Usage: $script_name [release-id] [archive-path]

Run the repository checks, build the frontend, and create a release archive.
The archive contains tracked repository files and frontend/dist only.
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ "$#" -gt 2 ]]; then
  usage >&2
  exit 2
fi

release_id="${1:-$(date -u +%Y%m%dT%H%M%SZ)-$(git -C "$project_root" rev-parse --short HEAD)}"
archive_path="${2:-/tmp/family-hub-release-${release_id}.tar.gz}"

if [[ "$archive_path" != /* ]]; then
  archive_path="$project_root/$archive_path"
fi

if [[ ! "$release_id" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  die "release id contains unsupported characters: $release_id"
fi

if [[ -e "$archive_path" || -L "$archive_path" ]]; then
  die "refusing to overwrite existing archive: $archive_path"
fi

command -v git >/dev/null || die 'git is required'
command -v make >/dev/null || die 'make is required'
command -v npm >/dev/null || die 'npm is required'
command -v tar >/dev/null || die 'tar is required'
command -v sha256sum >/dev/null || die 'sha256sum is required'

cd "$project_root"

if [[ -n "$(git status --porcelain)" ]]; then
  die 'working tree is not clean; commit or stash changes before creating a release'
fi

printf '%s\n' 'Installing locked frontend dependencies...'
npm --prefix frontend ci

production_upload_timeout="${VITE_UPLOAD_REQUEST_TIMEOUT_MS:-}"
printf '%s\n' 'Running backend and frontend checks...'
env -u VITE_UPLOAD_REQUEST_TIMEOUT_MS make check

if [[ -n "$production_upload_timeout" ]]; then
  printf 'Building frontend with VITE_UPLOAD_REQUEST_TIMEOUT_MS=%s...\n' "$production_upload_timeout"
  VITE_UPLOAD_REQUEST_TIMEOUT_MS="$production_upload_timeout" npm --prefix frontend run build
fi

[[ -f frontend/dist/index.html ]] || die 'frontend build did not create frontend/dist/index.html'

stage_dir="$(mktemp -d /tmp/family-hub-release.XXXXXX)"
cleanup() {
  rm -rf -- "$stage_dir"
}
trap cleanup EXIT

git archive --format=tar HEAD | tar --extract --file=- --directory="$stage_dir"
mkdir -p "$stage_dir/frontend/dist"
cp -a frontend/dist/. "$stage_dir/frontend/dist/"

forbidden_entry="$(find "$stage_dir" \( -name .env -o -name .venv -o -name node_modules \) -print -quit)"
if [[ -n "$forbidden_entry" ]]; then
  die "release contains a forbidden file: ${forbidden_entry#"$stage_dir/"}"
fi

mkdir -p "$(dirname "$archive_path")"
tar --create --gzip --file="$archive_path" --directory="$stage_dir" .

printf 'Release archive: %s\n' "$archive_path"
sha256sum "$archive_path"
