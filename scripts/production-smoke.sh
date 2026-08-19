#!/usr/bin/env bash

set -euo pipefail

if [[ -z "${PUBLIC_BASE_URL:-}" ]]; then
  printf '%s\n' 'PUBLIC_BASE_URL must contain the public HTTPS origin' >&2
  exit 2
fi

base_url="${PUBLIC_BASE_URL%/}"

request_status() {
  curl --silent --show-error --output /dev/null --write-out '%{http_code}' "$1"
}

request_headers() {
  curl --silent --show-error --dump-header - --output /dev/null "$1"
}

assert_status() {
  local path="$1"
  local expected="$2"
  local actual
  actual="$(request_status "${base_url}${path}")"
  if [[ "$actual" != "$expected" ]]; then
    printf 'FAIL %s: expected HTTP %s, got %s\n' "$path" "$expected" "$actual" >&2
    exit 1
  fi
  printf 'PASS %s: HTTP %s\n' "$path" "$actual"
}

assert_header_contains() {
  local path="$1"
  local header="$2"
  local expected="$3"
  local headers
  headers="$(request_headers "${base_url}${path}")"
  if ! grep --ignore-case --fixed-strings -- "$header:" <<<"$headers" | grep --ignore-case --fixed-strings -- "$expected" >/dev/null; then
    printf 'FAIL %s: expected %s to contain %s\n' "$path" "$header" "$expected" >&2
    exit 1
  fi
  printf 'PASS %s: %s contains %s\n' "$path" "$header" "$expected"
}

assert_status '/api/v1/health' 200
assert_status '/api/v1/readiness' 404
assert_status '/api/v1/auth/me' 401
assert_status '/api/v1/photos?limit=1' 401
assert_status '/' 200
assert_status '/sw.js' 200

assert_header_contains '/' 'cache-control' 'no-cache'
assert_header_contains '/sw.js' 'cache-control' 'no-store'
assert_header_contains '/api/v1/health' 'cache-control' 'no-store'

printf '%s\n' 'Production public smoke checks passed.'
