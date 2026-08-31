#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=lib/env.sh
source "$repo_root/scripts/lib/env.sh"

env_file=${ENV_FILE:-$repo_root/.env}
shared_root=${SHARED_CONFIG_ROOT:-$repo_root/../..}
postgres_env="$shared_root/postgres/.env"
minio_env="$shared_root/minio/.env"

"$repo_root/scripts/generate-env.sh" >/dev/null

for file in "$env_file" "$postgres_env" "$minio_env"; do
  [[ -r $file ]] || { printf 'Required environment file is not readable: %s\n' "$file" >&2; exit 1; }
done

plane_db_password=$(read_env_value "$env_file" POSTGRES_PASSWORD)
plane_s3_access=$(read_env_value "$env_file" AWS_ACCESS_KEY_ID)
plane_s3_secret=$(read_env_value "$env_file" AWS_SECRET_ACCESS_KEY)
postgres_admin=$(read_env_value "$postgres_env" POSTGRES_USER)
postgres_password=$(read_env_value "$postgres_env" POSTGRES_PASSWORD)
minio_root_user=$(read_env_value "$minio_env" MINIO_ROOT_USER)
minio_root_password=$(read_env_value "$minio_env" MINIO_ROOT_PASSWORD)

for value_name in plane_db_password plane_s3_access plane_s3_secret postgres_admin postgres_password minio_root_user minio_root_password; do
  [[ -n ${!value_name} ]] || { printf 'Required value is empty: %s\n' "$value_name" >&2; exit 1; }
done

if [[ ${DRY_RUN:-0} == 1 ]]; then
  printf '%s\n' \
    'PostgreSQL role/database: plane' \
    'MinIO bucket/user/policy: plane / plane / plane-bucket-policy' \
    'MinIO CORS origin: https://plane.devfor.link'
  exit 0
fi

command -v docker >/dev/null || { printf 'docker is required\n' >&2; exit 1; }
for container in postgres minio; do
  [[ $(docker inspect -f '{{.State.Running}}' "$container" 2>/dev/null) == true ]] || {
    printf 'Required container is not running: %s\n' "$container" >&2
    exit 1
  }
done

psql=(docker exec -i -e "PGPASSWORD=$postgres_password" postgres psql -v ON_ERROR_STOP=1 -U "$postgres_admin" -d postgres --set="plane_password=$plane_db_password")
printf '%s\n' \
  "SELECT 'CREATE ROLE plane LOGIN' WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'plane') \\gexec" \
  "SELECT format('ALTER ROLE plane WITH LOGIN PASSWORD %L', :'plane_password') \\gexec" \
  "SELECT 'CREATE DATABASE plane OWNER plane' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'plane') \\gexec" \
  'ALTER DATABASE plane OWNER TO plane;' | "${psql[@]}"

tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT
chmod 700 "$tmp_dir"

cat >"$tmp_dir/policy.json" <<'JSON'
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["s3:GetBucketLocation","s3:ListBucket"],"Resource":["arn:aws:s3:::plane"]},{"Effect":"Allow","Action":["s3:GetObject","s3:PutObject","s3:DeleteObject"],"Resource":["arn:aws:s3:::plane/*"]}]}
JSON
cat >"$tmp_dir/cors.xml" <<'XML'
<CORSConfiguration>
  <CORSRule>
    <AllowedOrigin>https://plane.devfor.link</AllowedOrigin>
    <AllowedMethod>GET</AllowedMethod>
    <AllowedMethod>POST</AllowedMethod>
    <AllowedMethod>PUT</AllowedMethod>
    <AllowedMethod>DELETE</AllowedMethod>
    <AllowedMethod>HEAD</AllowedMethod>
    <AllowedHeader>*</AllowedHeader>
    <ExposeHeader>ETag</ExposeHeader>
    <ExposeHeader>x-amz-server-side-encryption</ExposeHeader>
    <ExposeHeader>x-amz-request-id</ExposeHeader>
    <ExposeHeader>x-amz-id-2</ExposeHeader>
    <MaxAgeSeconds>3000</MaxAgeSeconds>
  </CORSRule>
</CORSConfiguration>
XML

docker run --rm --network host \
  -e "MINIO_ROOT_USER=$minio_root_user" \
  -e "MINIO_ROOT_PASSWORD=$minio_root_password" \
  -e "PLANE_ACCESS_KEY=$plane_s3_access" \
  -e "PLANE_SECRET_KEY=$plane_s3_secret" \
  -v "$tmp_dir:/work:ro" \
  --entrypoint /bin/sh minio/mc -ec '
    mc alias set shared http://127.0.0.1:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null
    mc mb --ignore-existing shared/plane
    mc admin policy create shared plane-bucket-policy /work/policy.json
    mc admin user add shared "$PLANE_ACCESS_KEY" "$PLANE_SECRET_KEY"
    mc admin policy attach shared plane-bucket-policy --user "$PLANE_ACCESS_KEY"
    mc cors set shared/plane /work/cors.xml
  '

printf '%s\n' 'Provisioned PostgreSQL role/database: plane' 'Provisioned MinIO bucket and scoped credentials: plane'
