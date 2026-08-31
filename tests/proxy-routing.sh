#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT

dynamic="$tmp_dir/dynamic.yml"
cat >"$dynamic" <<'YAML'
http:
  routers:
    existing-router:
      rule: "Host(`existing.example`)"
      service: existing-service
  middlewares:
    existing-middleware:
      headers: {}
  services:
    existing-service:
      loadBalancer:
        servers:
          - url: "http://host.docker.internal:9999"
YAML

TRAEFIK_DYNAMIC_FILE="$dynamic" TRAEFIK_VALIDATE_COMMAND=true \
  "$repo_root/scripts/install-traefik-route.sh"

grep -q '^    plane-router:$' "$dynamic"
grep -q '^    plane-service:$' "$dynamic"
grep -q 'Host(`plane.devfor.link`)' "$dynamic"
grep -q 'http://host.docker.internal:8220' "$dynamic"
grep -q '^    existing-router:$' "$dynamic"
grep -q '^    existing-service:$' "$dynamic"

first_hash=$(sha256sum "$dynamic")
TRAEFIK_DYNAMIC_FILE="$dynamic" TRAEFIK_VALIDATE_COMMAND=true \
  "$repo_root/scripts/install-traefik-route.sh"
test "$first_hash" = "$(sha256sum "$dynamic")"

cp "$dynamic" "$tmp_dir/half.yml"
sed -i '/^    plane-service:/,/^    existing-service:/{/^    plane-service:/,/^    existing-service:/{/^    existing-service:/!d}}' "$tmp_dir/half.yml"
if TRAEFIK_DYNAMIC_FILE="$tmp_dir/half.yml" TRAEFIK_VALIDATE_COMMAND=true \
  "$repo_root/scripts/install-traefik-route.sh" 2>/dev/null; then
  echo 'half-configured route should be rejected' >&2
  exit 1
fi

! grep -q 'plane-minio:9000' "$repo_root/apps/proxy/Caddyfile.ce"
