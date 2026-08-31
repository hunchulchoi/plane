#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=lib/env.sh
source "$repo_root/scripts/lib/env.sh"

env_example=${ENV_EXAMPLE:-$repo_root/.env.example}
env_file=${ENV_FILE:-$repo_root/.env}

if [[ -e $env_file ]]; then
  chmod 600 "$env_file"
  printf 'Environment already exists: %s\n' "$env_file"
  exit 0
fi

install -m 600 "$env_example" "$env_file"
for key in SECRET_KEY LIVE_SERVER_SECRET_KEY POSTGRES_PASSWORD RABBITMQ_PASSWORD AWS_SECRET_ACCESS_KEY; do
  if [[ $(read_env_value "$env_file" "$key") == replace-with-generated-value ]]; then
    upsert_env "$env_file" "$key" "$(generate_secret 32)"
    printf 'Generated %s\n' "$key"
  fi
done
