#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
dynamic_file=${TRAEFIK_DYNAMIC_FILE:-$repo_root/../../traefik/dynamic.yml}
fragment_file=${TRAEFIK_ROUTE_FRAGMENT:-$repo_root/deploy/traefik-plane.yml}

[[ -r $dynamic_file && -w $dynamic_file ]] || {
  printf 'Traefik dynamic configuration is not readable and writable: %s\n' "$dynamic_file" >&2
  exit 1
}

has_router=0
has_service=0
grep -q '^    plane-router:$' "$dynamic_file" && has_router=1
grep -q '^    plane-service:$' "$dynamic_file" && has_service=1

if ((has_router == 1 && has_service == 1)); then
  printf 'Plane Traefik route already installed\n'
  exit 0
fi
if ((has_router != has_service)); then
  printf 'Refusing partially configured Plane Traefik route\n' >&2
  exit 1
fi

tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT
router_block="$tmp_dir/router.yml"
service_block="$tmp_dir/service.yml"
candidate="$tmp_dir/dynamic.yml"

awk '
  /^routers:$/ { section="routers"; next }
  /^services:$/ { section="services"; next }
  section == "routers" { print "  " $0 }
' "$fragment_file" >"$router_block"
awk '
  /^services:$/ { section="services"; next }
  section == "services" { print "  " $0 }
' "$fragment_file" >"$service_block"

test -s "$router_block"
test -s "$service_block"

awk -v router_file="$router_block" -v service_file="$service_block" '
  $0 == "  routers:" {
    print
    while ((getline line < router_file) > 0) print line
    close(router_file)
    routers++
    next
  }
  $0 == "  services:" {
    print
    while ((getline line < service_file) > 0) print line
    close(service_file)
    services++
    next
  }
  { print }
  END { if (routers != 1 || services != 1) exit 42 }
' "$dynamic_file" >"$candidate" || {
  printf 'Expected exactly one http routers and services anchor\n' >&2
  exit 1
}

backup="${dynamic_file}.bak.$(date +%Y%m%d%H%M%S)"
cp -p "$dynamic_file" "$backup"
chmod --reference="$dynamic_file" "$candidate"
cp "$candidate" "$dynamic_file"

if [[ -n ${TRAEFIK_VALIDATE_COMMAND:-} ]]; then
  if ! bash -c "$TRAEFIK_VALIDATE_COMMAND"; then
    cp -p "$backup" "$dynamic_file"
    printf 'Traefik validation failed; restored %s\n' "$backup" >&2
    exit 1
  fi
elif ! docker exec traefik traefik check-config --configFile=/etc/traefik/traefik.yml >/dev/null; then
  cp -p "$backup" "$dynamic_file"
  printf 'Traefik validation failed; restored %s\n' "$backup" >&2
  exit 1
fi

printf 'Installed Plane Traefik route (backup: %s)\n' "$backup"
