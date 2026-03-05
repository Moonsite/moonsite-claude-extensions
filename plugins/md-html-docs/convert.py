#!/usr/bin/env python3
"""
md-html-docs converter — self-contained markdown-to-HTML with zero pip dependencies.

Usage:
    python3 convert.py <file.md>              # single file
    python3 convert.py <folder/>              # all .md in folder (non-recursive)
    python3 convert.py '<glob>'               # e.g. 'docs/**/*.md'
    python3 convert.py --index <folder/>      # regenerate index.html only
    python3 convert.py --all <root/>          # recursive convert + all indexes
"""
import glob as globmod
import html
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# ─── Diagram support ─────────────────────────────────────────────────────────

DIAGRAM_LANGUAGES = {
    'mermaid': ['pintora'],
    'pintora': ['pintora'],
    'dot': ['vizjs'],
    'graphviz': ['vizjs'],
    'nomnoml': ['nomnoml'],
}

DIAGRAM_CSS = """\
.diagram-block{margin:1rem 0}
.diagram-toolbar{margin-bottom:.5rem}
.diagram-toolbar select{font-family:inherit;font-size:.8rem;padding:.25rem .5rem;border:1px solid var(--border);border-radius:4px;background:var(--surface);color:var(--text);cursor:pointer}
.diagram-render{min-height:40px;display:flex;justify-content:center;overflow-x:auto}
.diagram-render svg{max-width:100%}
.diagram-error{color:#dc2626;font-size:.875rem;padding:.5rem;background:#fef2f2;border-radius:4px}
"""

DIAGRAM_SCRIPTS = """\
<script src="https://cdn.jsdelivr.net/npm/@pintora/standalone/lib/pintora-standalone.umd.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@viz-js/viz/lib/viz-standalone.js"></script>
<script src="https://unpkg.com/graphre/dist/graphre.js"></script>
<script src="https://unpkg.com/nomnoml/dist/nomnoml.js"></script>
<script>
(function(){
  var renderers={
    pintora:function(src,el){
      pintora.default.renderTo(src,{container:el,renderer:'svg'});
    },
    vizjs:function(src,el){
      Viz.instance().then(function(viz){
        var svg=viz.renderSVGElement(src);
        el.appendChild(svg);
      });
    },
    nomnoml:function(src,el){
      el.textContent='';
      var svgStr=nomnoml.renderSvg(src);
      var parser=new DOMParser();
      var doc=parser.parseFromString(svgStr,'image/svg+xml');
      el.appendChild(doc.documentElement);
    }
  };
  function render(block){
    var sel=block.querySelector('select');
    var target=block.querySelector('.diagram-render');
    var src=block.querySelector('script[type="text/diagram"]').textContent;
    var renderer=sel?sel.value:block.dataset.renderers;
    target.textContent='';
    try{
      renderers[renderer](src,target);
    }catch(e){
      var errDiv=document.createElement('div');
      errDiv.className='diagram-error';
      errDiv.textContent='Render error: '+e.message;
      target.appendChild(errDiv);
    }
  }
  document.querySelectorAll('.diagram-block').forEach(function(block){
    var sel=block.querySelector('select');
    if(sel) sel.addEventListener('change',function(){render(block);});
    render(block);
  });
})();
</script>
"""

# ─── Config loading ──────────────────────────────────────────────────────────

def load_config(start_dir):
    """Search up from start_dir for .claude/md-html-docs.json and return config dict."""
    defaults = {
        'projectName': 'Documentation',
        'orgName': '',
        'logoText': 'Docs',
        'footerText': '',
    }
    d = Path(start_dir).resolve()
    while True:
        config_path = d / '.claude' / 'md-html-docs.json'
        if config_path.is_file():
            try:
                with open(config_path, encoding='utf-8') as f:
                    cfg = json.load(f)
                result = {**defaults, **cfg}
                # Auto-derive logoText from projectName if not explicitly set
                if 'logoText' not in cfg and 'projectName' in cfg:
                    result['logoText'] = cfg['projectName'][:2]
                return result
            except (json.JSONDecodeError, OSError):
                return defaults
        parent = d.parent
        if parent == d:
            break
        d = parent
    return defaults


# ─── Templates ────────────────────────────────────────────────────────────────

LTR_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{TITLE}}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/vs2015.min.css">
<style>
:root{--bg:#f8f9fa;--surface:#fff;--text:#1a1a2e;--muted:#6b7280;--accent:#2563eb;--accent-light:#dbeafe;--border:#e5e7eb;--code-bg:#1E1E1E;--code-text:#d4d4d4;--radius:8px;--header-from:#1e3a5f;--header-to:#2563eb}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',system-ui,sans-serif;background:var(--bg);color:var(--text);line-height:1.7}

/* ── Header ── */
.site-header{background:linear-gradient(135deg,var(--header-from),var(--header-to));color:#fff;padding:1.25rem 2rem;display:flex;align-items:center;gap:1rem;box-shadow:0 2px 8px rgba(0,0,0,.15)}
.logo-circle{width:44px;height:44px;border-radius:50%;background:rgba(255,255,255,.2);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:1rem;letter-spacing:.5px;flex-shrink:0}
.site-header .header-text h1{font-size:1.1rem;font-weight:600;margin:0;line-height:1.3}
.site-header .header-text .org{font-size:.8rem;opacity:.8;margin:0}
.header-badge{margin-left:auto;background:rgba(255,255,255,.18);padding:.3rem .75rem;border-radius:20px;font-size:.75rem;font-weight:500;letter-spacing:.3px}

/* ── Layout ── */
.page{display:grid;grid-template-columns:280px 1fr;max-width:1300px;margin:0 auto;min-height:calc(100vh - 70px)}

/* ── Sidebar ── */
.sidebar{position:sticky;top:0;height:calc(100vh - 70px);overflow-y:auto;padding:1.5rem;background:var(--surface);border-right:1px solid var(--border)}
.sidebar-card{background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);padding:1rem;margin-bottom:1rem}
.sidebar-card h3{font-size:.7rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin-bottom:.75rem;font-weight:600}
.sidebar a{display:block;padding:.3rem .5rem;color:var(--text);text-decoration:none;font-size:.85rem;border-left:2px solid transparent;margin-bottom:.15rem;border-radius:0 4px 4px 0;transition:all .15s}
.sidebar a:hover{color:var(--accent);border-left-color:var(--accent);background:var(--accent-light)}
.sidebar a.h3-link{padding-left:1.25rem;font-size:.8rem;color:var(--muted)}

/* ── Mobile TOC toggle ── */
.toc-toggle{display:none;position:fixed;bottom:1.5rem;right:1.5rem;z-index:100;background:var(--accent);color:#fff;border:none;border-radius:50%;width:48px;height:48px;font-size:1.3rem;cursor:pointer;box-shadow:0 3px 12px rgba(37,99,235,.4);transition:transform .2s}
.toc-toggle:hover{transform:scale(1.1)}

/* ── Content ── */
.content{padding:2.5rem 3.5rem;max-width:860px}
.doc-header{margin-bottom:2rem;padding-bottom:1.5rem;border-bottom:2px solid var(--border)}
.doc-header h1{font-size:2rem;font-weight:700;margin-bottom:.4rem;color:var(--text)}
.subtitle{color:var(--muted);font-size:1.05rem}
.date{color:var(--muted);font-size:.8rem;margin-top:.4rem}

/* ── Typography ── */
h2{font-size:1.4rem;font-weight:600;margin:2.5rem 0 1rem;padding-bottom:.4rem;border-bottom:2px solid var(--accent-light)}
h3{font-size:1.15rem;font-weight:600;margin:1.75rem 0 .75rem}
h4{font-size:1rem;font-weight:600;margin:1.25rem 0 .5rem}
p{margin-bottom:1rem}
a{color:var(--accent)}
ul,ol{margin:0 0 1rem 1.5rem}
li{margin-bottom:.35rem}
li input[type="checkbox"]{margin-right:.4rem}
blockquote{border-left:3px solid var(--accent);padding:.75rem 1rem;margin:1rem 0;background:var(--accent-light);border-radius:0 var(--radius) var(--radius) 0}

/* ── Code ── */
pre{background:var(--code-bg);color:var(--code-text);padding:1.15rem 1.25rem;border-radius:var(--radius);overflow-x:auto;margin:1rem 0;font-size:.85rem;box-shadow:inset 0 1px 3px rgba(0,0,0,.2)}
code{font-family:'JetBrains Mono',monospace;font-size:.85em}
p code,li code{background:#e8eaed;color:#c7254e;padding:.15rem .4rem;border-radius:4px}
pre code{background:transparent;color:inherit;padding:0}

/* ── Tables ── */
table{width:100%;border-collapse:collapse;margin:1rem 0;font-size:.9rem}
th,td{border:1px solid var(--border);padding:.6rem .8rem;text-align:left}
th{background:var(--accent);color:#fff;font-weight:600}
tr:nth-child(even){background:#f5f6f8}

/* ── Misc ── */
hr{border:none;border-top:1px solid var(--border);margin:2rem 0}
img{max-width:100%;border-radius:var(--radius);margin:1rem 0}
.footer{margin-top:3rem;padding:1.5rem 0;border-top:1px solid var(--border);color:var(--muted);font-size:.8rem;display:flex;justify-content:space-between;align-items:center}

/* ── Print ── */
@media print{
  .site-header{background:var(--accent)!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .sidebar,.toc-toggle{display:none!important}
  .page{grid-template-columns:1fr}
  .content{padding:1rem;max-width:100%}
  pre{white-space:pre-wrap;word-break:break-all}
}

/* ── Mobile ── */
@media(max-width:768px){
  .page{grid-template-columns:1fr}
  .sidebar{display:none;position:fixed;top:0;left:0;right:0;bottom:0;z-index:99;height:100vh;border:none;box-shadow:0 0 30px rgba(0,0,0,.3)}
  .sidebar.open{display:block}
  .toc-toggle{display:flex;align-items:center;justify-content:center}
  .content{padding:1.5rem}
}
{{DIAGRAM_CSS}}
</style>
</head>
<body>
<header class="site-header">
  <div class="logo-circle">{{LOGO_TEXT}}</div>
  <div class="header-text">
    <h1>{{PROJECT_NAME}}</h1>
    <div class="org">{{ORG_NAME}}</div>
  </div>
  <div class="header-badge">{{BADGE_TEXT}}</div>
</header>
<div class="page">
<nav class="sidebar" id="sidebar">
  <div class="sidebar-card">
    <h3>Contents</h3>
    {{TOC}}
  </div>
</nav>
<main class="content">
<div class="doc-header">
<h1>{{TITLE}}</h1>
<div class="subtitle">{{SUBTITLE}}</div>
<div class="date">{{GENERATION_DATE}}</div>
</div>
{{CONTENT}}
<div class="footer">
  <span>{{FOOTER_TEXT}}</span>
  <span>Generated: {{GENERATION_DATE}}</span>
</div>
</main>
</div>
<button class="toc-toggle" onclick="document.getElementById('sidebar').classList.toggle('open')" aria-label="Toggle table of contents">&#128209;</button>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script>hljs.highlightAll();</script>
<script type="module">
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
mermaid.initialize({startOnLoad:true,theme:'dark'});
</script>
{{DIAGRAM_SCRIPTS}}
</body>
</html>
"""

RTL_TEMPLATE = """\
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{TITLE}}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;500;600;700&family=Rubik:wght@400;500;600;700&family=Assistant:wght@400;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/vs.min.css">
<style>
:root{--bg:#f8f9fa;--surface:#fff;--text:#1a1a2e;--muted:#6b7280;--accent:#2563eb;--accent-light:#dbeafe;--border:#e5e7eb;--code-bg:#f5f5f5;--code-text:#1a1a2e;--radius:8px;--header-from:#1e3a5f;--header-to:#2563eb}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Heebo','Rubik','Assistant',system-ui,sans-serif;background:var(--bg);color:var(--text);line-height:1.8;direction:rtl}

/* ── Header ── */
.site-header{background:linear-gradient(135deg,var(--header-from),var(--header-to));color:#fff;padding:1.25rem 2rem;display:flex;align-items:center;gap:1rem;box-shadow:0 2px 8px rgba(0,0,0,.15)}
.logo-circle{width:44px;height:44px;border-radius:50%;background:rgba(255,255,255,.2);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:1rem;letter-spacing:.5px;flex-shrink:0}
.site-header .header-text h1{font-size:1.1rem;font-weight:600;margin:0;line-height:1.3}
.site-header .header-text .org{font-size:.8rem;opacity:.8;margin:0}
.header-badge{margin-left:auto;background:rgba(255,255,255,.18);padding:.3rem .75rem;border-radius:20px;font-size:.75rem;font-weight:500;letter-spacing:.3px}

/* ── Layout ── */
.page{display:grid;grid-template-columns:1fr 280px;max-width:1300px;margin:0 auto;min-height:calc(100vh - 70px)}

/* ── Sidebar ── */
.sidebar{position:sticky;top:0;height:calc(100vh - 70px);overflow-y:auto;padding:1.5rem;background:var(--surface);border-right:none;border-left:1px solid var(--border)}
.sidebar-card{background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);padding:1rem;margin-bottom:1rem}
.sidebar-card h3{font-size:.7rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin-bottom:.75rem;font-weight:600}
.sidebar a{display:block;padding:.3rem .5rem;color:var(--text);text-decoration:none;font-size:.85rem;border-right:2px solid transparent;border-left:none;margin-bottom:.15rem;border-radius:4px 0 0 4px;padding-right:.75rem;transition:all .15s}
.sidebar a:hover{color:var(--accent);border-right-color:var(--accent);background:var(--accent-light)}
.sidebar a.h3-link{padding-right:1.25rem;font-size:.8rem;color:var(--muted)}

/* ── Mobile TOC toggle ── */
.toc-toggle{display:none;position:fixed;bottom:1.5rem;left:1.5rem;z-index:100;background:var(--accent);color:#fff;border:none;border-radius:50%;width:48px;height:48px;font-size:1.3rem;cursor:pointer;box-shadow:0 3px 12px rgba(37,99,235,.4);transition:transform .2s}
.toc-toggle:hover{transform:scale(1.1)}

/* ── Content ── */
.content{padding:2.5rem 3.5rem;max-width:860px}
.doc-header{margin-bottom:2rem;padding-bottom:1.5rem;border-bottom:2px solid var(--border)}
.doc-header h1{font-size:2rem;font-weight:700;margin-bottom:.4rem;color:var(--text)}
.subtitle{color:var(--muted);font-size:1.05rem}
.date{color:var(--muted);font-size:.8rem;margin-top:.4rem}

/* ── Typography ── */
h2{font-size:1.4rem;font-weight:600;margin:2.5rem 0 1rem;padding-bottom:.4rem;border-bottom:2px solid var(--accent-light)}
h3{font-size:1.15rem;font-weight:600;margin:1.75rem 0 .75rem}
h4{font-size:1rem;font-weight:600;margin:1.25rem 0 .5rem}
p{margin-bottom:1rem}
a{color:var(--accent)}
ul,ol{margin:0 0 1rem 0;padding-right:1.5rem}
li{margin-bottom:.35rem}
li input[type="checkbox"]{margin-left:.4rem}
blockquote{border-right:3px solid var(--accent);border-left:none;padding:.75rem 1rem;margin:1rem 0;background:var(--accent-light);border-radius:var(--radius) 0 0 var(--radius)}

/* ── Warning boxes ── */
.warning-box{border-right:4px solid #f59e0b;background:#fffbeb;padding:1rem;border-radius:0 var(--radius) var(--radius) 0;margin:1rem 0}

/* ── Code ── */
pre{background:var(--code-bg);color:var(--code-text);padding:1.15rem 1.25rem;border-radius:var(--radius);overflow-x:auto;margin:1rem 0;font-size:.85rem;direction:ltr;text-align:left;border:1px solid var(--border)}
code{font-family:'JetBrains Mono',monospace;font-size:.85em;direction:ltr}
p code,li code{background:#e8eaed;color:#c7254e;padding:.15rem .4rem;border-radius:4px}
pre code{background:transparent;color:inherit;padding:0}

/* ── Tables ── */
table{width:100%;border-collapse:collapse;margin:1rem 0;font-size:.9rem}
th,td{border:1px solid var(--border);padding:.6rem .8rem;text-align:right}
th{background:var(--accent);color:#fff;font-weight:600}
tr:nth-child(even){background:#f5f6f8}

/* ── Misc ── */
hr{border:none;border-top:1px solid var(--border);margin:2rem 0}
img{max-width:100%;border-radius:var(--radius);margin:1rem 0}
.footer{margin-top:3rem;padding:1.5rem 0;border-top:1px solid var(--border);color:var(--muted);font-size:.8rem;display:flex;justify-content:space-between;align-items:center}

/* ── Print ── */
@media print{
  .site-header{background:var(--accent)!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .sidebar,.toc-toggle{display:none!important}
  .page{grid-template-columns:1fr}
  .content{padding:1rem;max-width:100%}
  pre{white-space:pre-wrap;word-break:break-all}
}

/* ── Mobile ── */
@media(max-width:768px){
  .page{grid-template-columns:1fr}
  .sidebar{display:none;position:fixed;top:0;left:0;right:0;bottom:0;z-index:99;height:100vh;border:none;box-shadow:0 0 30px rgba(0,0,0,.3)}
  .sidebar.open{display:block}
  .toc-toggle{display:flex;align-items:center;justify-content:center}
  .content{padding:1.5rem}
}
{{DIAGRAM_CSS}}
</style>
</head>
<body>
<header class="site-header">
  <div class="logo-circle">{{LOGO_TEXT}}</div>
  <div class="header-text">
    <h1>{{PROJECT_NAME}}</h1>
    <div class="org">{{ORG_NAME}}</div>
  </div>
  <div class="header-badge">{{BADGE_TEXT}}</div>
</header>
<div class="page">
<main class="content">
<div class="doc-header">
<h1>{{TITLE}}</h1>
<div class="subtitle">{{SUBTITLE}}</div>
<div class="date">{{GENERATION_DATE}}</div>
</div>
{{CONTENT}}
<div class="footer">
  <span>{{FOOTER_TEXT}}</span>
  <span>Generated: {{GENERATION_DATE}}</span>
</div>
</main>
<nav class="sidebar" id="sidebar">
  <div class="sidebar-card">
    <h3>&#1514;&#1493;&#1499;&#1503; &#1506;&#1504;&#1497;&#1497;&#1504;&#1497;&#1501;</h3>
    {{TOC}}
  </div>
</nav>
</div>
<button class="toc-toggle" onclick="document.getElementById('sidebar').classList.toggle('open')" aria-label="Toggle table of contents">&#128209; &#1514;&#1493;&#1499;&#1503; &#1506;&#1504;&#1497;&#1497;&#1504;&#1497;&#1501;</button>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script>hljs.highlightAll();</script>
<script type="module">
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
mermaid.initialize({startOnLoad:true,theme:'default'});
</script>
{{DIAGRAM_SCRIPTS}}
</body>
</html>
"""

INDEX_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{TITLE}}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#f8f9fa;--surface:#fff;--text:#1a1a2e;--muted:#6b7280;--accent:#2563eb;--border:#e5e7eb;--radius:8px}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',system-ui,sans-serif;background:var(--bg);color:var(--text);line-height:1.7}
.container{max-width:800px;margin:0 auto;padding:3rem 2rem}
h1{font-size:2rem;font-weight:700;margin-bottom:.5rem}
.subtitle{color:var(--muted);margin-bottom:2rem}
.section{margin-bottom:2rem}
.section h2{font-size:1.2rem;font-weight:600;margin-bottom:.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;font-size:.85rem}
.card{display:block;padding:1rem 1.25rem;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);margin-bottom:.5rem;text-decoration:none;color:var(--text);transition:border-color .15s}
.card:hover{border-color:var(--accent)}
.card .title{font-weight:600;margin-bottom:.25rem}
.card .desc{color:var(--muted);font-size:.9rem}
.footer{margin-top:3rem;padding-top:1rem;border-top:1px solid var(--border);color:var(--muted);font-size:.8rem}
</style>
</head>
<body>
<div class="container">
<h1>{{TITLE}}</h1>
<div class="subtitle">{{SUBTITLE}}</div>
{{CONTENT}}
<div class="footer">Generated: {{GENERATION_DATE}}</div>
</div>
</body>
</html>
"""


# ─── Hebrew detection ─────────────────────────────────────────────────────────

def is_hebrew(text: str) -> bool:
    """Return True if >5% of alphabetic characters are Hebrew."""
    hebrew = sum(1 for c in text if '\u0590' <= c <= '\u05FF')
    alpha = sum(1 for c in text if c.isalpha())
    return alpha > 0 and (hebrew / alpha) > 0.05


# ─── Markdown → HTML ──────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Create URL-safe anchor from heading text."""
    text = re.sub(r'<[^>]+>', '', text)  # strip HTML tags
    text = re.sub(r'[^\w\s\u0590-\u05FF-]', '', text)
    return re.sub(r'[\s]+', '-', text.strip()).lower()


def md_to_html(md: str) -> tuple:
    """Convert markdown string to (html_content, headings_list).

    Returns:
        (html_str, [(level, text, slug), ...])
    """
    lines = md.split('\n')
    out = []
    headings = []
    in_code_block = False
    code_lang = ''
    code_lines = []
    in_list = False
    list_type = None  # 'ul' or 'ol'
    in_table = False
    table_rows = []
    in_blockquote = False
    bq_lines = []

    def flush_list():
        nonlocal in_list, list_type
        if in_list:
            out.append(f'</{list_type}>')
            in_list = False
            list_type = None

    def flush_table():
        nonlocal in_table, table_rows
        if not in_table:
            return
        in_table = False
        if not table_rows:
            return
        html_t = '<table>\n<thead><tr>'
        headers = table_rows[0]
        for h in headers:
            html_t += f'<th>{inline(h.strip())}</th>'
        html_t += '</tr></thead>\n<tbody>\n'
        # skip separator row (index 1)
        for row in table_rows[2:]:
            html_t += '<tr>'
            for cell in row:
                html_t += f'<td>{inline(cell.strip())}</td>'
            html_t += '</tr>\n'
        html_t += '</tbody></table>'
        out.append(html_t)
        table_rows = []

    def flush_blockquote():
        nonlocal in_blockquote, bq_lines
        if in_blockquote:
            content = '\n'.join(bq_lines)
            out.append(f'<blockquote>{inline(content)}</blockquote>')
            in_blockquote = False
            bq_lines = []

    def inline(text: str) -> str:
        """Process inline markdown: bold, italic, code, links, images, checkboxes."""
        # Images: ![alt](src)
        text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'<img src="\2" alt="\1">', text)
        # Links: [text](url)
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
        # Inline code (must be before bold/italic)
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
        # Bold + italic
        text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
        # Bold
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        # Italic
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        # Strikethrough
        text = re.sub(r'~~(.+?)~~', r'<del>\1</del>', text)
        # Checkboxes
        text = text.replace('[ ]', '<input type="checkbox" disabled>')
        text = text.replace('[x]', '<input type="checkbox" checked disabled>')
        text = text.replace('[X]', '<input type="checkbox" checked disabled>')
        return text

    i = 0
    while i < len(lines):
        line = lines[i]

        # Code blocks
        if re.match(r'^```', line):
            if in_code_block:
                if code_lang.lower() in DIAGRAM_LANGUAGES:
                    raw_source = '\n'.join(code_lines)
                    lang_lower = code_lang.lower()
                    compat = DIAGRAM_LANGUAGES[lang_lower]
                    renderers_str = ','.join(compat)
                    toolbar = ''
                    if len(compat) > 1:
                        opts = ''.join(f'<option value="{r}">{r}</option>' for r in compat)
                        toolbar = f'<div class="diagram-toolbar"><select>{opts}</select></div>'
                    out.append(
                        f'<div class="diagram-block" data-lang="{html.escape(lang_lower)}" data-renderers="{html.escape(renderers_str)}">'
                        f'<script type="text/diagram">{raw_source}</script>'
                        f'{toolbar}'
                        f'<div class="diagram-render"></div>'
                        f'</div>'
                    )
                else:
                    escaped = html.escape('\n'.join(code_lines))
                    cls = f' class="language-{code_lang}"' if code_lang else ''
                    out.append(f'<pre><code{cls}>{escaped}</code></pre>')
                in_code_block = False
                code_lines = []
                code_lang = ''
            else:
                flush_list()
                flush_table()
                flush_blockquote()
                in_code_block = True
                code_lang = line[3:].strip()
            i += 1
            continue

        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        # Blank line
        if not line.strip():
            flush_list()
            flush_table()
            flush_blockquote()
            i += 1
            continue

        # Table row
        if '|' in line and re.match(r'^\s*\|', line):
            flush_list()
            flush_blockquote()
            cells = [c for c in line.split('|')[1:-1]]  # strip first/last empty
            if not in_table:
                in_table = True
                table_rows = [cells]
            else:
                table_rows.append(cells)
            i += 1
            continue
        else:
            flush_table()

        # Blockquote
        if line.startswith('>'):
            flush_list()
            flush_table()
            content = re.sub(r'^>\s?', '', line)
            if not in_blockquote:
                in_blockquote = True
                bq_lines = [content]
            else:
                bq_lines.append(content)
            i += 1
            continue
        else:
            flush_blockquote()

        # Headings
        m = re.match(r'^(#{1,6})\s+(.+)', line)
        if m:
            flush_list()
            level = len(m.group(1))
            text = m.group(2).strip()
            slug = slugify(text)
            processed = inline(text)
            if level >= 2:
                headings.append((level, text, slug))
            out.append(f'<h{level} id="{slug}">{processed}</h{level}>')
            i += 1
            continue

        # Horizontal rule
        if re.match(r'^(-{3,}|\*{3,}|_{3,})\s*$', line):
            flush_list()
            out.append('<hr>')
            i += 1
            continue

        # Unordered list
        m = re.match(r'^(\s*)[-*+]\s+(.*)', line)
        if m:
            flush_table()
            flush_blockquote()
            if not in_list or list_type != 'ul':
                flush_list()
                out.append('<ul>')
                in_list = True
                list_type = 'ul'
            out.append(f'<li>{inline(m.group(2))}</li>')
            i += 1
            continue

        # Ordered list
        m = re.match(r'^(\s*)\d+\.\s+(.*)', line)
        if m:
            flush_table()
            flush_blockquote()
            if not in_list or list_type != 'ol':
                flush_list()
                out.append('<ol>')
                in_list = True
                list_type = 'ol'
            out.append(f'<li>{inline(m.group(2))}</li>')
            i += 1
            continue

        # Paragraph
        flush_list()
        out.append(f'<p>{inline(line)}</p>')
        i += 1

    # Flush any remaining state
    flush_list()
    flush_table()
    flush_blockquote()
    if in_code_block:
        escaped = html.escape('\n'.join(code_lines))
        out.append(f'<pre><code>{escaped}</code></pre>')

    return '\n'.join(out), headings


# ─── Extract metadata ─────────────────────────────────────────────────────────

def extract_metadata(md: str) -> tuple:
    """Extract title and subtitle from markdown.

    Title: first # heading.
    Subtitle: first > blockquote, or next heading, or first paragraph.
    """
    title = ''
    subtitle = ''
    for line in md.split('\n'):
        line = line.strip()
        if not title:
            m = re.match(r'^#\s+(.+)', line)
            if m:
                title = m.group(1).strip()
                continue
        elif not subtitle:
            # Try blockquote
            m = re.match(r'^>\s*(.+)', line)
            if m:
                subtitle = m.group(1).strip()
                break
            # Try heading
            m = re.match(r'^#{2,}\s+(.+)', line)
            if m:
                subtitle = m.group(1).strip()
                break
            # Try non-empty paragraph (skip hr and blank)
            if line and not re.match(r'^(-{3,}|\*{3,}|_{3,})$', line):
                subtitle = line
                break
    return title or 'Untitled', subtitle


# ─── Build TOC ────────────────────────────────────────────────────────────────

def build_toc(headings: list) -> str:
    """Build sidebar TOC HTML from headings list."""
    if not headings:
        return ''
    parts = []
    for level, text, slug in headings:
        cls = ' class="h3-link"' if level >= 3 else ''
        parts.append(f'<a href="#{slug}"{cls}>{text}</a>')
    return '\n'.join(parts)


# ─── Convert single file ─────────────────────────────────────────────────────

def convert_file(md_path: str) -> str:
    """Convert a single .md file to .html. Returns output path."""
    md_path = Path(md_path).resolve()
    md_text = md_path.read_text(encoding='utf-8')

    title, subtitle = extract_metadata(md_text)
    content_html, headings = md_to_html(md_text)
    toc_html = build_toc(headings)
    gen_date = datetime.now().strftime('%Y-%m-%d %H:%M')

    is_rtl = is_hebrew(md_text)
    template = RTL_TEMPLATE if is_rtl else LTR_TEMPLATE

    config = load_config(md_path.parent)

    badge_default = '\u05de\u05e1\u05de\u05da' if is_rtl else 'Document'

    has_diagrams = 'class="diagram-block"' in content_html
    final = (template
             .replace('{{TITLE}}', html.escape(title))
             .replace('{{SUBTITLE}}', html.escape(subtitle))
             .replace('{{TOC}}', toc_html)
             .replace('{{CONTENT}}', content_html)
             .replace('{{GENERATION_DATE}}', gen_date)
             .replace('{{PROJECT_NAME}}', html.escape(config['projectName']))
             .replace('{{ORG_NAME}}', html.escape(config['orgName']))
             .replace('{{LOGO_TEXT}}', html.escape(config['logoText']))
             .replace('{{BADGE_TEXT}}', html.escape(config.get('badgeText', badge_default)))
             .replace('{{FOOTER_TEXT}}', html.escape(config['footerText']))
             .replace('{{DIAGRAM_CSS}}', DIAGRAM_CSS if has_diagrams else '')
             .replace('{{DIAGRAM_SCRIPTS}}', DIAGRAM_SCRIPTS if has_diagrams else ''))

    out_path = md_path.with_suffix('.html')
    out_path.write_text(final, encoding='utf-8')
    return str(out_path)


# ─── Generate index ──────────────────────────────────────────────────────────

def generate_index(folder: str) -> str:
    """Generate index.html for a folder listing .md files and subfolders."""
    folder = Path(folder).resolve()
    folder_name = folder.name or 'Docs'
    gen_date = datetime.now().strftime('%Y-%m-%d %H:%M')

    # Collect .md files
    md_files = sorted(folder.glob('*.md'))
    # Collect subdirectories that contain .md files
    subdirs = sorted([d for d in folder.iterdir()
                      if d.is_dir() and not d.name.startswith('.')
                      and list(d.glob('*.md'))])

    sections_html = ''

    if md_files:
        sections_html += '<div class="section"><h2>Documents</h2>\n'
        for md in md_files:
            text = md.read_text(encoding='utf-8')
            t, s = extract_metadata(text)
            html_name = md.stem + '.html'
            desc = f'<div class="desc">{html.escape(s)}</div>' if s else ''
            sections_html += (f'<a class="card" href="{html_name}">'
                              f'<div class="title">{html.escape(t)}</div>{desc}</a>\n')
        sections_html += '</div>\n'

    if subdirs:
        sections_html += '<div class="section"><h2>Folders</h2>\n'
        for d in subdirs:
            count = len(list(d.glob('*.md')))
            sections_html += (f'<a class="card" href="{d.name}/index.html">'
                              f'<div class="title">{d.name}/</div>'
                              f'<div class="desc">{count} document{"s" if count != 1 else ""}</div></a>\n')
        sections_html += '</div>\n'

    final = (INDEX_TEMPLATE
             .replace('{{TITLE}}', html.escape(folder_name))
             .replace('{{SUBTITLE}}', f'{len(md_files)} documents')
             .replace('{{CONTENT}}', sections_html)
             .replace('{{GENERATION_DATE}}', gen_date))

    out_path = folder / 'index.html'
    out_path.write_text(final, encoding='utf-8')
    return str(out_path)


# ─── Batch operations ────────────────────────────────────────────────────────

def convert_folder(folder: str, recursive: bool = False) -> list:
    """Convert all .md files in a folder. Returns list of output paths."""
    folder = Path(folder).resolve()
    pattern = '**/*.md' if recursive else '*.md'
    results = []
    for md in sorted(folder.glob(pattern)):
        if md.name.startswith('_'):
            continue
        results.append(convert_file(str(md)))
        print(f'  converted: {md.name}')
    return results


def convert_all(root: str) -> None:
    """Recursively convert all .md and generate all indexes."""
    root = Path(root).resolve()
    # Convert files
    convert_folder(str(root), recursive=True)
    # Generate indexes bottom-up
    dirs_with_md = set()
    for md in root.rglob('*.md'):
        dirs_with_md.add(md.parent)
    # Sort by depth descending so children are indexed before parents
    for d in sorted(dirs_with_md, key=lambda p: len(p.parts), reverse=True):
        idx = generate_index(str(d))
        print(f'  index: {idx}')
    # Root index if it has subdirs
    if dirs_with_md:
        idx = generate_index(str(root))
        print(f'  index: {idx}')


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    if args[0] == '--all' and len(args) >= 2:
        root = args[1]
        print(f'Converting all in {root}...')
        convert_all(root)
        return

    if args[0] == '--index' and len(args) >= 2:
        folder = args[1]
        idx = generate_index(folder)
        print(f'Index generated: {idx}')
        return

    target = args[0]
    p = Path(target)

    if p.is_file() and p.suffix == '.md':
        out = convert_file(str(p))
        print(f'Converted: {out}')
        return

    if p.is_dir():
        print(f'Converting folder {p}...')
        convert_folder(str(p))
        idx = generate_index(str(p))
        print(f'Index generated: {idx}')
        return

    # Glob pattern
    matches = sorted(globmod.glob(target, recursive=True))
    md_matches = [m for m in matches if m.endswith('.md')]
    if md_matches:
        for md in md_matches:
            out = convert_file(md)
            print(f'Converted: {out}')
        return

    print(f'Error: {target} is not a file, directory, or matching glob pattern.')
    sys.exit(1)


if __name__ == '__main__':
    main()
