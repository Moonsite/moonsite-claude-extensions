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
    'mermaid': ['mermaid'],
    'pintora': ['pintora'],
    'dot': ['vizjs'],
    'graphviz': ['vizjs'],
    'nomnoml': ['nomnoml'],
}

DIAGRAM_CSS = """\
.diagram-block{margin:1rem 0;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:1rem;overflow-x:auto}
.diagram-render{min-height:40px;display:flex;justify-content:center}
.diagram-render svg{width:100%;height:auto;max-height:80vh}
.diagram-error{color:#dc2626;font-size:.875rem;padding:.5rem;background:#fef2f2;border-radius:4px}
"""

DIAGRAM_SCRIPTS = """\
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@viz-js/viz/lib/viz-standalone.js"></script>
<script src="https://unpkg.com/graphre/dist/graphre.js"></script>
<script src="https://unpkg.com/nomnoml/dist/nomnoml.js"></script>
<script type="module">
import elkLayouts from 'https://cdn.jsdelivr.net/npm/@mermaid-js/layout-elk/dist/mermaid-layout-elk.esm.min.mjs';
mermaid.registerLayoutLoaders(elkLayouts);
mermaid.initialize({
  startOnLoad:false,
  look:'neo',
  theme:'base',
  layout:'elk',
  themeVariables:{
    primaryColor:'#dbeafe',
    primaryTextColor:'#1e3a5f',
    primaryBorderColor:'#3b82f6',
    lineColor:'#94a3b8',
    secondaryColor:'#f1f5f9',
    tertiaryColor:'#eff6ff',
    noteBkgColor:'#fef3c7',
    noteBorderColor:'#f59e0b',
    noteTextColor:'#92400e',
    actorBkg:'#dbeafe',
    actorBorder:'#3b82f6',
    actorTextColor:'#1e3a5f',
    signalColor:'#475569',
    signalTextColor:'#1e293b',
    activationBkgColor:'#eff6ff',
    activationBorderColor:'#3b82f6',
    fontFamily:'Inter,system-ui,sans-serif'
  },
  flowchart:{useMaxWidth:true,htmlLabels:true,padding:15},
  sequence:{useMaxWidth:true,wrap:true,width:200}
});
var renderers={
  mermaid:function(src,el){
    var id='mermaid-'+Math.random().toString(36).substr(2,9);
    mermaid.render(id,src).then(function(result){
      el.insertAdjacentHTML('beforeend',result.svg);
    }).catch(function(e){
      var errDiv=document.createElement('div');
      errDiv.className='diagram-error';
      errDiv.textContent='Render error: '+e.message;
      el.appendChild(errDiv);
    });
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
document.querySelectorAll('.diagram-block').forEach(function(block){
  var target=block.querySelector('.diagram-render');
  var src=block.querySelector('script[type="text/diagram"]').textContent;
  var renderer=block.dataset.renderers;
  target.textContent='';
  try{
    renderers[renderer](src,target);
  }catch(e){
    var errDiv=document.createElement('div');
    errDiv.className='diagram-error';
    errDiv.textContent='Render error: '+e.message;
    target.appendChild(errDiv);
  }
});
</script>
"""

# ─── Config loading ──────────────────────────────────────────────────────────

def load_config(start_dir, title=''):
    """Search up from start_dir for .claude/md-html-docs.json and return config dict.

    When no config file is found, uses the document title for smart defaults
    instead of generic 'Documentation'/'Docs'.
    """
    defaults = {
        'projectName': '',
        'orgName': '',
        'logoText': '',
        'footerText': '',
    }
    d = Path(start_dir).resolve()
    found_config = False
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
                found_config = True
                return result
            except (json.JSONDecodeError, OSError):
                break
        parent = d.parent
        if parent == d:
            break
        d = parent
    # No config found — derive smart defaults from document title
    if title:
        defaults['projectName'] = title
        defaults['logoText'] = title[:2]
    else:
        defaults['projectName'] = 'Documentation'
        defaults['logoText'] = 'Docs'
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
.header-badge:empty,.org:empty{display:none}

/* ── Layout ── */
.page{display:grid;grid-template-columns:280px 1fr;max-width:1300px;margin:0 auto;min-height:calc(100vh - 70px)}

/* ── Sidebar ── */
.sidebar{position:sticky;top:0;height:calc(100vh - 70px);overflow-y:auto;padding:1.5rem;background:var(--surface);border-right:1px solid var(--border)}
.sidebar-card{background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);padding:1rem;margin-bottom:1rem}
.sidebar-card h3{font-size:.7rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin-bottom:.75rem;font-weight:600}
.sidebar a{display:block;padding:.3rem .5rem;color:var(--text);text-decoration:none;font-size:.85rem;border-left:2px solid transparent;margin-bottom:.15rem;border-radius:0 4px 4px 0;transition:all .15s}
.sidebar a:hover{color:var(--accent);border-left-color:var(--accent);background:var(--accent-light)}
.sidebar a.h3-link{padding-left:1.25rem;font-size:.8rem;color:var(--muted)}
.index-link{display:block;padding:.5rem .5rem .75rem;font-weight:600;font-size:.85rem;color:var(--accent)!important;border-bottom:1px solid var(--border);margin-bottom:.5rem;text-decoration:none}
.index-link:hover{text-decoration:underline}
/* ── Collapsible TOC ── */
.sidebar details{margin-bottom:.15rem}
.sidebar details summary{list-style:none;cursor:pointer}
.sidebar details summary::-webkit-details-marker{display:none}
.sidebar details summary::before{content:'▸';display:inline-block;width:1em;font-size:.7em;transition:transform .15s;vertical-align:middle}
.sidebar details[open] summary::before{transform:rotate(90deg)}
.sidebar details summary a{display:inline}
/* ── Layout switcher ── */
.layout-toolbar{margin-left:auto;display:flex;gap:.3rem;align-items:center}
.layout-toolbar button{background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.25);border-radius:4px;padding:.2rem .55rem;font-size:.7rem;cursor:pointer;color:rgba(255,255,255,.8);transition:all .15s}
.layout-toolbar button:hover{background:rgba(255,255,255,.25)}
.layout-toolbar button.active{background:rgba(255,255,255,.35);color:#fff;border-color:rgba(255,255,255,.5)}
.layout-narrow .content{max-width:860px}
.layout-wide .content{max-width:1100px}
.layout-fluid .page{max-width:100%}
.layout-fluid .content{max-width:100%}

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
  <div class="layout-toolbar">
    <button onclick="setLayout('narrow')" id="btn-narrow">Narrow</button>
    <button onclick="setLayout('wide')" id="btn-wide">Wide</button>
    <button onclick="setLayout('fluid')" id="btn-fluid">Full</button>
  </div>
</header>
<div class="page">
<nav class="sidebar" id="sidebar">
  <div class="sidebar-card">
    <a href="index.html" class="index-link">&#128196; Index</a>
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
<script>
function setLayout(mode){
  var page=document.querySelector('.page');
  page.classList.remove('layout-narrow','layout-wide','layout-fluid');
  page.classList.add('layout-'+mode);
  document.querySelectorAll('.layout-toolbar button').forEach(function(b){b.classList.remove('active')});
  document.getElementById('btn-'+mode).classList.add('active');
  try{localStorage.setItem('doc-layout',mode)}catch(e){}
}
(function(){var m=localStorage.getItem('doc-layout')||'narrow';setLayout(m)})();
</script>
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
.header-badge:empty,.org:empty{display:none}

/* ── Layout ── */
.page{display:grid;grid-template-columns:280px 1fr;max-width:1300px;margin:0 auto;min-height:calc(100vh - 70px)}

/* ── Sidebar ── */
.sidebar{position:sticky;top:0;height:calc(100vh - 70px);overflow-y:auto;padding:1.5rem;background:var(--surface);border-right:none;border-left:1px solid var(--border)}
.sidebar-card{background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);padding:1rem;margin-bottom:1rem}
.sidebar-card h3{font-size:.7rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin-bottom:.75rem;font-weight:600}
.sidebar a{display:block;padding:.3rem .5rem;color:var(--text);text-decoration:none;font-size:.85rem;border-right:2px solid transparent;border-left:none;margin-bottom:.15rem;border-radius:4px 0 0 4px;padding-right:.75rem;transition:all .15s}
.sidebar a:hover{color:var(--accent);border-right-color:var(--accent);background:var(--accent-light)}
.sidebar a.h3-link{padding-right:1.25rem;font-size:.8rem;color:var(--muted)}
.index-link{display:block;padding:.5rem .5rem .75rem;font-weight:600;font-size:.85rem;color:var(--accent)!important;border-bottom:1px solid var(--border);margin-bottom:.5rem;text-decoration:none}
.index-link:hover{text-decoration:underline}
/* ── Collapsible TOC ── */
.sidebar details{margin-bottom:.15rem}
.sidebar details summary{list-style:none;cursor:pointer}
.sidebar details summary::-webkit-details-marker{display:none}
.sidebar details summary::before{content:'◂';display:inline-block;width:1em;font-size:.7em;transition:transform .15s;vertical-align:middle}
.sidebar details[open] summary::before{transform:rotate(-90deg)}
.sidebar details summary a{display:inline}
/* ── Layout switcher ── */
.layout-toolbar{margin-left:auto;display:flex;gap:.3rem;align-items:center}
.layout-toolbar button{background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.25);border-radius:4px;padding:.2rem .55rem;font-size:.7rem;cursor:pointer;color:rgba(255,255,255,.8);transition:all .15s}
.layout-toolbar button:hover{background:rgba(255,255,255,.25)}
.layout-toolbar button.active{background:rgba(255,255,255,.35);color:#fff;border-color:rgba(255,255,255,.5)}
.layout-narrow .content{max-width:860px}
.layout-wide .content{max-width:1100px}
.layout-fluid .page{max-width:100%}
.layout-fluid .content{max-width:100%}

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
  <div class="layout-toolbar">
    <button onclick="setLayout('narrow')" id="btn-narrow">&#1510;&#1512;</button>
    <button onclick="setLayout('wide')" id="btn-wide">&#1512;&#1495;&#1489;</button>
    <button onclick="setLayout('fluid')" id="btn-fluid">&#1502;&#1500;&#1488;</button>
  </div>
</header>
<div class="page">
<nav class="sidebar" id="sidebar">
  <div class="sidebar-card">
    <a href="index.html" class="index-link">&#128196; &#1488;&#1497;&#1504;&#1491;&#1511;&#1505;</a>
    <h3>&#1514;&#1493;&#1499;&#1503; &#1506;&#1504;&#1497;&#1497;&#1504;&#1497;&#1501;</h3>
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
<button class="toc-toggle" onclick="document.getElementById('sidebar').classList.toggle('open')" aria-label="Toggle table of contents">&#128209; &#1514;&#1493;&#1499;&#1503; &#1506;&#1504;&#1497;&#1497;&#1504;&#1497;&#1501;</button>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script>hljs.highlightAll();</script>
<script>
function setLayout(mode){
  var page=document.querySelector('.page');
  page.classList.remove('layout-narrow','layout-wide','layout-fluid');
  page.classList.add('layout-'+mode);
  document.querySelectorAll('.layout-toolbar button').forEach(function(b){b.classList.remove('active')});
  document.getElementById('btn-'+mode).classList.add('active');
  try{localStorage.setItem('doc-layout',mode)}catch(e){}
}
(function(){var m=localStorage.getItem('doc-layout')||'narrow';setLayout(m)})();
</script>
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
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Heebo:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;background:#f0f2f5;color:#212121;min-height:100vh}
.header{background:linear-gradient(135deg,{{HEADER_FROM}} 0%,{{HEADER_TO}} 100%);color:#fff;padding:3rem 2rem;text-align:center}
.header-logo{width:80px;height:80px;background:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:32px;color:{{HEADER_FROM}};font-weight:700;margin:0 auto 1rem}
.header h1{font-size:36px;font-weight:700;margin-bottom:.5rem}
.header p{font-size:16px;opacity:.9;max-width:600px;margin:0 auto}
.container{max-width:1000px;margin:2.5rem auto;padding:0 2rem}
.section-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1.5rem}
.section-card{background:#fff;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,.08);overflow:hidden;transition:transform .2s,box-shadow .2s;text-decoration:none;color:inherit;display:flex;flex-direction:column}
.section-card:hover{transform:translateY(-4px);box-shadow:0 8px 24px rgba(0,0,0,.15)}
.card-accent{height:6px}
.card-accent.blue{background:linear-gradient(90deg,#1565C0,#42A5F5)}
.card-accent.green{background:linear-gradient(90deg,#2E7D32,#66BB6A)}
.card-accent.purple{background:linear-gradient(90deg,#7B1FA2,#BA68C8)}
.card-body{padding:1.5rem;flex:1;display:flex;flex-direction:column}
.card-icon{font-size:36px;margin-bottom:.75rem}
.card-lang{display:inline-block;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:1px;padding:.15rem .5rem;border-radius:8px;margin-bottom:.5rem;width:fit-content}
.card-lang.he{background:#E8F5E9;color:#2E7D32}
.card-lang.en{background:#E3F2FD;color:#1565C0}
.card-body h2{font-size:20px;font-weight:600;margin-bottom:.4rem}
.card-body p{font-size:14px;color:#616161;line-height:1.6;flex:1}
.card-meta{display:flex;gap:1.5rem;padding-top:1rem;margin-top:auto;border-top:1px solid #f0f0f0;font-size:13px;color:#9E9E9E}
.card-meta strong{color:#424242}
.footer{text-align:center;padding:2rem;color:#9E9E9E;font-size:13px;margin-top:1rem}
@media(max-width:480px){.section-grid{grid-template-columns:1fr}.header h1{font-size:28px}}
</style>
</head>
<body>
<header class="header">
  <div class="header-logo">{{LOGO_TEXT}}</div>
  <h1>{{PROJECT_NAME}}</h1>
  {{ORG_HTML}}
</header>
<div class="container">
<div class="section-grid">
{{CONTENT}}
</div>
</div>
<div class="footer">{{FOOTER_TEXT}} &mdash; Generated: {{GENERATION_DATE}}</div>
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
                    renderer = DIAGRAM_LANGUAGES[lang_lower][0]
                    out.append(
                        f'<div class="diagram-block" data-lang="{html.escape(lang_lower)}" data-renderers="{html.escape(renderer)}">'
                        f'<script type="text/diagram">{raw_source}</script>'
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
    Skips table rows (lines starting with |) to avoid picking up table content as subtitle.
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
            # Skip table rows
            if line.startswith('|'):
                continue
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
    """Build sidebar TOC HTML from headings list.

    Groups h3+ under parent h2 using <details><summary> for collapsible sections.
    Standalone h2s (no children) remain plain links.
    """
    if not headings:
        return ''
    # Group headings: list of (h2_entry, [children])
    groups = []
    for level, text, slug in headings:
        if level == 2:
            groups.append(((level, text, slug), []))
        elif groups:
            groups[-1][1].append((level, text, slug))
        else:
            # h3+ before any h2 — treat as standalone
            groups.append(((level, text, slug), []))

    parts = []
    for (level, text, slug), children in groups:
        if not children or level != 2:
            cls = ' class="h3-link"' if level >= 3 else ''
            parts.append(f'<a href="#{slug}"{cls}>{text}</a>')
        else:
            inner = ''.join(
                f'<a href="#{cs}" class="h3-link">{ct}</a>'
                for cl, ct, cs in children
            )
            parts.append(
                f'<details open><summary><a href="#{slug}">{text}</a></summary>'
                f'{inner}</details>'
            )
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

    config = load_config(md_path.parent, title=title)

    # Conditional badge/org HTML
    badge_text = config.get('badgeText', '')
    org_name = config.get('orgName', '')

    has_diagrams = 'class="diagram-block"' in content_html
    final = (template
             .replace('{{TITLE}}', html.escape(title))
             .replace('{{SUBTITLE}}', html.escape(subtitle))
             .replace('{{TOC}}', toc_html)
             .replace('{{CONTENT}}', content_html)
             .replace('{{GENERATION_DATE}}', gen_date)
             .replace('{{PROJECT_NAME}}', html.escape(config['projectName']))
             .replace('{{ORG_NAME}}', html.escape(org_name) if org_name else '')
             .replace('{{LOGO_TEXT}}', html.escape(config['logoText']))
             .replace('{{BADGE_TEXT}}', html.escape(badge_text) if badge_text else '')
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

    cards_html = ''
    accent_colors = ['blue', 'green', 'purple']

    if md_files:
        for idx, md in enumerate(md_files):
            text = md.read_text(encoding='utf-8')
            t, s = extract_metadata(text)
            html_name = md.stem + '.html'
            is_heb = is_hebrew(text)
            lang_cls = 'he' if is_heb else 'en'
            lang_label = 'Hebrew' if is_heb else 'English'
            accent = accent_colors[idx % len(accent_colors)]
            icon = '&#128214;' if is_heb else '&#128196;'
            desc_html = f'<p>{html.escape(s)}</p>' if s else '<p></p>'
            cards_html += (
                f'<a class="section-card" href="{html_name}">'
                f'<div class="card-accent {accent}"></div>'
                f'<div class="card-body">'
                f'<div class="card-icon">{icon}</div>'
                f'<span class="card-lang {lang_cls}">{lang_label}</span>'
                f'<h2>{html.escape(t)}</h2>'
                f'{desc_html}'
                f'<div class="card-meta">'
                f'<span><strong>{lang_label}</strong> doc</span>'
                f'</div>'
                f'</div></a>\n'
            )

    if subdirs:
        for idx, d in enumerate(subdirs):
            md_count = len(list(d.glob('*.md')))
            # Check language of first .md in subfolder
            first_md = next(d.glob('*.md'), None)
            is_heb = False
            if first_md:
                sample = first_md.read_text(encoding='utf-8')[:500]
                is_heb = is_hebrew(sample)
            lang_cls = 'he' if is_heb else 'en'
            lang_label = 'Hebrew' if is_heb else 'English'
            accent = accent_colors[(idx + len(md_files)) % len(accent_colors)]
            icon = '&#128194;'
            cards_html += (
                f'<a class="section-card" href="{d.name}/index.html">'
                f'<div class="card-accent {accent}"></div>'
                f'<div class="card-body">'
                f'<div class="card-icon">{icon}</div>'
                f'<span class="card-lang {lang_cls}">{lang_label}</span>'
                f'<h2>{d.name}</h2>'
                f'<p>{md_count} document{"s" if md_count != 1 else ""}</p>'
                f'<div class="card-meta">'
                f'<span><strong>{md_count}</strong> doc{"s" if md_count != 1 else ""}</span>'
                f'</div>'
                f'</div></a>\n'
            )

    config = load_config(str(folder), title=folder_name)
    org_name = config.get('orgName', '')
    org_html = f'<p>{html.escape(org_name)}</p>' if org_name else ''
    header_from = config.get('headerFrom', '#1e3a5f')
    header_to = config.get('headerTo', '#2563eb')

    final = (INDEX_TEMPLATE
             .replace('{{TITLE}}', html.escape(folder_name))
             .replace('{{SUBTITLE}}', f'{len(md_files)} documents')
             .replace('{{CONTENT}}', cards_html)
             .replace('{{GENERATION_DATE}}', gen_date)
             .replace('{{PROJECT_NAME}}', html.escape(config['projectName']))
             .replace('{{LOGO_TEXT}}', html.escape(config['logoText']))
             .replace('{{ORG_HTML}}', org_html)
             .replace('{{FOOTER_TEXT}}', html.escape(config['footerText']))
             .replace('{{HEADER_FROM}}', header_from)
             .replace('{{HEADER_TO}}', header_to))

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
