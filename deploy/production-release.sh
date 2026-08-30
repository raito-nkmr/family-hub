#!/usr/bin/env bash

set -Eeuo pipefail

readonly releases_dir=/opt/family-hub/releases
readonly current_link=/opt/family-hub/current
readonly backend_service=family-hub-backend.service
readonly backend_health_url=http://127.0.0.1:8000/api/v1/health
readonly caddy_health_url=http://127.0.0.1:8080/api/v1/health
readonly caddy_root_url=http://127.0.0.1:8080/
readonly lock_file=/run/lock/family-hub-release.lock
readonly health_timeout_seconds=30

script_name="$(basename "$0")"

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<EOF
Usage: $script_name <release-archive> [release-id]

Install a release archive, prepare its backend environment, and switch the
production symlink only after local validation succeeds. Use a new release id
for every attempt; partial releases are never reused.

Set UV_BIN to an absolute path when uv is not installed in /usr/local/bin/uv
or /usr/bin/uv.
EOF
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ "$#" -lt 1 || "$#" -gt 2 ]]; then
  usage >&2
  exit 2
fi

[[ "$EUID" -eq 0 ]] || die 'run as root'

archive_path="$(readlink -f -- "$1")"
[[ -f "$archive_path" ]] || die "release archive not found: $archive_path"

archive_name="$(basename "$archive_path")"
default_release_id="${archive_name%.tar.gz}"
release_id="${2:-$default_release_id}"

if [[ ! "$release_id" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]]; then
  die "release id contains unsupported characters: $release_id"
fi

release_dir="$releases_dir/$release_id"

command -v curl >/dev/null || die 'curl is required'
command -v chown >/dev/null || die 'chown is required'
command -v flock >/dev/null || die 'flock is required'
command -v getent >/dev/null || die 'getent is required'
command -v install >/dev/null || die 'install is required'
command -v mv >/dev/null || die 'mv is required'
command -v runuser >/dev/null || die 'runuser is required'
command -v sha256sum >/dev/null || die 'sha256sum is required'
command -v systemctl >/dev/null || die 'systemctl is required'
command -v tar >/dev/null || die 'tar is required'

[[ -d "$releases_dir" ]] || die "release directory does not exist: $releases_dir"
[[ -L "$current_link" ]] || die "current path is not a symlink: $current_link"
[[ -e "$release_dir" || -L "$release_dir" ]] && die "release already exists: $release_dir"
getent passwd family-hub >/dev/null || die 'family-hub user does not exist'
getent group family-hub >/dev/null || die 'family-hub group does not exist'

old_release="$(readlink -f -- "$current_link")"
[[ -d "$old_release" ]] || die "current release does not exist: $old_release"
case "$old_release" in
  "$releases_dir"/*) ;;
  *) die "current symlink points outside the release directory: $old_release" ;;
esac

if [[ -n "${UV_BIN:-}" ]]; then
  uv_bin="$UV_BIN"
else
  uv_bin=''
  for candidate in /usr/local/bin/uv /usr/bin/uv; do
    if [[ -x "$candidate" ]]; then
      uv_bin="$candidate"
      break
    fi
  done
fi
[[ -n "$uv_bin" && "$uv_bin" = /* && -x "$uv_bin" ]] || die \
  'uv was not found; install it system-wide or set UV_BIN to an absolute executable path'

archive_entries() {
  tar --list --file="$archive_path"
}

archive_entries >/dev/null || die 'release archive is not a readable tar archive'

unsafe_entry="$(archive_entries | grep -E '(^/|(^|/)\.\.(/|$))' | head -n 1 || true)"
[[ -z "$unsafe_entry" ]] || die "release archive contains an unsafe path: $unsafe_entry"

forbidden_entry="$(archive_entries | grep -E '(^|/)\.env$|(^|/)\.venv(/|$)|(^|/)node_modules(/|$)' | head -n 1 || true)"
[[ -z "$forbidden_entry" ]] || die "release archive contains a forbidden path: $forbidden_entry"

exec 9>"$lock_file"
flock -n 9 || die 'another Family Hub release is already running'

wait_for_http() {
  local url="$1"
  local deadline=$((SECONDS + health_timeout_seconds))

  while (( SECONDS < deadline )); do
    if curl --fail --silent --show-error --connect-timeout 2 --max-time 5 "$url" >/dev/null; then
      return 0
    fi
    sleep 1
  done

  return 1
}

check_current_health() {
  wait_for_http "$backend_health_url" || die "current backend is not healthy: $backend_health_url"
  wait_for_http "$caddy_health_url" || die "current Caddy API is not healthy: $caddy_health_url"
  wait_for_http "$caddy_root_url" || die "current static root is not healthy: $caddy_root_url"
}

wait_for_static_release() {
  local expected_index_hash
  local actual_index_hash
  local deadline=$((SECONDS + health_timeout_seconds))

  expected_index_hash="$(sha256sum "$release_dir/frontend/dist/index.html")"
  expected_index_hash="${expected_index_hash%% *}"

  while (( SECONDS < deadline )); do
    if actual_index_hash="$(curl --fail --silent --show-error --connect-timeout 2 --max-time 5 \
      --header 'Accept-Encoding: identity' "$caddy_root_url" | sha256sum)"; then
      actual_index_hash="${actual_index_hash%% *}"
      if [[ "$actual_index_hash" == "$expected_index_hash" ]]; then
        return 0
      fi
    fi
    sleep 1
  done

  return 1
}

rollback() {
  local rollback_link="${current_link}.rollback.$$"

  printf 'Rolling back to %s\n' "$old_release" >&2
  [[ "$(readlink -f -- "$current_link")" == "$release_dir" ]] || {
    printf '%s\n' 'ERROR: current symlink changed outside this script; manual rollback required' >&2
    return 1
  }

  [[ ! -e "$rollback_link" && ! -L "$rollback_link" ]] || {
    printf '%s\n' "ERROR: rollback link already exists: $rollback_link" >&2
    return 1
  }

  ln -s -- "$old_release" "$rollback_link"
  mv --no-target-directory -- "$rollback_link" "$current_link"
  systemctl restart "$backend_service"
  wait_for_http "$backend_health_url"
}

check_current_health

printf 'Preparing %s\n' "$release_dir"
install -d -o root -g root -m 0755 "$release_dir"
tar --extract --gzip --file="$archive_path" --directory="$release_dir" --no-same-owner --no-same-permissions

for required_path in \
  backend/pyproject.toml \
  backend/uv.lock \
  frontend/dist/index.html \
  deploy/compose.production.yaml; do
  [[ -e "$release_dir/$required_path" ]] || die "release is missing: $required_path"
done

printf 'Creating pinned backend environment with %s\n' "$uv_bin"
(
  cd "$release_dir/backend"
  env -u VIRTUAL_ENV -u UV_PROJECT_ENVIRONMENT "$uv_bin" sync --locked --no-dev
)
chown -R root:root "$release_dir"
# The release may have been extracted or created under a restrictive root umask.
# Keep releases immutable while allowing the service users to traverse and read them.
chmod -R a+rX "$release_dir"

backend_python="$release_dir/backend/.venv/bin/python"
[[ -x "$backend_python" ]] || die "backend environment was not created: $backend_python"
runuser --user family-hub -- "$backend_python" -m uvicorn --help >/dev/null

next_link="${current_link}.next.$$"
[[ ! -e "$next_link" && ! -L "$next_link" ]] || die "temporary switch link already exists: $next_link"
ln -s -- "$release_dir" "$next_link"
mv --no-target-directory -- "$next_link" "$current_link"

if ! systemctl restart "$backend_service"; then
  rollback || die 'new backend failed and automatic rollback also failed'
  die 'new backend failed; application was rolled back'
fi

if ! wait_for_http "$backend_health_url" || \
  ! wait_for_http "$caddy_health_url" || \
  ! wait_for_static_release; then
  rollback || die 'post-switch health check failed and automatic rollback also failed'
  die 'post-switch health check failed; application was rolled back'
fi

printf 'Release active: %s\n' "$release_dir"
printf '%s\n' 'Backend, Caddy, and static content health checks passed.'
