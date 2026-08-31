#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
env_file=${ENV_FILE:-$repo_root/.env}
compose_file=${COMPOSE_FILE:-$repo_root/compose.custom.yaml}
[[ -r $env_file ]] || { printf 'Missing environment file: %s\n' "$env_file" >&2; exit 1; }

compose=(docker compose --env-file "$env_file" -f "$compose_file")
export PLANE_ENV_FILE=$env_file
available=$("${compose[@]}" config --services)
if (($# == 0)); then set -- web admin space live api worker beat-worker proxy; fi
for service in "$@"; do
  grep -qx "$service" <<<"$available" || { printf 'Unknown service: %s\n' "$service" >&2; exit 1; }
  case "$service" in web|admin|space|live|api|worker|beat-worker|proxy) ;; *) exit 1 ;; esac
done

"${compose[@]}" build "$@"
needs_migration=0
for service in "$@"; do case "$service" in api|worker|beat-worker) needs_migration=1 ;; esac; done
if ((needs_migration)); then
  "${compose[@]}" up -d plane-redis plane-mq
  "${compose[@]}" run --rm migrator
fi
"${compose[@]}" up -d "$@"
