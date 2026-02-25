# Moonsite Spec Document Template

Use this template structure when generating specification documents.

## Document Structure

```markdown
# איפיון טכני
# {Project Name}
# {Feature Name}

| שדה | ערך |
|-----|-----|
| כותב המסמך | {Author Name} |
| תאריך | {DD/MM/YYYY} |
| גורמים מאשרים | {Approvers} |
| גורמים לידיעה | {FYI Recipients} |

---

## 1. מנהלה

### 1.1. מעקב שינויים

| מספר שינוי | צבע | תאריך | מחבר | תיאור |
|------------|-----|-------|------|-------|
| 1.0 | | {date} | {author} | גרסה ראשונית |

### 1.2. מקרא סימונים

| סימון | משמעות | דוגמא |
|-------|---------|-------|
| רקע צהוב | דוגמאות מפרוייקטים אחרים להדגמה בלבד | טקסט לדוגמא |
| רקע טורקיז | נקודות הדורשות בדיקה/התייחסות והשלמה | טקסט לדוגמא |
| כתב אדום מודגש עם קו תחתון | תנאי לוגי | **טקסט לדוגמא** |
| כתב כחול מודגש | משתנה | `variableName` |
| כתב אדום מודגש | נתיב – Route | **/Routes/Path/{id}** |

---

## 2. תוכן עניינים

[Auto-generated based on sections]

---

## 3. כללי

מסמך איפיון זה מכסה את היכולות הבאות:
1. {Capability 1}
2. {Capability 2}
3. {Capability 3}

### אפיונים נוספים קשורים לנושא:

| מספר איפיון | קישור |
|-------------|-------|
| {Number} | {Link to related spec} |

---

## 4. איפיון ממשק למשתמש

### 4.1. רכיבים

#### 4.1.1. רכיב {ComponentName}

| נושא | תיאור |
|------|-------|
| מטרת האלמנט | {Purpose of the element} |
| סוג תצוגה | {screen / רכיב (component) / פופאפ} |
| איפה מוצג | {Where it appears - pages, contexts} |
| תיאור | {How the component works, parameters it accepts} |

##### מצבי תצוגה

| # | אלמנט | תיאור | הערות |
|---|-------|-------|-------|
| 1 | {Element name} | {Description with conditions} | {Notes} |
| 2 | {Element name} | {Description} | |

##### הערות
{Additional notes about behavior, edge cases}

##### הודעות שגיאה
| קוד | הודעה | תנאי |
|-----|-------|------|
| {code} | {message} | {when shown} |

##### ממשקי API
- {HTTP Method} {endpoint}

---

## 5. תהליכים

### 5.1. {Process Name}

| # | מקרה | תיאור |
|---|------|-------|
| 1 | {Step name} | אם {condition} אז {action} אחרת {alternative} |
| 2 | {Step name} | {Description} |

---

## 6. ממשקים

### 6.1. {API Endpoint Name}

#### Request

| שדה | סוג | חובה | תיאור |
|-----|-----|------|-------|
| {fieldName} | {string/number/boolean/array/object} | {כן/לא} | {Description} |

#### Response

| שדה | סוג | תיאור |
|-----|-----|-------|
| {fieldName} | {type} | {Description} |

#### חוקים עסקיים
1. {Business rule 1}
2. {Business rule 2}

---

## 7. נספחים

### נספח א' - {Appendix Title}

{Content - error codes, status mappings, screenshots, etc.}

### נספח ב' - מיפוי שגיאות

| קוד שגיאה | הודעה | טיפול |
|-----------|-------|-------|
| {code} | {message} | {handling} |
```

## Section Guidelines

### UI Components (איפיון ממשק למשתמש)
- Document each component/screen separately
- Include all display states in a table
- Reference variables using `object.field` notation
- Include screenshots/mockups where available

### Processes (תהליכים)
- Use numbered steps
- Format conditions as: אם X אז Y אחרת Z
- Reference API calls where applicable
- Include error handling steps

### APIs (ממשקים)
- Document Request and Response separately
- Include all fields with types and required status
- Add business rules section for validation logic
- Use camelCase for field names

### Appendices (נספחים)
- Error code mappings
- Status code definitions
- Screenshots with numbered annotations
- Related documentation links
