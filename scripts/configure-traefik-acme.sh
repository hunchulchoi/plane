#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
traefik_dir=${TRAEFIK_DIR:-$repo_root/../../traefik}
env_file=$traefik_dir/.env
token=${CF_DNS_API_TOKEN:-}
if [[ -z $token && -r $env_file ]]; then
  token=$(sed -n 's/^CF_DNS_API_TOKEN=//p' "$env_file" | tail -1)
fi
[[ -n $token ]] || { printf 'CF_DNS_API_TOKEN is required\n' >&2; exit 1; }

static=$traefik_dir/traefik.yml
dynamic=$traefik_dir/dynamic.yml
compose=$traefik_dir/compose.yaml
for file in "$static" "$dynamic" "$compose"; do
  [[ -f $file ]] || { printf 'Missing Traefik file: %s\n' "$file" >&2; exit 1; }
done

mkdir -p "$traefik_dir/letsencrypt"
touch "$traefik_dir/letsencrypt/acme.json"
chmod 600 "$traefik_dir/letsencrypt/acme.json"

env_tmp=$(mktemp "$traefik_dir/.env.tmp.XXXXXX")
trap 'rm -f "$env_tmp"' EXIT
if [[ -f $env_file ]]; then
  grep -v '^CF_DNS_API_TOKEN=' "$env_file" >"$env_tmp" || true
fi
printf 'CF_DNS_API_TOKEN=%s\n' "$token" >>"$env_tmp"
mv "$env_tmp" "$env_file"
chmod 600 "$env_file"

if ! grep -q '^certificatesResolvers:' "$static"; then
  static_tmp=$(mktemp "$traefik_dir/traefik.yml.tmp.XXXXXX")
  awk '1; END {
    print ""
    print "certificatesResolvers:"
    print "  letsencrypt:"
    print "    acme:"
    print "      storage: /letsencrypt/acme.json"
    print "      dnsChallenge:"
    print "        provider: cloudflare"
    print "        resolvers:"
    print "          - \"1.1.1.1:53\""
    print "          - \"8.8.8.8:53\""
  }' "$static" >"$static_tmp"
  mv "$static_tmp" "$static"
fi

if ! grep -A16 '^    plane-router:' "$dynamic" | grep -q 'certResolver: letsencrypt'; then
  dynamic_tmp=$(mktemp "$traefik_dir/dynamic.yml.tmp.XXXXXX")
  awk '
    { print }
    /^      service: plane-service$/ {
      print "      tls:"
      print "        certResolver: letsencrypt"
    }
  ' "$dynamic" >"$dynamic_tmp"
  mv "$dynamic_tmp" "$dynamic"
fi

if ! grep -A12 '^  traefik:' "$compose" | grep -q '^    env_file:'; then
  compose_tmp=$(mktemp "$traefik_dir/compose.yaml.tmp.XXXXXX")
  awk '
    { print }
    /^    image: traefik:/ {
      print "    env_file:"
      print "      - .env"
    }
  ' "$compose" >"$compose_tmp"
  mv "$compose_tmp" "$compose"
fi

if ! grep -q -- './letsencrypt:/letsencrypt' "$compose"; then
  compose_tmp=$(mktemp "$traefik_dir/compose.yaml.tmp.XXXXXX")
  awk '
    { print }
    /\.\/dynamic\.yml:\/etc\/traefik\/dynamic\.yml:ro/ {
      print "      - ./letsencrypt:/letsencrypt"
    }
  ' "$compose" >"$compose_tmp"
  mv "$compose_tmp" "$compose"
fi

printf 'Traefik ACME DNS-01 configuration prepared\n'
