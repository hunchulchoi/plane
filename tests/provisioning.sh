#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
tmp_dir=$(mktemp -d)
trap 'status=$?; rm -rf "$tmp_dir"; exit "$status"' EXIT

# shellcheck source=/dev/null
source "$repo_root/scripts/lib/env.sh"

fixture="$tmp_dir/input.env"
output="$tmp_dir/output.env"
printf '%s\n' 'POSTGRES_USER="admin"' 'POSTGRES_PASSWORD=admin-secret' >"$fixture"

test "$(read_env_value "$fixture" POSTGRES_USER)" = admin
upsert_env "$output" POSTGRES_PASSWORD first
upsert_env "$output" POSTGRES_PASSWORD second
test "$(grep -c '^POSTGRES_PASSWORD=' "$output")" -eq 1
test "$(read_env_value "$output" POSTGRES_PASSWORD)" = second
test "$(stat -c %a "$output")" = 600
secret=$(generate_secret 24)
test "${#secret}" -eq 48

generated="$tmp_dir/generated.env"
ENV_EXAMPLE="$repo_root/.env.example" ENV_FILE="$generated" "$repo_root/scripts/generate-env.sh" >/dev/null
test "$(stat -c %a "$generated")" = 600
! grep -q 'replace-with-generated-value' "$generated"
before=$(sha256sum "$generated")
ENV_EXAMPLE="$repo_root/.env.example" ENV_FILE="$generated" "$repo_root/scripts/generate-env.sh" >/dev/null
test "$before" = "$(sha256sum "$generated")"

mkdir -p "$tmp_dir/shared/postgres" "$tmp_dir/shared/minio"
printf '%s\n' 'POSTGRES_USER=shared-admin' 'POSTGRES_PASSWORD=shared-db-secret' >"$tmp_dir/shared/postgres/.env"
printf '%s\n' 'MINIO_ROOT_USER=shared-root' 'MINIO_ROOT_PASSWORD=shared-minio-secret' >"$tmp_dir/shared/minio/.env"

dry_run=$(DRY_RUN=1 SHARED_CONFIG_ROOT="$tmp_dir/shared" ENV_FILE="$generated" \
  "$repo_root/scripts/provision-shared-services.sh")

grep -q 'PostgreSQL role/database: plane' <<<"$dry_run"
grep -q 'MinIO bucket/user/policy: plane' <<<"$dry_run"
grep -q 'MinIO CORS origin: https://plane.devfor.link' <<<"$dry_run"
! grep -q 'shared-db-secret\|shared-minio-secret' <<<"$dry_run"

fake_bin="$tmp_dir/bin"
mkdir -p "$fake_bin"
cat >"$fake_bin/docker" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >>"$FAKE_DOCKER_LOG"
if [[ ${1:-} == inspect ]]; then
  echo true
  exit 0
fi
if [[ ${1:-} == exec ]]; then
  for arg in "$@"; do
    if [[ $arg == *'\gexec'* || $arg == *":'plane_password'"* ]]; then
      echo 'psql client commands must be supplied on stdin' >&2
      exit 99
    fi
  done
  cat >/dev/null
  exit 0
fi
if [[ ${1:-} == run ]]; then
  shift
  work_dir=
  while (($#)); do
    if [[ $1 == -v ]]; then
      shift
      [[ ${1:-} == *:/work:ro ]] && work_dir=${1%%:*}
    fi
    shift || true
  done
  [[ -n $work_dir && -f $work_dir/cors.xml ]] || exit 97
  grep -q '<CORSConfiguration>' "$work_dir/cors.xml" || exit 97
  grep -q '<AllowedOrigin>https://plane.devfor.link</AllowedOrigin>' "$work_dir/cors.xml" || exit 97
  exit 0
fi
exit 98
SH
chmod +x "$fake_bin/docker"

FAKE_DOCKER_LOG="$tmp_dir/fake-docker.log" PATH="$fake_bin:$PATH" SHARED_CONFIG_ROOT="$tmp_dir/shared" ENV_FILE="$generated" \
  "$repo_root/scripts/provision-shared-services.sh" >/dev/null
grep -q '^run ' "$tmp_dir/fake-docker.log"
