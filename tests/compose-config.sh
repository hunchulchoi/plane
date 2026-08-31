#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$repo_root"

rendered=$(mktemp)
trap 'rm -f "$rendered"' EXIT

PLANE_ENV_FILE=.env.example docker compose --env-file .env.example -f compose.custom.yaml config --format json >"$rendered"

node - "$rendered" <<'NODE'
const fs = require("fs");
const config = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const required = [
  "web", "admin", "space", "live", "api", "worker", "beat-worker",
  "migrator", "plane-redis", "plane-mq", "proxy",
];

for (const service of required) {
  if (!config.services[service]) throw new Error(`missing service: ${service}`);
}
for (const forbidden of ["plane-db", "plane-minio"]) {
  if (config.services[forbidden]) throw new Error(`forbidden duplicate service: ${forbidden}`);
}

const proxyPorts = config.services.proxy.ports ?? [];
if (!proxyPorts.some((port) =>
  port.host_ip === "127.0.0.1" && Number(port.published) === 8220 && Number(port.target) === 80
)) throw new Error("proxy must publish 127.0.0.1:8220 to container port 80");

for (const service of ["api", "worker", "beat-worker", "migrator"]) {
  const extraHosts = config.services[service].extra_hosts ?? {};
  const hasHostGateway = Array.isArray(extraHosts)
    ? extraHosts.includes("host.docker.internal=host-gateway")
    : extraHosts["host.docker.internal"] === "host-gateway";
  if (!hasHostGateway) {
    throw new Error(`${service} cannot reach shared host services`);
  }
}

for (const service of ["web", "admin", "space", "live", "api", "proxy"]) {
  if (!config.services[service].build) throw new Error(`${service} is not built from source`);
  if (!String(config.services[service].image ?? "").startsWith("plane-custom-")) {
    throw new Error(`${service} image is not locally namespaced`);
  }
}
NODE
