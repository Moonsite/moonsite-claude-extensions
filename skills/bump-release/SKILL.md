---
name: bump-release
description: "Bump version across all project files, commit, push, and create PR. Use when the user says 'bump version', 'release', 'bump-release', 'cut a release', 'version bump', or similar."
version: 1.0.0
---

# Bump Release

Detect all version files in the project, bump them to a new version, commit, push, and optionally create a PR.

## Workflow

### Step 1: Detect Version Files

Scan the project root (and immediate subdirectories) for files containing version strings. Check for:

- `package.json` — `"version": "x.y.z"`
- `*.csproj` / `Directory.Build.props` — `<Version>x.y.z</Version>`
- `pyproject.toml` — `version = "x.y.z"`
- `setup.py` / `setup.cfg` — `version=` or `version =`
- `Cargo.toml` — `version = "x.y.z"`
- `build.gradle` / `build.gradle.kts` — `version =` or `version=`
- `*.podspec` — `.version =`
- `marketplace.json` / `plugin.json` — `"version": "x.y.z"`
- `SKILL.md` frontmatter — `version: x.y.z`
- Any other file matching `"version": "x.y.z"` or `version = "x.y.z"` patterns

Use Glob and Grep to find these files. Collect each file path and its current version string.

**Important:** Only include files that are tracked by git or are in the project's source directories. Skip `node_modules/`, `dist/`, `build/`, `.git/`, vendor directories, and lock files (`package-lock.json`, `yarn.lock`, `Cargo.lock`, etc.).

### Step 2: Determine Bump Type

If the user specified a bump type (patch, minor, major), use it. Otherwise, ask using AskUserQuestion:

- **patch** (default) — bug fixes, small changes (1.2.3 -> 1.2.4)
- **minor** — new features, backwards compatible (1.2.3 -> 1.3.0)
- **major** — breaking changes (1.2.3 -> 2.0.0)

### Step 3: Show Current Versions

Display a table of all detected version files and their current versions. Example:

```
File                                  Current Version
────────────────────────────────────  ───────────────
.claude-plugin/marketplace.json       1.0.0
plugins/foo/.claude-plugin/plugin.json 4.0.0
skills/bar/SKILL.md                   1.0.0
```

Ask the user to confirm before proceeding. If versions differ across files, ask whether to:
- Bump each file independently from its current version
- Align all files to a single new version

### Step 4: Bump Versions

Update each detected file with the new version using the Edit tool. Handle each file format correctly:

- **JSON files** (`package.json`, `marketplace.json`, `plugin.json`): Update the `"version"` value
- **YAML frontmatter** (`SKILL.md`): Update the `version:` field
- **TOML files** (`pyproject.toml`, `Cargo.toml`): Update `version = "..."` in the appropriate section
- **XML files** (`.csproj`, `Directory.Build.props`): Update `<Version>...</Version>`
- **Gradle files**: Update `version = "..."` or `version '...'`
- **Python setup files**: Update `version=` argument

### Step 5: Commit and Push

1. Run `git status` and `git diff` to review changes
2. Stage only the version-bumped files (by name, not `git add -A`)
3. Commit with message: `Bump version to X.Y.Z`
4. Push to the current remote branch

### Step 6: Create PR (if applicable)

Check the current branch. If it's NOT the main/default branch:
1. Use `gh pr create` to create a pull request
2. Title: `Release vX.Y.Z`
3. Body: List all bumped files and old -> new versions
4. Return the PR URL to the user

If already on main/master, skip PR creation and inform the user that the version bump has been pushed directly.

## Notes

- Never modify lock files — only source version files
- If a file has multiple `"version"` fields (e.g., nested dependencies), only bump the top-level project version
- Respect `.gitignore` — don't scan ignored directories
- If no version files are found, inform the user and exit gracefully
