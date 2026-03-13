---
name: publish
description: "Publish all changed plugins/skills — bump versions, update marketplace.json, commit, push, and install locally. Use when the user says 'publish', 'release all', 'publish marketplace', or similar."
version: 1.0.3
---

# Publish Marketplace

Detect all changed plugins/skills since the last release, bump their versions, update marketplace.json, push to git, and install locally.

## Step 1: Detect Changed Plugins

Run `git diff origin/main --name-only` to get all files that have changed relative to the remote main branch.

If the current branch IS main, use the last tag or `git diff HEAD~1 --name-only` instead (compare against the last commit on remote: `git diff origin/main...HEAD --name-only`). If there are no differences (everything is already pushed), check for uncommitted/unstaged changes with `git diff --name-only` and `git diff --cached --name-only`.

Map each changed file to its plugin:
- Files under `plugins/<name>/` belong to plugin `<name>`
- Files under `skills/<name>/` also map to plugin `<name>` (legacy location)
- Files in `.claude-plugin/marketplace.json` are metadata-only, skip them
- Files in the repo root (`.gitignore`, `CLAUDE.md`, etc.) don't belong to any plugin

Build a deduplicated list of changed plugin names.

If no plugins have changed, inform the user and exit.

## Step 2: Determine Bump Type

If the user specified a bump type in `$ARGUMENTS` (e.g., `/publish patch`, `/publish minor`), use it. Otherwise ask:

- **patch** (default) — bug fixes, small changes
- **minor** — new features, backwards compatible
- **major** — breaking changes

## Step 3: Collect Version Files for Each Changed Plugin

For each changed plugin `<name>`, find ALL version references:

1. **Plugin manifest**: `plugins/<name>/.claude-plugin/plugin.json` → `"version": "x.y.z"` (if exists)
2. **Marketplace entry**: `.claude-plugin/marketplace.json` → find the plugin entry by `"name": "<name>"` and get its `"version"`
3. **SKILL.md files**: Search `plugins/<name>/**/SKILL.md` for frontmatter `version: x.y.z`
4. **Code constants**: Search `plugins/<name>/**/*.py` and `plugins/<name>/**/*.mjs` for patterns like `PLUGIN_VERSION = 'x.y.z'` or `VERSION = 'x.y.z'`

Collect all file paths with their current versions.

## Step 4: Show Summary and Confirm

Display a table for each changed plugin:

```
Changed plugins detected: persona-panel, md-html-docs

persona-panel (current: 1.2.1 → 1.2.2)
  File                                              Current
  ────────────────────────────────────────────────  ───────
  plugins/persona-panel/.claude-plugin/plugin.json   1.2.1
  .claude-plugin/marketplace.json (persona-panel)    1.2.1

md-html-docs (current: 2.4.0 → 2.4.1)
  File                                              Current
  ────────────────────────────────────────────────  ───────
  .claude-plugin/marketplace.json (md-html-docs)     2.4.0
  plugins/md-html-docs/skills/md-html-docs/SKILL.md  2.4.0
  plugins/md-html-docs/convert.py (PLUGIN_VERSION)   2.4.0
```

Also show that the top-level marketplace version will be bumped.

Ask the user to confirm before proceeding. If versions differ across files within the same plugin, flag the mismatch and ask whether to align them first.

## Step 5: Bump All Versions

For each changed plugin, update every detected version file using the Edit tool:

- **JSON files** (`plugin.json`, `marketplace.json`): Update the `"version"` value
- **YAML frontmatter** (`SKILL.md`): Update the `version:` field
- **Python constants**: Update `PLUGIN_VERSION = 'x.y.z'`
- **JS constants**: Update version string assignments

Also bump the **top-level marketplace version** in `.claude-plugin/marketplace.json` → `metadata.version`. Use patch bump for this.

## Step 6: Commit and Push

1. Run `git diff --stat` to review all changes
2. Stage only the version-bumped files by name (never `git add -A`)
3. Commit with message: `Publish: bump <plugin1> to vX.Y.Z, <plugin2> to vX.Y.Z`
   - If only one plugin changed: `Publish: bump <plugin> to vX.Y.Z`
4. Push to the current branch

## Step 7: Create PR and Merge (if not on main)

If on a feature branch:
1. Create PR with `gh pr create`:
   - Title: `Publish marketplace vX.Y.Z`
   - Body: list all bumped plugins with old → new versions
2. Merge with `gh pr merge --merge --admin`
   - If `--admin` fails, try without it
   - If merge is blocked, provide the PR URL
3. After merge: `git checkout main && git pull`

If already on main, just push directly.

## Step 8: Install Locally

After the push/merge is complete, update the local plugin installation:

```bash
# Update the marketplace cache
claude plugins marketplace update moonsite-claude-extensions

# Reinstall each changed plugin to get the new version
claude plugins install <plugin-name>@moonsite-claude-extensions
```

Run this for each changed plugin.

If the `claude` CLI is not available in the current shell, inform the user and provide the commands they should run manually.

## Step 9: Verify

After installation, show a final summary:

```
Published:
  persona-panel    1.2.1 → 1.2.2
  md-html-docs     2.4.0 → 2.4.1
  marketplace      1.3.1 → 1.3.2

Installed locally. Run `claude plugins list` to verify.
```

## Notes

- Never modify lock files or generated HTML files
- Only bump plugins that have actual code/content changes (not just version bumps)
- If a plugin has no version files at all, skip it with a warning
- The top-level marketplace version always gets a patch bump regardless of the plugin bump type
- Skip `node_modules/`, `dist/`, `__pycache__/`, `.git/` when scanning for version files
