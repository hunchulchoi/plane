# Source-built Plane deployment design

## Goal

Run Plane Community Edition at `https://plane.devfor.link` from locally built
source so that application behavior can be changed and redeployed. Reuse the
host's shared PostgreSQL and MinIO instances while isolating Plane's data and
credentials from other applications.

## Source and upgrade model

- Base the customization branch `custom/v1.4.2` on the latest non-prerelease
  upstream tag, `v1.4.2`.
- Keep the upstream Git history and remote so local changes remain reviewable
  and future stable tags can be merged deliberately.
- Build every Plane application image from this checkout. Do not depend on the
  prebuilt `makeplane/plane-*` application images.
- Keep deployment-only configuration at the checkout root and keep generated
  secrets in an ignored `.env` file.

## Runtime architecture

The Compose project builds and runs the Plane web, admin, space, live, API,
worker, beat worker, migrator, and application proxy services. It also runs a
Plane-specific Valkey and RabbitMQ because these are application runtime state,
not part of the shared services requested by the operator.

The Compose project does not run PostgreSQL or MinIO. Application containers
reach the host-published shared services through `host.docker.internal`, with
the Linux `host-gateway` mapping declared explicitly. PostgreSQL receives a
dedicated `plane` database and role. MinIO receives a dedicated bucket and
access credentials with permissions limited to that bucket.

The Plane proxy publishes only a loopback host port. The existing host Traefik
configuration routes `plane.devfor.link` to that port, applies the established
CrowdSec and rate-limit middleware, and terminates TLS. The public MinIO endpoint
is `https://s3.devfor.link`; using the public endpoint is required because Plane
returns presigned upload URLs to browsers.

## Configuration and secrets

An idempotent bootstrap script generates application, database, RabbitMQ,
MinIO, and live-server secrets when they do not already exist. It uses the
existing shared-service administrator credentials only while provisioning the
dedicated role, database, bucket, policy, and access key. Those administrator
credentials are not copied into Plane configuration.

The Plane `.env` contains only the dedicated runtime credentials and is ignored
by Git. A committed `.env.example` documents every required value without real
secrets. MinIO Community does not support per-bucket CORS, so provisioning
verifies that its global `api cors_allow_origin` is either `*` or explicitly
includes `https://plane.devfor.link`. The existing shared MinIO uses `*`.

SMTP and optional OAuth integrations remain disabled until their credentials
are supplied. Initial instance administration is completed through Plane's
first-run setup screen.

## Development workflow

Normal customization happens on `custom/v1.4.2`. A helper command accepts one
or more service names, rebuilds their local images, runs migrations when the API
changes, and recreates only the affected containers. A full build command is
also available for dependency or cross-application changes.

Generated image names include a local `plane-custom` prefix so they cannot be
confused with upstream release images. Persistent Valkey and RabbitMQ data use
named volumes. Application logs remain available through Docker and the
existing host logging stack.

## Failure handling

- Bootstrap stops before deployment if Docker, the shared PostgreSQL container,
  the shared MinIO container, DNS-facing configuration, or required credentials
  are unavailable.
- Provisioning operations are idempotent and safe to rerun.
- The migrator must finish successfully before API and worker readiness is
  accepted.
- Health checks and dependency conditions prevent Traefik from receiving a
  knowingly unhealthy application.
- No shared database, bucket, user, or access key is deleted automatically.

## Verification

Verification consists of:

1. validating the rendered Compose configuration;
2. building all locally sourced application images;
3. confirming the dedicated PostgreSQL role can connect only to its database;
4. confirming the MinIO credentials can write, read, and delete a probe object
   in the Plane bucket;
5. running database migrations and checking all required container health;
6. requesting the Plane root and API instance endpoints through the loopback
   proxy and through `https://plane.devfor.link` when DNS is available; and
7. checking that generated upload URLs use `https://s3.devfor.link`.

## Scope boundaries

This installation does not customize Plane features yet; it establishes the
repeatable source-build baseline on which those changes can be made. It does
not migrate existing Plane data, configure outbound email, or alter unrelated
shared-service consumers.

Plane is licensed under AGPL-3.0. Any modified version offered over a network
must retain the applicable source-availability and license obligations.
