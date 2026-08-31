#!/usr/bin/env bash

read_env_value() {
  local file=$1 key=$2 value
  value=$(awk -v key="$key" 'index($0, key "=") == 1 { print substr($0, length(key) + 2); exit }' "$file")
  if [[ $value == \"*\" && $value == *\" ]] || [[ $value == \'*\' && $value == *\' ]]; then
    value=${value:1:${#value}-2}
  fi
  printf '%s\n' "$value"
}

upsert_env() {
  local file=$1 key=$2 value=$3 dir tmp
  dir=$(dirname "$file")
  mkdir -p "$dir"
  tmp=$(mktemp "$dir/.env-update.XXXXXX")
  if [[ -f $file ]]; then
    awk -v key="$key" -v value="$value" '
      BEGIN { found = 0 }
      index($0, key "=") == 1 {
        if (!found) print key "=" value
        found = 1
        next
      }
      { print }
      END { if (!found) print key "=" value }
    ' "$file" >"$tmp"
  else
    printf '%s=%s\n' "$key" "$value" >"$tmp"
  fi
  chmod 600 "$tmp"
  mv "$tmp" "$file"
}

generate_secret() {
  local bytes=${1:-32}
  openssl rand -hex "$bytes"
}
