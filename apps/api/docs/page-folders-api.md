# Project page folders API

Authenticate with `X-Api-Key`. All routes are relative to
`/api/v1/workspaces/{slug}/projects/{project_id}/`.

| Method | Route                       | Body                | Result               |
| ------ | --------------------------- | ------------------- | -------------------- |
| GET    | `page-folders/`             | —                   | Folder array         |
| POST   | `page-folders/`             | `{"name":"Specs"}`  | Created folder (201) |
| GET    | `page-folders/{folder_id}/` | —                   | Folder details       |
| PATCH  | `page-folders/{folder_id}/` | `{"name":"Design"}` | Renamed folder       |
| DELETE | `page-folders/{folder_id}/` | —                   | No content (204)     |

Folder objects contain `id`, `name`, `project`, and `workspace`. Names are
trimmed, required, and limited to 255 characters. Only `name` is writable;
unknown fields return 400. Folder IDs are scoped to the URL workspace and
project; accessing a folder from another project returns 404.

Permissions match the app: active project guests can read, members and admins
can create or rename, and only project admins can delete. API key rate limits
apply. Requests without active project membership are denied.

## Assign pages to folders

Create a page inside a folder:

```http
POST pages/
Content-Type: application/json
X-Api-Key: YOUR_API_KEY

{"name":"Architecture","folder":"FOLDER_UUID"}
```

Move an existing page to a folder with
`PATCH pages/{page_id}/` and `{"folder":"FOLDER_UUID"}`. Send
`{"folder":null}` to move it out of the folder. Existing page permissions and
locking rules apply. The folder must be active and belong to the URL project;
invalid or foreign folder IDs return 400.

Deleting a folder preserves its pages and clears their folder assignment,
including for soft-deleted pages. It does not delete page content.

This API manages folders and folder assignment. The page `parent` field remains
outside the public write allowlist; nested page management remains in the app.
