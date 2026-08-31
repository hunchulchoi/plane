#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT

cp "$repo_root/../../traefik/traefik.yml" "$tmp_dir/traefik.yml"
cp "$repo_root/../../traefik/dynamic.yml" "$tmp_dir/dynamic.yml"
cp "$repo_root/../../traefik/compose.yaml" "$tmp_dir/compose.yaml"

TRAEFIK_DIR="$tmp_dir" CF_DNS_API_TOKEN=test-token \
  "$repo_root/scripts/configure-traefik-acme.sh"

test "$(stat -c '%a' "$tmp_dir/.env")" = 600
test "$(stat -c '%a' "$tmp_dir/letsencrypt/acme.json")" = 600
grep -q '^CF_DNS_API_TOKEN=test-token$' "$tmp_dir/.env"
grep -q '^certificatesResolvers:' "$tmp_dir/traefik.yml"
grep -q 'provider: cloudflare' "$tmp_dir/traefik.yml"
grep -q '1.1.1.1:53' "$tmp_dir/traefik.yml"
if grep -q '8.8.8.8:53' "$tmp_dir/traefik.yml"; then
  printf 'Google resolver must not remain in ACME DNS-01 configuration\n' >&2
  exit 1
fi
grep -q 'storage: /letsencrypt/acme.json' "$tmp_dir/traefik.yml"
for router in plane-router traefik-dashboard minio-console-router minio-s3-router; do
  grep -A18 "^    $router:" "$tmp_dir/dynamic.yml" | grep -q 'certResolver: letsencrypt'
done
if grep -A18 '^    traefik-dashboard-redirect:' "$tmp_dir/dynamic.yml" | grep -q 'certResolver: letsencrypt'; then
  printf 'Dashboard redirect must reuse the primary dashboard certificate\n' >&2
  exit 1
fi
grep -q -- './letsencrypt:/letsencrypt' "$tmp_dir/compose.yaml"
grep -q -- '.env' "$tmp_dir/compose.yaml"

# Reapplying must be idempotent.
TRAEFIK_DIR="$tmp_dir" CF_DNS_API_TOKEN=test-token \
  "$repo_root/scripts/configure-traefik-acme.sh"
test "$(grep -c '^certificatesResolvers:' "$tmp_dir/traefik.yml")" = 1
test "$(grep -c 'certResolver: letsencrypt' "$tmp_dir/dynamic.yml")" = 4

# Once stored, the token can be reused without placing it on the command line.
env -u CF_DNS_API_TOKEN TRAEFIK_DIR="$tmp_dir" \
  "$repo_root/scripts/configure-traefik-acme.sh"
