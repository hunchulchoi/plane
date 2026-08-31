#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT

fake_bin="$tmp_dir/bin"
docker_log="$tmp_dir/docker.log"
mkdir -p "$fake_bin"
cat >"$fake_bin/docker" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >>"$DOCKER_LOG"
if [[ " $* " == *" config --services "* ]]; then
  printf '%s\n' web admin space live api worker beat-worker migrator plane-redis plane-mq proxy
fi
SH
chmod +x "$fake_bin/docker"

env_file="$tmp_dir/plane.env"
cp "$repo_root/.env.example" "$env_file"

PATH="$fake_bin:$PATH" DOCKER_LOG="$docker_log" ENV_FILE="$env_file" \
  "$repo_root/scripts/rebuild.sh" web admin
grep -q ' build web admin$' "$docker_log"
grep -q ' up -d web admin$' "$docker_log"
! grep -q 'run --rm migrator' "$docker_log"

: >"$docker_log"
PATH="$fake_bin:$PATH" DOCKER_LOG="$docker_log" ENV_FILE="$env_file" \
  "$repo_root/scripts/rebuild.sh" api
grep -q ' build api$' "$docker_log"
grep -q 'run --rm migrator' "$docker_log"
grep -q ' up -d api$' "$docker_log"

deploy_output=$(DRY_RUN=1 ENV_FILE="$env_file" "$repo_root/scripts/deploy.sh")
expected=(generate-env provision-shared-services compose-config compose-build start-dependencies migrate start-applications install-traefik-route verify)
previous=0
for marker in "${expected[@]}"; do
  line=$(grep -n "^$marker$" <<<"$deploy_output" | cut -d: -f1)
  test -n "$line"
  test "$line" -gt "$previous"
  previous=$line
done

# Deploy runs the migrator with --rm, so verification must not require its
# container to remain after a successful migration.
! grep -q 'ps -aq migrator' "$repo_root/scripts/verify.sh"
# Plane must retain its publicly trusted ACME certificate. A private S3 bucket
# correctly returns 403 for an anonymous bucket request.
grep -q 'retry_url https://plane.devfor.link/' "$repo_root/scripts/verify.sh"
if grep -q 'retry_url --insecure https://plane.devfor.link/' "$repo_root/scripts/verify.sh"; then
  printf 'Plane verification must enforce its public ACME certificate\n' >&2
  exit 1
fi
grep -q '200|403' "$repo_root/scripts/verify.sh"
if grep -q 's3_status=$(curl --insecure' "$repo_root/scripts/verify.sh"; then
  printf 'S3 verification must enforce its public ACME certificate\n' >&2
  exit 1
fi
