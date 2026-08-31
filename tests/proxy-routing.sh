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
cp "$dynamic" "$tmp_dir/base.yml"

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

cp "$tmp_dir/base.yml" "$tmp_dir/default-validation.yml"
mkdir -p "$tmp_dir/bin"
cat >"$tmp_dir/bin/docker" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
if [[ " $* " == *" check-config "* ]]; then exit 88; fi
if [[ ${1:-} == logs ]]; then exit 0; fi
exit 0
SH
chmod +x "$tmp_dir/bin/docker"
PATH="$tmp_dir/bin:$PATH" TRAEFIK_DYNAMIC_FILE="$tmp_dir/default-validation.yml" \
  "$repo_root/scripts/install-traefik-route.sh"
grep -q '^    plane-router:$' "$tmp_dir/default-validation.yml"

! grep -q 'plane-minio:9000' "$repo_root/apps/proxy/Caddyfile.ce"
