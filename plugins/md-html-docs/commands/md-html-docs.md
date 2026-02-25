---
name: md-html-docs
description: Enable or disable automatic HTML generation from markdown files in docs/
arguments:
  - name: action
    description: "enable or disable"
    required: true
---

Manage the md-html-docs auto-generation for this project.

Based on the `$ARGUMENTS` action:

**If "enable":**
1. Write `{"enabled": true}` to `.claude/md-html-docs.json`
2. Confirm: "md-html-docs enabled. HTML will be auto-generated whenever you create or edit `.md` files in `docs/`."

**If "disable":**
1. Write `{"enabled": false}` to `.claude/md-html-docs.json`
2. Confirm: "md-html-docs disabled. To re-enable, run `/md-html-docs enable`."

**If "status":**
1. Read `.claude/md-html-docs.json` and report current state.

**Anything else:**
Show usage: `/md-html-docs enable`, `/md-html-docs disable`, `/md-html-docs status`
