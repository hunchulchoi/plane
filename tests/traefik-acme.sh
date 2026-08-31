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
grep -q 'storage: /letsencrypt/acme.json' "$tmp_dir/traefik.yml"
grep -A16 '^    plane-router:' "$tmp_dir/dynamic.yml" | grep -q 'certResolver: letsencrypt'
grep -q -- './letsencrypt:/letsencrypt' "$tmp_dir/compose.yaml"
grep -q -- '.env' "$tmp_dir/compose.yaml"

# Reapplying must be idempotent.
TRAEFIK_DIR="$tmp_dir" CF_DNS_API_TOKEN=test-token \
  "$repo_root/scripts/configure-traefik-acme.sh"
test "$(grep -c '^certificatesResolvers:' "$tmp_dir/traefik.yml")" = 1
test "$(grep -c 'certResolver: letsencrypt' "$tmp_dir/dynamic.yml")" = 1

# Once stored, the token can be reused without placing it on the command line.
env -u CF_DNS_API_TOKEN TRAEFIK_DIR="$tmp_dir" \
  "$repo_root/scripts/configure-traefik-acme.sh"
