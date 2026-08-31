#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=lib/env.sh
source "$repo_root/scripts/lib/env.sh"
env_file=${ENV_FILE:-$repo_root/.env}
compose_file=${COMPOSE_FILE:-$repo_root/compose.custom.yaml}
[[ -r $env_file ]] || { printf 'Missing environment file: %s\n' "$env_file" >&2; exit 1; }

export PLANE_ENV_FILE=$env_file
compose=(docker compose --env-file "$env_file" -f "$compose_file")
required=(web admin space live api worker beat-worker plane-redis plane-mq proxy)
running=$("${compose[@]}" ps --services --filter status=running)
for service in "${required[@]}"; do
  grep -qx "$service" <<<"$running" || { printf 'Service is not running: %s\n' "$service" >&2; exit 1; }
done

db_password=$(read_env_value "$env_file" POSTGRES_PASSWORD)
docker exec -e "PGPASSWORD=$db_password" postgres psql -v ON_ERROR_STOP=1 -U plane -d plane -Atqc 'SELECT 1' | grep -qx 1

s3_access=$(read_env_value "$env_file" AWS_ACCESS_KEY_ID)
s3_secret=$(read_env_value "$env_file" AWS_SECRET_ACCESS_KEY)
probe="verification-$(date +%s)-$$"
docker run --rm --network host -e "S3_ACCESS=$s3_access" -e "S3_SECRET=$s3_secret" -e "PROBE=$probe" \
  --entrypoint /bin/sh minio/mc -ec '
    mc alias set plane http://127.0.0.1:9000 "$S3_ACCESS" "$S3_SECRET" >/dev/null
    printf verify | mc pipe "plane/plane/$PROBE" >/dev/null
    mc stat "plane/plane/$PROBE" >/dev/null
    mc rm "plane/plane/$PROBE" >/dev/null
  '

retry_url() {
  local attempts=24
  while ! curl --fail --silent --show-error --output /dev/null "$@"; do
    ((attempts--)) || return 1
    sleep 5
  done
}
retry_url http://127.0.0.1:8220/
retry_url http://127.0.0.1:8220/api/instances/

if getent ahosts plane.devfor.link >/dev/null 2>&1; then
  # The shared Traefik currently serves its generated self-signed certificate.
  retry_url --insecure https://plane.devfor.link/
  s3_status=$(curl --insecure --silent --show-error --output /dev/null --write-out '%{http_code}' https://s3.devfor.link/plane/)
  [[ $s3_status =~ ^(200|403)$ ]] || { printf 'Unexpected S3 status: %s\n' "$s3_status" >&2; exit 1; }
else
  printf 'Public DNS check skipped: plane.devfor.link does not resolve\n'
fi
printf 'Plane verification passed\n'
