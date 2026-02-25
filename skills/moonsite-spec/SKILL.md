---
name: moonsite-spec
description: "Generate a Word document (.docx) technical specification in Moonsite style. Use ONLY when the user explicitly asks to generate a Word/DOCX spec in Moonsite format — e.g. 'create a Moonsite spec', 'generate a Word spec', 'make a DOCX איפיון in Moonsite style'. Do NOT use for general documentation, markdown specs, or HTML docs."
---

# Moonsite Spec Generator

Generate well-formatted technical specification documents following Moonsite's standard format.

## Workflow

### Step 1: Gather Inputs

Collect from user:
1. **Requirements** - Business requirements, user stories, or feature descriptions
2. **Source code** (optional) - Existing code to document or extend
3. **Figma designs** (optional) - UI designs to specify

### Step 2: Analyze & Structure

1. Read all provided inputs
2. If Figma URL provided, use Figma MCP to get design context
3. Identify components, screens, processes, and APIs
4. Create outline following the template structure

### Step 3: Generate Spec

Follow the detailed guides:
- **What to include:** [references/DOCUMENT_STRUCTURE_V2.md](references/DOCUMENT_STRUCTURE_V2.md)
- **How to write:** [references/SPEC_WRITING_GUIDELINES_V2.md](references/SPEC_WRITING_GUIDELINES_V2.md)

Generate the spec with these sections:

#### Required Sections
1. **מנהלה (Administration)** - Title, author, date, change tracking, symbols legend
2. **תוכן עניינים (TOC)** - Auto-generated
3. **כללי (General)** - Scope, related specs
4. **איפיון ממשק למשתמש (UI Spec)** - Components with standard fields

#### Optional Sections (as needed)
5. **תהליכים (Processes)** - Step-by-step with IF/THEN logic
6. **ממשקים (Interfaces)** - API Request/Response definitions
7. **נספחים (Appendices)** - Error codes, status mappings

### Step 4: Output - Use Office-Skills OOXML Workflow

**Create Word document using office-skills OOXML editing:**

1. **Read office-skills ooxml.md:**
   ```
   Read ~/.claude/skills/office-skills/public/docx/ooxml.md completely
   ```

2. **Workflow:**
   ```bash
   # Copy template as starting point
   cp assets/moonsite-template.docx outputs/[spec-name]/spec.docx

   # Unpack to XML
   ~/.claude/skills/office-skills/venv/bin/python \
     ~/.claude/skills/office-skills/public/docx/ooxml/scripts/unpack.py \
     outputs/[spec-name]/spec.docx \
     outputs/[spec-name]/unpacked/

   # Edit XML using Document library (Python)
   # - Add content while preserving template structure
   # - RTL paragraphs, LTR code blocks
   # - Tables inherit template formatting

   # Pack back to DOCX
   ~/.claude/skills/office-skills/venv/bin/python \
     ~/.claude/skills/office-skills/public/docx/ooxml/scripts/pack.py \
     outputs/[spec-name]/unpacked/ \
     outputs/[spec-name]/spec.docx
   ```

**Why OOXML editing:**
- ✅ Starts from template (all formatting preserved)
- ✅ Full control over RTL/LTR per paragraph
- ✅ Tables keep borders, spacing, styles
- ✅ Can mix Hebrew (RTL) and code blocks (LTR) properly
- ✅ PropertyAlias, LogicCondition styles from template

**Also create Markdown:**
- Write .md as reference
- Use for version control

## Component Specification Format

For each UI component, document:

| Field | Hebrew | Description |
|-------|--------|-------------|
| Purpose | מטרת האלמנט | What the component does |
| Type | סוג תצוגה | screen/component/popup |
| Location | איפה מוצג | Where it appears |
| Description | תיאור | How it works |
| Display States | מצבי תצוגה | Table of states with fields |
| Notes | הערות | Additional info |
| Errors | הודעות שגיאה | Error messages |
| APIs | ממשקי API | Related endpoints |

## Formatting Conventions

### Text Styling
- **Yellow background** - Examples from other projects (for reference only)
- **Turquoise background** - Items requiring review/completion
- **Red bold underlined** - Logical conditions (IF/THEN)
- **Blue bold** - Variable names (camelCase)
- **Red bold** - Routes/navigation paths

### Logic Format
```
אם {condition}
אז {action}
אחרת {alternative}
```

### Variable References
Format: `object.field.subfield` (e.g., `state.line.markets[0].price`)

## Example Component Spec

```markdown
### רכיב LoginButton

| נושא | תיאור |
|------|-------|
| מטרת האלמנט | כפתור להתחברות למערכת |
| סוג תצוגה | רכיב (component) |
| איפה מוצג | Header של כל עמוד |
| תיאור | כפתור שמציג "התחבר" למשתמש לא מחובר ושם המשתמש למשתמש מחובר |

#### מצבי תצוגה

| # | אלמנט | תיאור | הערות |
|---|-------|-------|-------|
| 1 | טקסט כפתור | אם **isLoggedIn**==false אז "התחבר" אחרת **user.displayName** | |
| 2 | אייקון | אייקון משתמש מתוך assets/icons/user.svg | |

#### הערות
לחיצה על כפתור במצב לא מחובר פותחת פופאפ התחברות

#### ממשקי API
- GET /api/user/current
```
