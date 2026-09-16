# plane CLI

Zero-dependency Python wrapper for the Plane REST + webapp API
(originally from [JinkoLLC/plane-skill](https://github.com/JinkoLLC/plane-skill),
customized for this deployment).

## Install / update on a new machine

```bash
# script
mkdir -p ~/.local/bin
cp tools/plane-cli/plane ~/.local/bin/plane
chmod +x ~/.local/bin/plane

# agent skill
mkdir -p ~/.agents/skills/plane
cp tools/plane-cli/SKILL.md ~/.agents/skills/plane/SKILL.md
```

Or without cloning:

```bash
curl -o ~/.local/bin/plane \
  "https://forgejo.dgst.me/choihunchul/plane/raw/branch/master/tools/plane-cli/plane"
chmod +x ~/.local/bin/plane
```

## Config

```bash
mkdir -p ~/.config/plane
cat > ~/.config/plane/env <<'ENVEOF'
PLANE_API_KEY="<personal access token>"
PLANE_WORKSPACE="zodiac"
PLANE_BASE_URL="https://plane.devfor.link"
ENVEOF
```

## Local changes vs upstream

- `pages create/update` write content via `pages/{id}/description/` with
  `regenerate_binary` so description_html/json/binary stay in sync.
- `--file`/`--description` convert Markdown to editor HTML.
- `comments list` reads the comments endpoint (activities exclude comments).
- `api()` supports `fatal=False` for soft-fail fallbacks.
