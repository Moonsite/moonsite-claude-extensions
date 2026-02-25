# Report Markdown Template

Use this template when creating a new file in `docs/code-review/`.

## File naming

`DESCRIPTIVE_NAME_IN_CAPS.md` (e.g., `FEATURE_ANALYSIS.md`, `SECURITY_REVIEW.md`).

## Template

```markdown
# Report Title

> Brief context or scope of this report.

---

## Summary

High-level summary of findings and recommendations.

---

## Findings

### Finding 1: Title

**Severity**: High / Medium / Low
**Area**: Frontend / Backend / Infrastructure

Description of the finding.

**Recommendation**: What to do about it.

---

### Finding 2: Title

**Severity**: Medium
**Area**: Backend

Description.

**Recommendation**: Action.

---

## Action Items

- [ ] Item 1 — owner
- [ ] Item 2 — owner
- [x] Completed item — owner

---

## Appendix

Supporting details, code snippets, references.
```

## Checkbox rendering

The report converter (`_convert_report.py`) transforms checkboxes:
- `[ ]` → unchecked HTML checkbox (disabled)
- `[x]` → checked HTML checkbox (disabled)

These render as interactive-looking (but read-only) checkboxes in the HTML output.

## Registering in `_convert_report.py`

After creating the `.md` file, add an entry to the `REPORTS` list in `docs/code-review/_convert_report.py`:

```python
ReportDoc(
    md="DESCRIPTIVE_NAME.md",
    title="Report Title",
    subtitle="Brief subtitle",
),
```
