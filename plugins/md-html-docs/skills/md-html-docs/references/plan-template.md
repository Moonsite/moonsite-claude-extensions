# Plan / Decision Doc Template

Use this template when creating a new file in `docs/plans/`. No HTML conversion needed — these are plain markdown.

## File naming

`YYYY-MM-DD-short-description.md` (e.g., `2026-02-20-auth-migration.md`).

## Template

```markdown
# Title of Plan or Decision

**Date**: YYYY-MM-DD
**Status**: Draft | Approved | Implemented | Superseded
**Author**: Name

---

## Context

What is the situation that prompted this decision? What problem are we solving?

---

## Decision

What did we decide to do? State it clearly and directly.

---

## Options Considered

### Option A: Name

Description.

**Pros**: ...
**Cons**: ...

### Option B: Name

Description.

**Pros**: ...
**Cons**: ...

### Option C (chosen): Name

Description.

**Pros**: ...
**Cons**: ...

---

## Implementation Plan

Step-by-step breakdown of what needs to happen.

1. Step one
2. Step two
3. Step three

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Risk description | High/Med/Low | High/Med/Low | Mitigation action |

---

## References

- Link to related ticket
- Link to related spec
```

## Notes

- Plans do **not** get converted to HTML — commit only the `.md` file
- No index update needed
- No images folder required (though you can add one if needed)
- These are internal decision records, not user-facing documentation
