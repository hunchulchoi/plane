# Forgejo repository integration

Workspace administrators can connect repositories under **Workspace settings → Integrations → Forgejo**. The administrator must also be an active member of the selected, unarchived project. Each connection is scoped to exactly one project and one HTTPS repository URL.

## Setup

1. Choose the Plane project and enter `https://forgejo.example.com/owner/repository`.
2. Click **Connect repository**, then copy the webhook URL and secret. The secret is shown only on creation and stored encrypted using Plane's instance secret key.
3. In Forgejo, open the repository's **Settings → Webhooks → Add webhook → Forgejo** (the Gitea type also works).
4. Set the target URL and secret from Plane, method **POST**, content type **application/json**, and enable **Push** and **Pull Request** events. Activate the webhook.
5. Include a Plane work item key in a commit message or PR title/body, for example `Fix PROJ-123 session expiry`.

Incoming events add links to matching work items' existing **Links** section. A push adds individual commit links. PR creation, edits, reopening, closing and merging update the same PR link, including its status in the title. A PR retains its already linked work items when its title/body no longer mentions them. Older PR events with a source update timestamp do not overwrite a newer PR status. Reconnecting the same repository resumes updates to its existing links. Only work items in the mapped project are matched; matching is case insensitive and requires the complete project key. Draft, archived, deleted, and triage work items are excluded.

Repository mapping, signed event handling and work item links require no Forgejo access token. Plane does not fetch repository contents or make outbound Forgejo API calls. Existing commits/PRs are not backfilled: links appear after a matching event is delivered. This integration does not change work item states or sync Forgejo issues/comments. Forgejo webhook delivery logs show response errors and allow redelivery.

## Security and lifecycle

- Accepts `X-Forgejo-Signature` / `X-Gitea-Signature` HMAC-SHA256 over the exact raw body, using constant time comparison.
- Checks the payload repository URL against the configured connection and derives all link destinations from that trusted URL.
- Deduplicates delivery IDs within each connection, with an atomic transaction and row lock. Without a delivery ID, the body SHA256 is used.
- Validates the complete event before writing; invalid events leave no partial links. Maximum body size is 2 MiB and maximum commits per event is 2000.
- Deleting a mapping stops incoming events and deletes its delivery receipts. Existing work item links remain. Remove the unused webhook in Forgejo as well.
- To rotate a secret, disconnect/reconnect and replace the webhook URL and secret in Forgejo. Old URLs stop working.
- Delivery receipts are retained until their mapping is deleted.
- Webhook requests have a separate limit of 120 requests/minute per connection and sender IP; they do not consume the shared anonymous API limit.
- A valid `ping` records connectivity. Unhandled event types return `{"ignored": true}`.
- Each project's repository can be mapped once; the same repository may map to multiple projects using separate webhooks.
- Repository URLs use `https://host[:port]/owner/repo`; instance subpaths are currently unsupported.

## Session API

Workspace administrator access is required for management; normal Plane session authentication and origin checks apply. Secrets are never returned by list calls.

- `GET /api/workspaces/{slug}/forgejo-repositories/`: accessible mappings, target webhook URL, project name and last received time.
- `POST /api/workspaces/{slug}/forgejo-repositories/`: `{ "project_id": "uuid", "repository_url": "https://forgejo.example.com/owner/repo" }`. Returns `201`, the mapping and one-time secret. Duplicate mappings return `409`.
- `DELETE /api/workspaces/{slug}/forgejo-repositories/{id}/`: returns `204`.
- `POST /api/integrations/forgejo/{id}/webhook/`: signature-authenticated event receiver. Returns `{"linked": N}` or `{"duplicate": true}`. Bad signatures return `403`; mismatched repositories or malformed event fields return `400`.

Apply database migration `0128_forgejo` and deploy API/web images before using the integration. No production webhook or repository configuration is changed by installing this feature.

Forgejo event format and signature reference: <https://forgejo.org/docs/latest/user/repository/webhooks/>.
