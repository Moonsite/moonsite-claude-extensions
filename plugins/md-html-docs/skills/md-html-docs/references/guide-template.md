# Guide Markdown Template (Hebrew RTL)

Use this template when creating a new file in `docs/guides/`. All content must be in Hebrew.

## File naming

`NN-role-name.md` where NN is the next available two-digit number.

## Template

```markdown
# שם המדריך

## תפקיד המשתמש — מערכת תעמ"ת

---

## תוכן עניינים

1. [כניסה למערכת](#כניסה-למערכת)
2. [סעיף שני](#סעיף-שני)
3. [סעיף שלישי](#סעיף-שלישי)

---

## כניסה למערכת

תיאור השלבים לכניסה למערכת.

[SCREENSHOT: sign-in-page]

---

## סעיף שני

תוכן הסעיף.

> **שים לב:** הערות חשובות מוצגות כקופסת אזהרה.

---

## סעיף שלישי

[SCREENSHOT: feature-screen]

תיאור הפעולה.

### פעולות אפשריות

| פעולה | תיאור |
|---|---|
| הוספה | לחץ על כפתור + |
| עריכה | לחץ על שורה |
| מחיקה | לחץ על סמל האשפה |
```

## Important conventions

- **All headings in Hebrew** — including TOC anchors
- **`[SCREENSHOT: name]`** — placeholder for screenshots; the converter replaces these with styled `<div class="screenshot-placeholder">` elements
- **`> **text**`** — blockquote starting with bold text becomes a yellow warning box in HTML
- **Tables** — use standard pipe syntax; converter adds `field-table` CSS class automatically
- **TOC anchors** — Hebrew heading text becomes anchor IDs; the converter handles Hebrew character support

## Registering in `_convert.py`

After creating the `.md` file, add an entry to the `GUIDES` list in `docs/guides/_convert.py`:

```python
GuideDoc(
    md="NN-role-name.md",
    number="NN",
    title="שם המדריך",          # Hebrew title shown in header
    role="שם התפקיד",           # Hebrew role name shown under title
),
```

Add it in the correct numbered position. The converter automatically links prev/next navigation between guides based on list order.
