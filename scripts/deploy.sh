#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
env_file=${ENV_FILE:-$repo_root/.env}
compose_file=${COMPOSE_FILE:-$repo_root/compose.custom.yaml}

if [[ ${DRY_RUN:-0} == 1 ]]; then
  printf '%s\n' generate-env provision-shared-services compose-config compose-build \
    start-dependencies migrate start-applications install-traefik-route verify
  exit 0
fi

ENV_FILE=$env_file "$repo_root/scripts/generate-env.sh"
ENV_FILE=$env_file "$repo_root/scripts/provision-shared-services.sh"
export PLANE_ENV_FILE=$env_file
compose=(docker compose --env-file "$env_file" -f "$compose_file")
"${compose[@]}" config >/dev/null
"${compose[@]}" build
"${compose[@]}" up -d plane-redis plane-mq
"${compose[@]}" run --rm migrator
"${compose[@]}" up -d web admin space live api worker beat-worker proxy
"$repo_root/scripts/install-traefik-route.sh"
ENV_FILE=$env_file "$repo_root/scripts/verify.sh"
