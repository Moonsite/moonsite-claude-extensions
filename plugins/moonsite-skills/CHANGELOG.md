# Changelog — moonsite-skills

All notable changes to **moonsite-skills** are documented here.

---

## [1.0.4] — 2026-03-14

- Add per-plugin CHANGELOG.md generation to `/publish` skill (Step 5.5)
- Update `/bump-release` skill to maintain per-plugin changelogs when they exist

## [1.0.3] — 2026-03-13

- Add `/publish` skill for marketplace-wide releases
- Sync plugin.json version field

## [1.0.2] — 2026-03-11

- Add CHANGELOG.md auto-update step to bump-release skill
- Backfill full CHANGELOG.md from project history

## [1.0.1] — 2026-03-05

- Add merge step to bump-release skill

## [1.0.0] — 2026-03-04

- Initial release: `/bump-release` and `/moonsite-spec` skills
- `/bump-release`: detect version files, bump, commit, push, and create PR
- `/moonsite-spec`: generate technical specs in Moonsite corporate style
