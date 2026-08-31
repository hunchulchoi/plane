# Source-built Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run Plane CE from `custom/v1.4.2` at `https://plane.devfor.link`, with isolated credentials on the shared PostgreSQL and MinIO services.

**Architecture:** A custom Compose file builds all Plane application images from this checkout, runs Plane-specific Valkey and RabbitMQ, and reaches host-published PostgreSQL through `host.docker.internal`. Plane's Caddy proxy binds to `127.0.0.1:8220`; existing Traefik terminates TLS, while browser-visible object URLs use `https://s3.devfor.link`.

**Tech Stack:** Docker Compose v2, Plane v1.4.2, PostgreSQL 18, MinIO, Valkey 7.2, RabbitMQ 3.13, Caddy 2, Traefik 3.7, Bash

**Spec:** `docs/superpowers/specs/2026-08-31-source-built-plane-design.md`

## Global Constraints

- Build every Plane application image locally; use no prebuilt Plane application image.
- Run no PostgreSQL or MinIO service in the Plane project.
- Create only the dedicated PostgreSQL role/database and MinIO bucket/user/policy named `plane`.
- Store generated secrets in ignored, mode-0600 `.env`; commit only `.env.example`.
- Publish Plane only at `127.0.0.1:8220` and route `plane.devfor.link` through existing Traefik.
- Use `https://s3.devfor.link` for presigned browser uploads.
- Never delete unrelated shared resources; preserve AGPL-3.0 notices and obligations.

---

### Task 1: Source-build production Compose

**Files:**
- Create: `compose.custom.yaml`, `.env.example`, `tests/compose-config.sh`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: upstream `apps/*/Dockerfile.*` files.
- Produces: services `web`, `admin`, `space`, `live`, `api`, `worker`, `beat-worker`, `migrator`, `plane-redis`, `plane-mq`, and `proxy`.

- [ ] **Step 1: Write the failing structural test**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
test -f compose.custom.yaml
! grep -Eq '^  (plane-db|plane-minio):' compose.custom.yaml
grep -q '127.0.0.1:${PLANE_HTTP_PORT:-8220}:80' compose.custom.yaml
grep -q 'host.docker.internal:host-gateway' compose.custom.yaml
services=$(docker compose --env-file .env.example -f compose.custom.yaml config --services)
for name in web admin space live api worker beat-worker migrator plane-redis plane-mq proxy; do
  grep -qx "$name" <<<"$services"
done
```

- [ ] **Step 2: Verify failure**

Run: `bash tests/compose-config.sh`

Expected: FAIL because the new files do not exist.

- [ ] **Step 3: Add the environment contract and ignore rule**

Create `.env.example` with exact keys: `COMPOSE_PROJECT_NAME`, `PLANE_HTTP_PORT`, `WEB_URL`, `APP_DOMAIN`, `SECRET_KEY`, `LIVE_SERVER_SECRET_KEY`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `REDIS_HOST`, `REDIS_PORT`, `REDIS_URL`, `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD`, `RABBITMQ_VHOST`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_ENDPOINT_URL`, `AWS_S3_BUCKET_NAME`, `USE_MINIO`, `MINIO_ENDPOINT_SSL`, `FILE_SIZE_LIMIT`, `SIGNED_URL_EXPIRATION`, `DEBUG`, `CORS_ALLOWED_ORIGINS`, `GUNICORN_WORKERS`, and `API_KEY_RATE_LIMIT`.

Use `plane.devfor.link`, `host.docker.internal:5432`, bucket/database/user `plane`, `USE_MINIO=0`, `MINIO_ENDPOINT_SSL=1`, and `https://s3.devfor.link`. Use `replace-with-generated-value` only for secrets. Add `.env` to `.gitignore`.

- [ ] **Step 4: Implement `compose.custom.yaml`**

Adapt upstream `docker-compose.yml`. Retain source build contexts and Dockerfiles; assign `plane-custom-*` image names. Share the backend image across API/workers/migrator. Remove `plane-db`, `plane-minio`, their volumes, and dependencies. Add `host.docker.internal:host-gateway` to backend services. Retain Valkey/RabbitMQ volumes and health checks. Bind only:

```yaml
ports:
  - "127.0.0.1:${PLANE_HTTP_PORT:-8220}:80"
```

Use `restart: unless-stopped`, except migrator `restart: "no"`.

- [ ] **Step 5: Verify and commit**

Run: `bash tests/compose-config.sh && docker compose --env-file .env.example -f compose.custom.yaml config >/dev/null`

Expected: PASS.

```bash
git add compose.custom.yaml .env.example .gitignore tests/compose-config.sh
git commit -m "build: add source-built production compose"
```

### Task 2: Shared-service provisioning

**Files:**
- Create: `scripts/lib/env.sh`, `scripts/generate-env.sh`, `scripts/provision-shared-services.sh`, `tests/provisioning.sh`

**Interfaces:**
- Consumes: `../postgres/.env`, `../minio/.env`, and containers `postgres`, `minio`.
- Produces: `.env`, PostgreSQL role/database `plane`, MinIO bucket/user/policy `plane`, and CORS for `https://plane.devfor.link`.
- Produces functions `read_env_value(file,key)`, `upsert_env(file,key,value)`, and `generate_secret(bytes)`.

- [ ] **Step 1: Write failing helper/dry-run tests**

Use fake env fixtures under `mktemp -d`; never read real secret values into test output. Assert exact-key parsing, one-line idempotent replacement, mode `0600`, random secret length, and:

```bash
DRY_RUN=1 scripts/provision-shared-services.sh | grep -q 'CREATE DATABASE plane'
DRY_RUN=1 scripts/provision-shared-services.sh | grep -q 'plane-bucket-policy'
```

- [ ] **Step 2: Verify failure**

Run: `bash tests/provisioning.sh`

Expected: FAIL because the scripts do not exist.

- [ ] **Step 3: Implement secret-safe helpers and generation**

Use `set -euo pipefail`. Parse exact `KEY=` lines without sourcing files. Update via a same-directory temporary file and `chmod 600`. Generate values with `openssl rand -hex`. `generate-env.sh` copies `.env.example` only when `.env` is absent, replaces each secret placeholder independently, never replaces existing values, and prints key names only.

- [ ] **Step 4: Implement idempotent provisioning**

The provisioning script must verify Docker and both shared containers, then:

- use `docker exec postgres psql` with fixed SQL identifiers and a `psql --set` password variable;
- create/alter role `plane`, create database `plane` only if absent, and set its owner;
- use an ephemeral `minio/mc` client to create bucket `plane`;
- create `plane-bucket-policy` limited to `arn:aws:s3:::plane` and `arn:aws:s3:::plane/*`;
- create/update user `plane`, attach the policy, and install CORS allowing `https://plane.devfor.link` with GET/POST/PUT/DELETE/HEAD;
- clean temporary policy/CORS files with a trap;
- make `DRY_RUN=1` perform no Docker call and redact all secrets.

- [ ] **Step 5: Verify and commit**

Run: `bash tests/provisioning.sh && bash -n scripts/lib/env.sh scripts/generate-env.sh scripts/provision-shared-services.sh`

Expected: PASS.

```bash
git add scripts/lib/env.sh scripts/generate-env.sh scripts/provision-shared-services.sh tests/provisioning.sh
git commit -m "ops: provision shared Plane storage"
```

### Task 3: Proxy and Traefik routing

**Files:**
- Modify: `apps/proxy/Caddyfile.ce`
- Create: `deploy/traefik-plane.yml`, `scripts/install-traefik-route.sh`, `tests/proxy-routing.sh`
- Installation-only modification: `../traefik/dynamic.yml`

**Interfaces:**
- Consumes: `127.0.0.1:8220` Plane proxy.
- Produces: Traefik `plane-router` and `plane-service`.

- [ ] **Step 1: Write and run the failing route test**

Assert that Caddy contains no `plane-minio:9000`; the fragment contains `plane.devfor.link`, `http://host.docker.internal:8220`, `crowdsec-bouncer`, and `global-ratelimit`; and the installer passes `bash -n`.

Run: `bash tests/proxy-routing.sh`

Expected: FAIL on the upstream MinIO proxy and missing files.

- [ ] **Step 2: Make Caddy external-storage aware**

Remove only the two `reverse_proxy /{$BUCKET_NAME}... plane-minio:9000` directives. Preserve web/API/admin/space/live routing.

- [ ] **Step 3: Add the route fragment and safe installer**

The fragment defines `Host(`plane.devfor.link`)`, entrypoints `web`/`websecure`, established security middleware, and a load balancer server at `http://host.docker.internal:8220`. The installer backs up `../traefik/dynamic.yml`, inserts under exact `routers:` and `services:` anchors, exits 0 if both keys already exist, refuses half-configured state, validates through the Traefik container, and restores on failure.

- [ ] **Step 4: Verify and commit**

Run: `bash tests/proxy-routing.sh`

Expected: PASS.

```bash
git add apps/proxy/Caddyfile.ce deploy/traefik-plane.yml scripts/install-traefik-route.sh tests/proxy-routing.sh
git commit -m "ops: route Plane through shared Traefik"
```

### Task 4: Operator commands and documentation

**Files:**
- Create: `scripts/rebuild.sh`, `scripts/deploy.sh`, `scripts/verify.sh`, `tests/operations.sh`
- Modify: `README.md`

**Interfaces:**
- Produces commands `deploy.sh`, `rebuild.sh [service...]`, and `verify.sh`.

- [ ] **Step 1: Write and run failing command-contract tests**

Put a fake `docker` in a temporary `PATH`, log arguments, and assert that `rebuild.sh web admin` invokes Compose build/up only for those services; `rebuild.sh api` also runs migrator; and `DRY_RUN=1 deploy.sh` orders generation, provisioning, configuration, build, migration, startup, Traefik installation, and verification.

Run: `bash tests/operations.sh`

Expected: FAIL because scripts do not exist.

- [ ] **Step 2: Implement rebuild and deploy commands**

All scripts resolve repository root from their location and use strict mode. `rebuild.sh` validates names with `compose config --services`, defaults to all local application images, and migrates for backend selections. `deploy.sh` executes:

```text
generate environment -> provision shared services -> validate Compose -> build
-> start Valkey/RabbitMQ -> run migrator -> start applications/proxy
-> install Traefik route -> verify
```

Both support secret-safe `DRY_RUN=1`.

- [ ] **Step 3: Implement verification**

Require every long-running service and migrator exit 0. Run dedicated PostgreSQL `SELECT 1`; use ephemeral `minio/mc` to put/stat/remove a random object; retry loopback `/` and `/api/instances/` for 120 seconds. When DNS resolves, require public HTTPS and a presigned URL using `s3.devfor.link`. On failure, print only container names and last 100 log lines, never environment values.

- [ ] **Step 4: Document operations**

Add shared prerequisites, first deploy, targeted rebuild examples, `.env` handling, rollback, AGPL reminder, absent SMTP, and upstream update commands:

```bash
git fetch upstream --tags
git merge vNEXT
git push origin custom/vNEXT
```

- [ ] **Step 5: Verify and commit**

Run: `bash tests/operations.sh && bash tests/compose-config.sh && bash tests/provisioning.sh && bash tests/proxy-routing.sh && bash -n scripts/*.sh scripts/lib/*.sh`

Expected: PASS.

```bash
git add scripts/rebuild.sh scripts/deploy.sh scripts/verify.sh tests/operations.sh README.md
git commit -m "ops: add Plane deployment workflow"
```

### Task 5: Build, install, and verify

**Files:**
- Generate, never commit: `.env`
- Installation-only modification: `../traefik/dynamic.yml`
- Update: this plan's completed checkboxes

**Interfaces:**
- Consumes: Tasks 1-4.
- Produces: running, verified source-built Plane and Forgejo history.

- [ ] **Step 1: Run the complete static suite**

Run: `bash tests/compose-config.sh && bash tests/provisioning.sh && bash tests/proxy-routing.sh && bash tests/operations.sh && git diff --check`

Expected: PASS before any shared-state change.

- [ ] **Step 2: Provision and route**

Run: `./scripts/generate-env.sh && ./scripts/provision-shared-services.sh && ./scripts/install-traefik-route.sh`

Expected: `.env` mode 600; isolated database/bucket/user/policy exist; validated Traefik config is installed with a backup.

- [ ] **Step 3: Build and deploy from source**

Run: `./scripts/deploy.sh`

Expected: local `plane-custom-*` images build; migrator exits 0; long-running services become healthy.

- [ ] **Step 4: Verify end to end**

Run: `./scripts/verify.sh`

Expected: database, object probe, loopback HTTP, public HTTPS, and S3 endpoint checks pass. If DNS is not pointed here, report only the public check as an external blocker and retain local evidence.

- [ ] **Step 5: Audit and record completion**

Run: `test "$(stat -c %a .env)" = 600 && git check-ignore .env && git diff --check && git status --short`

Expected: `.env` ignored; only checkbox updates remain. Commit those updates and push:

```bash
git add docs/superpowers/plans/2026-08-31-source-built-plane.md
git commit -m "docs: record Plane deployment verification"
git push origin custom/v1.4.2
```
