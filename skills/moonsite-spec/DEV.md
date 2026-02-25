# Moonsite Spec Skill - Development Guide

## Directory Structure

```
moonsite-spec/
├── SKILL.md                      # Skill instructions (loaded by Claude)
├── DEV.md                        # This file - development guide
├── scripts/
│   └── spec_to_docx.py          # Convert markdown to DOCX with template
├── references/
│   └── template.md              # Spec document structure template
├── assets/
│   └── moonsite-template.docx   # Word styling template
└── outputs/
    └── *.md, *.docx             # Generated specs
```

## Workflow

### 1. Development Location
- **Develop here**: `~/Source/moonsite-skills/moonsite-spec/`
- **Installed to**: `~/.claude/skills/moonsite-spec/`

### 2. Making Changes

Edit files in `~/Source/moonsite-skills/moonsite-spec/`:
- `SKILL.md` - Update workflow instructions
- `references/template.md` - Modify spec structure
- `assets/moonsite-template.docx` - Update Word styles
- `scripts/spec_to_docx.py` - Enhance conversion logic

### 3. Sync to Claude

After changes, sync to Claude's skills directory:

```bash
cp -r ~/Source/moonsite-skills/moonsite-spec/* ~/.claude/skills/moonsite-spec/
```

### 4. Testing

Test the skill by asking Claude to create a spec:
```
"Create a spec for the homepage"
"Write an איפיון for the search page"
```

## Updating the Word Template

To update the styling template:

1. Open `assets/moonsite-template.docx` in Word
2. Modify styles (Heading 1, Heading 2, Normal, Table styles, etc.)
3. **Important**: Keep the document structure minimal - only styles matter
4. Save and sync to Claude skills folder

The template provides:
- Font families and sizes
- Colors (text, backgrounds, borders)
- Table formatting
- Spacing and indentation
- RTL text direction

## Scripts

### spec_to_docx.py

Converts markdown specs to DOCX using pandoc with:
- RTL support for Hebrew
- Moonsite template styling
- Preserves tables and formatting

**Usage:**
```bash
python3 scripts/spec_to_docx.py input.md output.docx
```

**Requirements:**
- pandoc: `brew install pandoc`

## Common Tasks

### Add a new section template

Edit `references/template.md` and add the section structure.

### Change output directory

Default: `outputs/` (relative to skill directory)

Modify in workflow or use absolute paths.

### Support additional formats

Add new scripts to `scripts/` for other conversions:
- `spec_to_pdf.py` - Direct markdown to PDF
- `spec_to_html.py` - Web-ready HTML output

## Packaging for Distribution

When the skill is ready to share:

```bash
~/.claude/skills/skill-creator/scripts/package_skill.py \
  ~/Source/moonsite-skills/moonsite-spec
```

This creates a `.skill` file that can be distributed to others.
