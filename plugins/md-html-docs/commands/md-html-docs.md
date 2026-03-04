---
name: md-html-docs
description: Enable, disable, or check status of automatic markdown-to-HTML generation
arguments:
  - name: action
    description: "enable, disable, status, or convert"
    required: true
---

Manage the md-html-docs auto-generation for this project.

Based on the `$ARGUMENTS` action:

**If "enable":**
1. Write `{"enabled": true}` to `.claude/md-html-docs.json`
2. Confirm: "md-html-docs enabled. HTML will be auto-generated whenever you create or edit `.md` files."

**If "disable":**
1. Write `{"enabled": false}` to `.claude/md-html-docs.json`
2. Confirm: "md-html-docs disabled. To re-enable, run `/md-html-docs enable`."

**If "status":**
1. Read `.claude/md-html-docs.json` and report current state.

**If "convert" (with additional arguments):**
Delegate to `/md-html-docs-convert` with the remaining arguments.

**Anything else:**
Show usage: `/md-html-docs enable`, `/md-html-docs disable`, `/md-html-docs status`, `/md-html-docs-convert <path>`
