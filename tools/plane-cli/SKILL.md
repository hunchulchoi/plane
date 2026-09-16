---
name: plane
description: "Manage Plane.so projects and work items using the `plane` CLI. List projects, create/update/search issues, manage cycles and modules, documentation pages and their file attachments, custom views, comments, and members."
metadata: {"moltbot":{"requires":{"bins":["plane"],"env":["PLANE_API_KEY","PLANE_WORKSPACE"]},"primaryEnv":"PLANE_API_KEY","emoji":"✈️","homepage":"https://github.com/JinkoLLC/plane-skill","install":[{"id":"github","kind":"download","url":"https://raw.githubusercontent.com/JinkoLLC/plane-skill/main/scripts/plane","targetDir":"~/.local/bin/","bins":["plane"],"label":"Download plane CLI from GitHub"}]}}
---

# Plane Skill

Interact with [Plane.so](https://plane.so) project management via the `plane` CLI. Supports both cloud and self-hosted instances.

## Installation

Download the CLI script and make it executable:

```bash
curl -o ~/.local/bin/plane https://raw.githubusercontent.com/JinkoLLC/plane-skill/main/scripts/plane
chmod +x ~/.local/bin/plane
```

## Setup

Set environment variables:

```bash
export PLANE_API_KEY="your-api-key"
export PLANE_WORKSPACE="your-workspace-slug"
# Optional (defaults to https://api.plane.so, or set for self-hosted instance e.g. https://plane.devfor.link):
export PLANE_BASE_URL="https://api.plane.so"
```

Or configure persistently in `~/.config/plane/env`:

```bash
mkdir -p ~/.config/plane
cat << 'EOF' > ~/.config/plane/env
PLANE_API_KEY="your-api-key"
PLANE_WORKSPACE="your-workspace-slug"
PLANE_BASE_URL="https://plane.devfor.link"
EOF
```

Get your API key from: **Plane → Profile Settings → Personal Access Tokens**

The workspace slug is the URL path segment (e.g., for `https://app.plane.so/my-team/` or `https://plane.devfor.link/my-team/` the slug is `my-team`).

> [!NOTE]
> **API Routing Note:** Public API v1 routes (`/api/v1/workspaces/...`) are used for core entities (projects, issues, cycles, modules, members).
> Document Pages and Custom Views use webapp API routes (`/api/workspaces/{slug}/projects/{project}/pages/` and `/api/workspaces/{slug}/projects/{project}/views/`) with `X-Api-Key` header authentication.

## Commands

### Current User

```bash
plane me                      # Show authenticated user info
```

### Workspace Members

```bash
plane members                 # List all workspace members (name, email, role, ID)
```

### Projects

```bash
plane projects list                                      # List all projects
plane projects get PROJECT_ID                            # Get project details
plane projects create --name "My Project" --identifier "PROJ"  # Create project
```

### Work Items (Issues)

```bash
# List work items
plane issues list -p PROJECT_ID
plane issues list -p PROJECT_ID --priority high --assignee USER_ID

# Get details
plane issues get -p PROJECT_ID ISSUE_ID

# Create
plane issues create -p PROJECT_ID --name "Fix login bug" --priority high
plane issues create -p PROJECT_ID --name "Feature" --assignee USER_ID --label LABEL_ID
# --label also accepts names (repeatable); unknown names are created automatically
plane issues create -p PROJECT_ID --name "Feature" --label bug --label frontend

# Update
plane issues update -p PROJECT_ID ISSUE_ID --state STATE_ID --priority medium

# Assign to members
plane issues assign -p PROJECT_ID ISSUE_ID USER_ID_1 USER_ID_2

# Delete
plane issues delete -p PROJECT_ID ISSUE_ID

# Search across workspace
plane issues search "login bug"
```

### Comments

```bash
plane comments list -p PROJECT_ID -i ISSUE_ID            # List comments on a work item
plane comments list -p PROJECT_ID -i ISSUE_ID --all      # Show all activity (not just comments)
plane comments add -p PROJECT_ID -i ISSUE_ID "Looks good, merging now"  # Add a comment
```

### Cycles (Sprints)

```bash
plane cycles list -p PROJECT_ID                          # List cycles
plane cycles get -p PROJECT_ID CYCLE_ID                  # Get cycle details
plane cycles create -p PROJECT_ID --name "Sprint 1" --start 2026-01-27 --end 2026-02-10

# Manage work items in cycle
plane cycles issues -p PROJECT_ID -c CYCLE_ID            # List issues in cycle
plane cycles add-issue -p PROJECT_ID -c CYCLE_ID ISSUE_ID_1 ISSUE_ID_2   # Add issues to cycle
plane cycles remove-issue -p PROJECT_ID -c CYCLE_ID ISSUE_ID             # Remove issue from cycle
```

### Modules

```bash
plane modules list -p PROJECT_ID                         # List modules
plane modules get -p PROJECT_ID MODULE_ID                # Get module details
plane modules create -p PROJECT_ID --name "Auth Module" --description "Authentication features"

# Manage work items in module
plane modules issues -p PROJECT_ID -m MODULE_ID          # List issues linked to module
plane modules add-issue -p PROJECT_ID -m MODULE_ID ISSUE_ID_1 ISSUE_ID_2 # Link issues to module
plane modules remove-issue -p PROJECT_ID -m MODULE_ID ISSUE_ID           # Unlink issue from module
```

### Document Pages

```bash
plane pages list -p PROJECT_ID                           # List document pages in project
plane pages get -p PROJECT_ID PAGE_ID                    # Get page metadata & details
plane pages get -p PROJECT_ID PAGE_ID --content-only     # Output raw description_html content
plane pages create -p PROJECT_ID --name "Deploy Guide" --file docs/deployment.md --color "#2563EB"
plane pages update -p PROJECT_ID PAGE_ID --name "Updated Title" --file docs/deployment.md
plane pages attach -p PROJECT_ID PAGE_ID --file docs/deployment.pdf
plane pages attach -p PROJECT_ID PAGE_ID --file screenshot.png --embed
plane pages delete -p PROJECT_ID PAGE_ID                 # Delete a document page
```

`--file`/`--description` accept Markdown or raw HTML (Markdown headings, lists,
task items, tables, code fences, quotes, and inline formatting are converted).
Content writes go through the page `description/` endpoint with
`regenerate_binary`, so `description_html`/`description_json`/`description_binary`
(Yjs) stay in sync — do not PATCH `description_html` directly on `pages/{id}/`,
as the editor renders from the binary doc and will overwrite stale HTML.

### File Attachments

```bash
# Attach a file to a supported project entity
plane assets upload -p PROJECT_ID --file docs/spec.pdf \
  --entity-type ISSUE_ATTACHMENT --entity-id ISSUE_ID

# Use --content-type only when the file type cannot be inferred
plane pages attach -p PROJECT_ID PAGE_ID --file diagram.bin \
  --content-type application/octet-stream
```

Uploads use Plane's presigned three-step flow. Supported entity types are
`ISSUE_ATTACHMENT`, `ISSUE_DESCRIPTION`, `COMMENT_DESCRIPTION`,
`PAGE_DESCRIPTION`, and `DRAFT_ISSUE_DESCRIPTION`. The server's configured
attachment MIME allowlist and file-size limit remain authoritative.

Use `--embed` only for JPEG, PNG, WebP, or GIF images. It appends a Plane
`image-component` to the page body and asks the server to regenerate the page's
HTML, JSON, and Yjs editor binary together. Without `--embed`, the command only
associates the uploaded asset with the page.

### Custom Views

```bash
plane views list -p PROJECT_ID                           # List custom views in project
plane views get -p PROJECT_ID VIEW_ID                    # Get view details and query filters
plane views create -p PROJECT_ID --name "High Priority" --filters '{"priority": ["urgent", "high"]}'
plane views delete -p PROJECT_ID VIEW_ID                 # Delete a custom view
```

### States & Labels

```bash
plane states -p PROJECT_ID    # List workflow states (useful for getting state IDs)
plane labels -p PROJECT_ID    # List labels (useful for getting label IDs)
plane labels create -p PROJECT_ID --name "bug" --color "#eb5757"  # Create a label
```

## Output Formats

Default output is a formatted table. Add `-f json` for raw JSON:

```bash
plane projects list -f json
plane issues list -p PROJECT_ID -f json
plane pages list -p PROJECT_ID -f json
plane views list -p PROJECT_ID -f json
```

## Typical Workflow

1. `plane projects list` — find your project ID
2. `plane states -p PROJECT_ID` — see available states
3. `plane members` — find member IDs for assignment
4. `plane issues create -p PROJECT_ID --name "Task" --priority high --assignee USER_ID`
5. `plane modules add-issue -p PROJECT_ID -m MODULE_ID ISSUE_ID` — organize issues into modules
6. `plane pages create -p PROJECT_ID --name "Architecture" --file docs/arch.md` — attach documentation
7. `plane comments add -p PROJECT_ID -i ISSUE_ID "Started working on this"`
