# Index Update Guide

After creating a new doc and generating its HTML, update the relevant index files.

---

## Spec: `docs/spec/index.html`

Find the appropriate section (Current System, Platform Evolution, or Feature Specs) and add a card. Pattern to match:

```html
<div class="spec-card" onclick="window.location='NN-PREV-FILE.html'">
```

Add after it:

```html
<div class="spec-card" onclick="window.location='NN-YOUR-FILE.html'">
    <div class="spec-number">NN</div>
    <div class="spec-content">
        <div class="spec-title">Your Spec Title</div>
        <div class="spec-desc">Brief one-line description of what this spec covers.</div>
        <span class="priority-badge priority-p1">P1</span>
    </div>
</div>
```

Priority badge classes: `priority-p0` (red), `priority-p1` (orange), `priority-p2` (blue)

---

## Guide: `docs/guides/index.html`

Find the guide cards list and add:

```html
<div class="guide-card" onclick="window.location='NN-role-name.html'">
    <div class="guide-number">NN</div>
    <div class="guide-content">
        <div class="guide-title">שם המדריך</div>
        <div class="guide-role">שם התפקיד</div>
    </div>
</div>
```

Also update the prev/next navigation in adjacent guide HTML files. In the **previous** guide's HTML, find:

```html
<a href="#" class="nav-btn next-btn">
```

And update the `href` to point to your new guide. In your **new** guide's HTML (after running converter), verify the prev link points to the previous guide.

---

## Report: `docs/code-review/index.html`

Add a card:

```html
<div class="report-card" onclick="window.location='REPORT_NAME.html'">
    <div class="report-content">
        <div class="report-title">Report Title</div>
        <div class="report-desc">Brief description.</div>
    </div>
</div>
```

---

## Main landing: `docs/index.html`

Update the document count shown on each section card. Find the count text (e.g., `"13 מסמכים"`) and increment it.

For specs:
```html
<!-- Find something like: -->
<span class="doc-count">13 spec docs</span>
<!-- Change to: -->
<span class="doc-count">14 spec docs</span>
```

For guides:
```html
<!-- Find: -->
<span class="doc-count">7 guides</span>
<!-- Change to: -->
<span class="doc-count">8 guides</span>
```

---

## Tip: Check actual HTML before editing

Always read the current `index.html` before making changes — the exact class names and structure may vary. Use these snippets as patterns, not exact copy-paste.
