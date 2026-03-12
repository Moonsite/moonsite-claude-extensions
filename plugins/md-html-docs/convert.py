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
    'd2': ['kroki'],
}

COLOR_PRESETS = {
    'blue': {
        'accentColor': '#2563eb', 'accentLight': '#dbeafe',
        'headerFrom': '#1e3a5f', 'headerTo': '#2563eb',
    },
    'green': {
        'accentColor': '#16a34a', 'accentLight': '#dcfce7',
        'headerFrom': '#14532d', 'headerTo': '#16a34a',
    },
    'purple': {
        'accentColor': '#7c3aed', 'accentLight': '#ede9fe',
        'headerFrom': '#3b0764', 'headerTo': '#7c3aed',
    },
    'orange': {
        'accentColor': '#ea580c', 'accentLight': '#fff7ed',
        'headerFrom': '#7c2d12', 'headerTo': '#ea580c',
    },
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
  },
  kroki:function(src,el){
    var lang=el.closest('.diagram-block').dataset.lang||'d2';
    el.textContent='Rendering...';
    fetch('https://kroki.io/'+lang+'/svg',{method:'POST',headers:{'Content-Type':'text/plain'},body:src})
    .then(function(r){if(!r.ok)throw new Error('Kroki returned '+r.status);return r.text()})
    .then(function(svg){el.innerHTML=svg})
    .catch(function(e){var d=document.createElement('div');d.className='diagram-error';d.textContent='Render error: '+e.message;el.textContent='';el.appendChild(d)});
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

# ─── Sticky Notes (review annotations) ──────────────────────────────────────

NOTES_CSS = """\
/* ── Inline Review Notes (text-selection annotations) ── */
mark.noted{background:#fef08a;border-bottom:2px solid #eab308;cursor:pointer;border-radius:2px;padding:0 1px;transition:background .15s}
mark.noted:hover{background:#fde047}
mark.noted.active{background:#fde047;box-shadow:0 0 0 2px rgba(234,179,8,.4)}
.note-popup{position:absolute;z-index:200;background:#fff;border:1px solid #e5e7eb;border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,.15);padding:.15rem;animation:noteIn .15s ease}
.note-popup button{background:#eab308;color:#fff;border:none;border-radius:6px;padding:.35rem .7rem;font-size:.8rem;cursor:pointer;font-family:inherit;white-space:nowrap;display:flex;align-items:center;gap:.3rem}
.note-popup button:hover{background:#ca8a04}
.note-editor{position:absolute;z-index:200;background:#fef9c3;border:1px solid #facc15;border-radius:10px;padding:.75rem;width:320px;box-shadow:0 6px 24px rgba(234,179,8,.2);animation:noteIn .2s ease}
.note-editor textarea{width:100%;min-height:70px;border:1px solid #e5e7eb;border-radius:6px;padding:.5rem;font-family:inherit;font-size:.85rem;resize:vertical;background:#fffef5}
.note-editor .note-selected{font-size:.75rem;color:#92400e;margin-bottom:.4rem;padding:.25rem .4rem;background:#fef3c7;border-radius:4px;max-height:40px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.note-editor .note-actions{display:flex;gap:.4rem;margin-top:.5rem;justify-content:flex-end}
.note-editor .note-actions button{padding:.3rem .7rem;border-radius:5px;border:1px solid #d1d5db;cursor:pointer;font-size:.78rem;font-family:inherit}
.note-editor .note-actions .note-save{background:#2563eb;color:#fff;border-color:#2563eb}
.note-editor .note-actions .note-save:hover{background:#1d4ed8}
.note-editor .note-actions .note-delete{background:#fff;color:#dc2626;border-color:#dc2626}
.note-editor .note-actions .note-delete:hover{background:#fef2f2}
.note-editor .note-actions .note-cancel{background:#fff;color:#6b7280}
.note-editor .note-actions .note-cancel:hover{background:#f3f4f6}
.notes-toggle{position:fixed;bottom:1.5rem;z-index:201;background:#eab308;color:#fff;border:none;border-radius:50%;width:52px;height:52px;font-size:1.4rem;cursor:pointer;box-shadow:0 3px 12px rgba(234,179,8,.4);transition:transform .2s;display:flex;align-items:center;justify-content:center}
[dir="ltr"] .notes-toggle,.notes-toggle{right:5rem}
[dir="rtl"] .notes-toggle{left:5rem;right:auto}
.notes-toggle:hover{transform:scale(1.1)}
.notes-toggle .badge{position:absolute;top:-4px;right:-4px;background:#dc2626;color:#fff;border-radius:50%;width:20px;height:20px;font-size:.7rem;display:flex;align-items:center;justify-content:center;font-weight:700}
.notes-toggle .badge:empty{display:none}
.notes-panel{position:fixed;bottom:5rem;width:380px;max-height:60vh;z-index:201;background:#fff;border:1px solid #e5e7eb;border-radius:12px;box-shadow:0 8px 30px rgba(0,0,0,.15);display:none;flex-direction:column;overflow:hidden}
[dir="ltr"] .notes-panel,.notes-panel{right:5rem}
[dir="rtl"] .notes-panel{left:5rem;right:auto}
.notes-panel.open{display:flex}
.notes-panel-header{padding:.75rem 1rem;background:#fef9c3;border-bottom:1px solid #facc15;display:flex;justify-content:space-between;align-items:center;font-weight:600;font-size:.9rem}
.notes-panel-header .panel-actions{display:flex;gap:.5rem}
.notes-panel-header button{background:none;border:none;cursor:pointer;font-size:.8rem;color:#2563eb;font-weight:500;padding:.1rem .3rem}
.notes-panel-header button:hover{text-decoration:underline}
.notes-panel-header .notes-clear{color:#dc2626}
.notes-panel-toolbar{display:none;padding:.4rem .75rem;background:#fef2f2;border-bottom:1px solid #fca5a5;align-items:center;gap:.5rem;font-size:.8rem}
.notes-panel-toolbar.visible{display:flex}
.notes-panel-toolbar .del-selected{background:#dc2626;color:#fff;border:none;border-radius:5px;padding:.25rem .6rem;cursor:pointer;font-size:.78rem;font-family:inherit}
.notes-panel-toolbar .del-selected:hover{background:#b91c1c}
.notes-panel-toolbar .sel-count{color:#dc2626;font-weight:600}
.notes-panel-toolbar .select-all-btn{margin-left:auto;color:#2563eb;background:none;border:none;cursor:pointer;font-size:.78rem;font-family:inherit}
.notes-panel-body{overflow-y:auto;padding:.5rem;flex:1}
.notes-panel-item{padding:.5rem .6rem;border-radius:6px;margin-bottom:.3rem;transition:background .15s;font-size:.85rem;border:1px solid transparent;display:flex;gap:.5rem;align-items:flex-start}
.notes-panel-item:hover{background:#fef9c3;border-color:#facc15}
.notes-panel-item input[type="checkbox"]{margin-top:.25rem;flex-shrink:0;cursor:pointer;accent-color:#dc2626}
.notes-panel-item .panel-item-content{flex:1;min-width:0;cursor:pointer}
.notes-panel-item .panel-quoted{font-size:.78rem;color:#92400e;background:#fef3c7;padding:.2rem .4rem;border-radius:4px;margin-bottom:.3rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.notes-panel-item .panel-note{color:#4b5563;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.notes-panel-empty{padding:1.5rem;text-align:center;color:#9ca3af;font-size:.85rem;line-height:1.6}
.heading-note-btn{opacity:0;cursor:pointer;background:none;border:none;font-size:.85rem;padding:.15rem .3rem;border-radius:4px;transition:opacity .15s,background .15s;vertical-align:middle;margin:0 .3rem}
h1:hover .heading-note-btn,h2:hover .heading-note-btn,h3:hover .heading-note-btn,h4:hover .heading-note-btn{opacity:.5}
.heading-note-btn:hover{opacity:1!important;background:#fef3c7}
.heading-note-btn.has-note{opacity:.7;color:#eab308}
.notes-panel-item .panel-section{font-size:.72rem;color:#6366f1;font-weight:500;margin-bottom:.15rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
@keyframes noteIn{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:translateY(0)}}
@media print{mark.noted{background:#fef08a!important;-webkit-print-color-adjust:exact;print-color-adjust:exact;border:none}.note-popup,.note-editor,.notes-toggle,.notes-panel,.heading-note-btn{display:none!important}}
"""

NOTES_JS = r"""
<script>
(function(){
  var STORAGE_KEY='doc-notes:'+location.pathname;
  var content=document.querySelector('.content');
  if(!content)return;

  // ── Storage ──
  function loadNotes(){try{return JSON.parse(localStorage.getItem(STORAGE_KEY))||[]}catch(e){return []}}
  function saveNotes(arr){try{localStorage.setItem(STORAGE_KEY,JSON.stringify(arr))}catch(e){}}
  var allNotes=loadNotes();

  // ── Find line:col in original markdown source ──
  var mdSourceEl=document.getElementById('md-source');
  var mdSource=mdSourceEl?mdSourceEl.textContent:'';
  function findMdLocation(selectedText,ctxBefore,ctxAfter){
    if(!mdSource||!selectedText)return null;
    // Try with context first, then plain text
    var needle=ctxBefore+selectedText+ctxAfter;
    var idx=mdSource.indexOf(needle);
    if(idx!==-1){idx+=ctxBefore.length}
    else{idx=mdSource.indexOf(selectedText);if(idx===-1)return null}
    // Count line and column
    var before=mdSource.substring(0,idx);
    var line=before.split('\\n').length;
    var lastNl=before.lastIndexOf('\\n');
    var col=lastNl===-1?idx+1:idx-lastNl;
    return{line:line,col:col,index:idx};
  }

  // ── Text search: find a range in .content matching selectedText with context ──
  function getTextNodes(root){
    var nodes=[],walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,null,false);
    while(walker.nextNode())nodes.push(walker.currentNode);
    return nodes;
  }
  function buildTextMap(nodes){
    var text='',offsets=[];
    for(var i=0;i<nodes.length;i++){offsets.push(text.length);text+=nodes[i].nodeValue}
    return{text:text,offsets:offsets,nodes:nodes};
  }
  function findTextRange(map,selected,ctxBefore,ctxAfter){
    var needle=ctxBefore+selected+ctxAfter;
    var idx=map.text.indexOf(needle);
    if(idx===-1){idx=map.text.indexOf(selected);if(idx===-1)return null}
    else{idx+=ctxBefore.length}
    var startOff=idx,endOff=idx+selected.length;
    var startNode,startLocal,endNode,endLocal;
    for(var i=0;i<map.nodes.length;i++){
      var nStart=map.offsets[i],nEnd=nStart+map.nodes[i].nodeValue.length;
      if(startNode===undefined&&startOff<nEnd){startNode=map.nodes[i];startLocal=startOff-nStart}
      if(endOff<=nEnd){endNode=map.nodes[i];endLocal=endOff-nStart;break}
    }
    if(!startNode||!endNode)return null;
    var range=document.createRange();
    range.setStart(startNode,startLocal);
    range.setEnd(endNode,endLocal);
    return range;
  }

  // ── Highlight: wraps each text node segment individually for cross-element safety ──
  function highlightRange(range,noteId){
    var nodes=getTextNodes(content);
    var started=false,segments=[];
    // Phase 1: collect segments (no DOM mutation)
    for(var i=0;i<nodes.length;i++){
      var n=nodes[i],nLen=n.nodeValue.length;
      var segStart=0,segEnd=nLen;
      if(n===range.startContainer){started=true;segStart=range.startOffset}
      if(!started)continue;
      if(n===range.endContainer){segEnd=range.endOffset}
      if(segStart>=segEnd){if(n===range.endContainer)break;continue}
      segments.push({node:n,start:segStart,end:segEnd});
      if(n===range.endContainer)break;
    }
    // Phase 2: wrap in reverse order to preserve node positions
    var marks=[];
    for(var j=segments.length-1;j>=0;j--){
      try{
        var seg=segments[j];
        var r=document.createRange();
        r.setStart(seg.node,seg.start);
        r.setEnd(seg.node,seg.end);
        var mark=document.createElement('mark');
        mark.className='noted';
        mark.dataset.noteId=noteId;
        r.surroundContents(mark);
        marks.unshift(mark);
      }catch(e){}
    }
    return marks[0]||null;
  }

  // ── Get surrounding context from selection ──
  function getContext(rangeObj,chars){
    var tempRange=document.createRange();
    try{
      tempRange.selectNodeContents(content);
      tempRange.setEnd(rangeObj.startContainer,rangeObj.startOffset);
      var before=tempRange.toString().slice(-chars);
      tempRange.selectNodeContents(content);
      tempRange.setStart(rangeObj.endContainer,rangeObj.endOffset);
      var after=tempRange.toString().slice(0,chars);
      return{before:before,after:after};
    }catch(e){return{before:'',after:''}}
  }

  // ── Restore all saved highlights on load ──
  function restoreNotes(){
    try{
      var map=buildTextMap(getTextNodes(content));
      allNotes.forEach(function(n){
        if(n.type==='heading')return;
        var range=findTextRange(map,n.selectedText,n.ctxBefore||'',n.ctxAfter||'');
        if(range){
          highlightRange(range,n.id);
          map=buildTextMap(getTextNodes(content));
        }
      });
      document.querySelectorAll('mark.noted').forEach(function(mark){
        var nObj=allNotes.find(function(x){return x.id===mark.dataset.noteId});
        if(nObj)bindMark(mark,nObj);
      });
    }catch(e){console.warn('Note restore failed:',e)}
  }

  // ── Bind click on a <mark> to open its note editor ──
  function bindMark(mark,noteObj){
    mark.onclick=function(e){
      e.stopPropagation();
      closeAllEditors();
      // Highlight all marks for this note
      document.querySelectorAll('mark.noted[data-note-id="'+noteObj.id+'"]').forEach(function(m){m.classList.add('active')});
      var rect=mark.getBoundingClientRect();
      openEditor(rect,noteObj,noteObj.id);
    };
  }

  // ── Close any open popups/editors ──
  function closeAllEditors(){
    document.querySelectorAll('.note-popup,.note-editor').forEach(function(el){el.remove()});
    document.querySelectorAll('mark.noted.active').forEach(function(m){m.classList.remove('active')});
  }

  // ── Selection popup: appears when user selects text ──
  function showPopup(rect,selRange){
    closeAllEditors();
    var popup=document.createElement('div');
    popup.className='note-popup';
    var btn=document.createElement('button');
    btn.textContent='\uD83D\uDCDD Add Note';
    popup.appendChild(btn);
    document.body.appendChild(popup);
    var top=rect.top+window.scrollY-popup.offsetHeight-6;
    var left=rect.left+window.scrollX+(rect.width/2)-(popup.offsetWidth/2);
    popup.style.top=Math.max(0,top)+'px';
    popup.style.left=Math.max(4,left)+'px';

    btn.onclick=function(e){
      e.stopPropagation();
      popup.remove();
      var selectedText=selRange.toString();
      if(!selectedText.trim())return;
      var ctx=getContext(selRange,30);
      var heading=findNearestHeading(selRange.startContainer);
      var loc=findMdLocation(selectedText,ctx.before,ctx.after);
      var noteObj={id:Date.now().toString(36)+Math.random().toString(36).substr(2,4),type:'text',selectedText:selectedText,ctxBefore:ctx.before,ctxAfter:ctx.after,note:'',section:heading.text,sectionId:heading.id,mdLine:loc?loc.line:null,mdCol:loc?loc.col:null,mdIndex:loc?loc.index:null,createdAt:new Date().toISOString()};
      var firstMark=highlightRange(selRange,noteObj.id);
      if(!firstMark)return;
      window.getSelection().removeAllRanges();
      var markRect=firstMark.getBoundingClientRect();
      openEditor(markRect,noteObj,noteObj.id,true);
    };
  }

  // ── Note editor: positioned near the highlight ──
  function openEditor(rect,noteObj,noteId,isNew){
    var editor=document.createElement('div');
    editor.className='note-editor';
    var quoted=document.createElement('div');
    quoted.className='note-selected';
    quoted.textContent='\u201C'+noteObj.selectedText.slice(0,80)+(noteObj.selectedText.length>80?'\u2026':'')+'\u201D';
    editor.appendChild(quoted);

    var ta=document.createElement('textarea');
    ta.placeholder='Your review note\u2026';
    ta.value=noteObj.note||'';
    editor.appendChild(ta);

    var actions=document.createElement('div');
    actions.className='note-actions';
    var saveBtn=document.createElement('button');
    saveBtn.className='note-save';
    saveBtn.textContent='Save';
    var cancelBtn=document.createElement('button');
    cancelBtn.className='note-cancel';
    cancelBtn.textContent='Cancel';
    var delBtn=document.createElement('button');
    delBtn.className='note-delete';
    delBtn.textContent='Delete';

    saveBtn.onclick=function(){
      var text=ta.value.trim();
      if(!text){removeNoteById(noteId);editor.remove();return}
      noteObj.note=text;
      var idx=allNotes.findIndex(function(n){return n.id===noteObj.id});
      if(idx>=0){allNotes[idx]=noteObj}else{allNotes.push(noteObj)}
      saveNotes(allNotes);
      // Rebind all marks for this note
      document.querySelectorAll('mark.noted[data-note-id="'+noteId+'"]').forEach(function(m){
        m.classList.remove('active');
        bindMark(m,noteObj);
      });
      editor.remove();
      updateBadge();
    };
    cancelBtn.onclick=function(){
      editor.remove();
      document.querySelectorAll('mark.noted[data-note-id="'+noteId+'"]').forEach(function(m){m.classList.remove('active')});
      if(isNew)unwrapMarksById(noteId);
    };
    delBtn.onclick=function(){removeNoteById(noteId);editor.remove()};

    actions.appendChild(saveBtn);
    if(!isNew)actions.appendChild(delBtn);
    actions.appendChild(cancelBtn);
    editor.appendChild(actions);
    document.body.appendChild(editor);

    var top=rect.bottom+window.scrollY+6;
    var left=rect.left+window.scrollX;
    if(left+320>window.innerWidth)left=window.innerWidth-330;
    if(left<4)left=4;
    editor.style.top=top+'px';
    editor.style.left=left+'px';
    ta.focus();
  }

  function removeNoteById(id){
    allNotes=allNotes.filter(function(n){return n.id!==id});
    saveNotes(allNotes);
    unwrapMarksById(id);
    updateBadge();
  }

  function unwrapMarksById(id){
    document.querySelectorAll('mark.noted[data-note-id="'+id+'"]').forEach(unwrapMark);
  }

  function unwrapMark(mark){
    var parent=mark.parentNode;
    if(!parent)return;
    while(mark.firstChild)parent.insertBefore(mark.firstChild,mark);
    parent.removeChild(mark);
    parent.normalize();
  }

  // ── Listen for text selection in .content (works on paragraphs, tables, lists, headings, etc.) ──
  var popupTimeout;
  document.addEventListener('mouseup',function(e){
    if(e.target.closest&&e.target.closest('.note-popup,.note-editor,.notes-panel'))return;
    clearTimeout(popupTimeout);
    popupTimeout=setTimeout(function(){
      var sel=window.getSelection();
      if(!sel||sel.isCollapsed||!sel.rangeCount)return;
      var range=sel.getRangeAt(0);
      // Must be within .content — handles all elements: p, td, th, li, h1-h4, blockquote, etc.
      var ancestor=range.commonAncestorContainer;
      if(ancestor.nodeType===3)ancestor=ancestor.parentNode;
      if(!content.contains(ancestor))return;
      if(range.toString().trim().length<1)return;
      var rect=range.getBoundingClientRect();
      showPopup(rect,range.cloneRange());
    },200);
  });

  document.addEventListener('mousedown',function(e){
    if(e.target.closest&&!e.target.closest('.note-popup,.note-editor,.notes-panel,.notes-toggle,mark.noted')){
      closeAllEditors();
    }
  });

  // ── Floating toggle button + notes panel ──
  var toggleBtn=document.createElement('button');
  toggleBtn.className='notes-toggle';
  toggleBtn.textContent='\uD83D\uDCDD';
  toggleBtn.title='Review notes';
  var badge=document.createElement('span');
  badge.className='badge';
  toggleBtn.appendChild(badge);
  document.body.appendChild(toggleBtn);

  var panel=document.createElement('div');
  panel.className='notes-panel';
  // Header
  var panelHeader=document.createElement('div');
  panelHeader.className='notes-panel-header';
  var headerLabel=document.createElement('span');
  headerLabel.textContent='Review Notes';
  panelHeader.appendChild(headerLabel);
  var panelActions=document.createElement('div');
  panelActions.className='panel-actions';
  var exportBtn=document.createElement('button');
  exportBtn.textContent='Export MD';
  exportBtn.onclick=exportNotes;
  panelActions.appendChild(exportBtn);
  var clearBtn=document.createElement('button');
  clearBtn.className='notes-clear';
  clearBtn.textContent='Clear All';
  clearBtn.onclick=function(){
    if(!confirm('Remove all notes from this page?'))return;
    allNotes=[];saveNotes(allNotes);
    document.querySelectorAll('mark.noted').forEach(unwrapMark);
    updateBadge();renderPanel();
  };
  panelActions.appendChild(clearBtn);
  panelHeader.appendChild(panelActions);
  panel.appendChild(panelHeader);
  // Selection toolbar
  var toolbar=document.createElement('div');
  toolbar.className='notes-panel-toolbar';
  var selCount=document.createElement('span');
  selCount.className='sel-count';
  toolbar.appendChild(selCount);
  var delSelBtn=document.createElement('button');
  delSelBtn.className='del-selected';
  delSelBtn.textContent='Delete Selected';
  delSelBtn.onclick=function(){
    var checks=panelBody.querySelectorAll('input[type="checkbox"]:checked');
    if(!checks.length)return;
    var ids=[];
    checks.forEach(function(cb){ids.push(cb.dataset.noteId)});
    ids.forEach(function(id){
      allNotes=allNotes.filter(function(n){return n.id!==id});
      unwrapMarksById(id);
    });
    saveNotes(allNotes);updateBadge();renderPanel();
  };
  toolbar.appendChild(delSelBtn);
  var selectAllBtn=document.createElement('button');
  selectAllBtn.className='select-all-btn';
  selectAllBtn.textContent='Select All';
  selectAllBtn.onclick=function(){
    var checks=panelBody.querySelectorAll('input[type="checkbox"]');
    var allChecked=true;
    checks.forEach(function(cb){if(!cb.checked)allChecked=false});
    checks.forEach(function(cb){cb.checked=!allChecked;cb.dispatchEvent(new Event('change'))});
  };
  toolbar.appendChild(selectAllBtn);
  panel.appendChild(toolbar);
  // Body
  var panelBody=document.createElement('div');
  panelBody.className='notes-panel-body';
  panel.appendChild(panelBody);
  document.body.appendChild(panel);

  toggleBtn.onclick=function(e){
    e.stopPropagation();
    panel.classList.toggle('open');
    if(panel.classList.contains('open'))renderPanel();
  };

  function updateToolbar(){
    var checks=panelBody.querySelectorAll('input[type="checkbox"]:checked');
    var count=checks.length;
    if(count>0){
      toolbar.classList.add('visible');
      selCount.textContent=count+' selected';
    }else{
      toolbar.classList.remove('visible');
    }
  }

  function updateBadge(){
    badge.textContent=allNotes.length||'';
    updateHeadingButtons();
  }

  function renderPanel(){
    allNotes=loadNotes();
    panelBody.textContent='';
    toolbar.classList.remove('visible');
    if(!allNotes.length){
      var empty=document.createElement('div');
      empty.className='notes-panel-empty';
      empty.textContent='No notes yet.\nSelect any text and click the note icon to annotate.';
      panelBody.appendChild(empty);
      return;
    }
    allNotes.forEach(function(n){
      var item=document.createElement('div');
      item.className='notes-panel-item';
      var cb=document.createElement('input');
      cb.type='checkbox';
      cb.dataset.noteId=n.id;
      cb.onchange=updateToolbar;
      item.appendChild(cb);
      var itemContent=document.createElement('div');
      itemContent.className='panel-item-content';
      // Show section context
      var sectionLabel=n.type==='heading'?n.headingText:(n.section||'');
      if(sectionLabel){
        var sec=document.createElement('div');
        sec.className='panel-section';
        sec.textContent=(n.type==='heading'?'\uD83D\uDCCC ':'\u00A7 ')+sectionLabel;
        itemContent.appendChild(sec);
      }
      var q=document.createElement('div');
      q.className='panel-quoted';
      q.textContent='\u201C'+n.selectedText.slice(0,60)+(n.selectedText.length>60?'\u2026':'')+'\u201D';
      itemContent.appendChild(q);
      var t=document.createElement('div');
      t.className='panel-note';
      t.textContent=n.note.split('\n')[0];
      itemContent.appendChild(t);
      itemContent.onclick=function(){
        panel.classList.remove('open');
        var mark=document.querySelector('mark.noted[data-note-id="'+n.id+'"]');
        if(mark){
          mark.scrollIntoView({behavior:'smooth',block:'center'});
          mark.classList.add('active');
          setTimeout(function(){mark.click()},400);
        }
      };
      item.appendChild(itemContent);
      panelBody.appendChild(item);
    });
  }

  function exportNotes(){
    var notes=loadNotes();
    var lines=['# Review Notes','','**Document:** '+document.title,'**Date:** '+new Date().toLocaleDateString(),''];
    // Group notes by section
    var sections={};var order=[];
    notes.forEach(function(n){
      var sec=n.type==='heading'?(n.headingText||'General'):(n.section||'General');
      if(!sections[sec]){sections[sec]=[];order.push(sec)}
      sections[sec].push(n);
    });
    order.forEach(function(sec){
      if(sec!=='General'){
        lines.push('---');
        lines.push('');
        lines.push('## '+sec);
        lines.push('');
      }
      sections[sec].forEach(function(n){
        if(n.type==='heading'){
          lines.push('**[Section note]**');
        }else{
          var ref=n.mdLine?(' *(line '+n.mdLine+', col '+n.mdCol+')*'):'';
          lines.push('> '+n.selectedText.replace(/\n/g,'\n> ')+ref);
        }
        lines.push('');
        lines.push(n.note);
        lines.push('');
      });
    });
    var blob=new Blob([lines.join('\n')],{type:'text/markdown'});
    var a=document.createElement('a');
    a.href=URL.createObjectURL(blob);
    a.download='review-notes-'+document.title.replace(/[^a-z0-9]+/gi,'-').toLowerCase()+'.md';
    a.click();
    URL.revokeObjectURL(a.href);
  }

  // ── Find nearest heading above a DOM node ──
  function findNearestHeading(node){
    var el=node.nodeType===3?node.parentNode:node;
    // Walk backwards through preceding siblings and parents to find h1-h4
    while(el&&content.contains(el)){
      // Check preceding siblings
      var sib=el.previousElementSibling;
      while(sib){
        if(/^H[1-4]$/i.test(sib.tagName))return{id:sib.id||'',text:sib.textContent.replace(/\uD83D\uDCDD/g,'').trim()};
        sib=sib.previousElementSibling;
      }
      // Check if el itself is a heading
      if(/^H[1-4]$/i.test(el.tagName))return{id:el.id||'',text:el.textContent.replace(/\uD83D\uDCDD/g,'').trim()};
      el=el.parentNode;
    }
    return{id:'',text:''};
  }

  // ── Add note buttons to all headings ──
  function addHeadingButtons(){
    content.querySelectorAll('h1,h2,h3,h4').forEach(function(h){
      if(h.querySelector('.heading-note-btn'))return;
      var btn=document.createElement('button');
      btn.className='heading-note-btn';
      btn.textContent='\uD83D\uDCDD';
      btn.title='Add note to this section';
      // Check if heading already has a note
      var hText=h.textContent.trim();
      var existing=allNotes.find(function(n){return n.type==='heading'&&n.headingId===h.id});
      if(existing)btn.classList.add('has-note');
      btn.onclick=function(e){
        e.stopPropagation();
        e.preventDefault();
        closeAllEditors();
        var headingText=h.textContent.replace(/\uD83D\uDCDD/g,'').trim();
        // Check if note exists for this heading
        var existingNote=allNotes.find(function(n){return n.type==='heading'&&n.headingId===h.id});
        if(existingNote){
          var rect=h.getBoundingClientRect();
          openEditor(rect,existingNote,existingNote.id);
        }else{
          var noteObj={id:Date.now().toString(36)+Math.random().toString(36).substr(2,4),type:'heading',headingId:h.id,headingText:headingText,selectedText:headingText,ctxBefore:'',ctxAfter:'',note:'',createdAt:new Date().toISOString()};
          var rect=h.getBoundingClientRect();
          openEditor(rect,noteObj,noteObj.id,true);
        }
      };
      h.appendChild(btn);
    });
  }

  // ── Update heading button states ──
  function updateHeadingButtons(){
    content.querySelectorAll('.heading-note-btn').forEach(function(btn){
      var h=btn.parentNode;
      var existing=allNotes.find(function(n){return n.type==='heading'&&n.headingId===h.id});
      if(existing)btn.classList.add('has-note');
      else btn.classList.remove('has-note');
    });
  }

  // ── Init ──
  restoreNotes();
  addHeadingButtons();
  updateBadge();
})();
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
                # Merge color preset if colorScheme is set
                scheme = result.get('colorScheme', '')
                if scheme in COLOR_PRESETS:
                    preset = COLOR_PRESETS[scheme]
                    for k, v in preset.items():
                        if k not in cfg:
                            result[k] = v
                found_config = True
                return result
            except (json.JSONDecodeError, OSError):
                break
        parent = d.parent
        if parent == d:
            break
        d = parent
    # No config found — use folder name as project name (not document title)
    start = Path(start_dir).resolve()
    folder_name = start.name or 'Docs'
    defaults['projectName'] = folder_name
    defaults['logoText'] = folder_name[:2]
    return defaults


# ─── Templates ────────────────────────────────────────────────────────────────

UNIFIED_TEMPLATE = """\
<!DOCTYPE html>
<html lang="{{LANG}}" dir="{{DIR}}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{TITLE}}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Heebo:wght@400;500;600;700&family=Rubik:wght@400;500;600;700&family=Assistant:wght@400;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" id="hljs-dark" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/vs2015.min.css">
<link rel="stylesheet" id="hljs-light" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/vs.min.css" disabled>
<style>
:root{--bg:#f8f9fa;--surface:#fff;--text:#1a1a2e;--muted:#6b7280;--accent:#2563eb;--accent-light:#dbeafe;--border:#e5e7eb;--code-bg:#1E1E1E;--code-text:#d4d4d4;--radius:8px;--header-from:#1e3a5f;--header-to:#2563eb}
[dir="rtl"]{--code-bg:#f5f5f5;--code-text:#1a1a2e}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',system-ui,sans-serif;background:var(--bg);color:var(--text);line-height:1.7}
[dir="rtl"] body{font-family:'Heebo','Rubik','Assistant',system-ui,sans-serif;line-height:1.8}

/* ── Header ── */
.site-header{position:sticky;top:0;z-index:50;background:linear-gradient(135deg,var(--header-from),var(--header-to));color:#fff;padding:.75rem 2rem;display:flex;align-items:center;gap:1rem;box-shadow:0 2px 8px rgba(0,0,0,.15)}
.logo-circle{width:40px;height:40px;border-radius:12px;background:rgba(255,255,255,.15);backdrop-filter:blur(8px);border:1px solid rgba(255,255,255,.25);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:1.1rem;flex-shrink:0;box-shadow:0 2px 8px rgba(0,0,0,.1)}
.site-header .header-text h1{font-size:1rem;font-weight:600;margin:0;line-height:1.3}
.site-header .header-text .org{font-size:.75rem;opacity:.8;margin:0}
.doc-title{font-size:1rem;font-weight:500;opacity:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:45vw;transition:opacity .25s;pointer-events:none}
.doc-title.visible{opacity:.9;pointer-events:auto}
.doc-title::before{content:'\\2022';margin:0 .6rem;opacity:.4}
.header-right{margin-left:auto;display:flex;align-items:center;gap:.5rem;flex-shrink:0}
[dir="rtl"] .header-right{margin-left:0;margin-right:auto}
.header-index{color:rgba(255,255,255,.9);text-decoration:none;font-size:.7rem;font-weight:500;padding:.3rem .7rem;border-radius:6px;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.15);transition:all .15s;white-space:nowrap;display:flex;align-items:center;gap:.3rem}
.header-index:hover{background:rgba(255,255,255,.22);color:#fff;border-color:rgba(255,255,255,.3)}
.header-index svg{width:14px;height:14px;opacity:.7;flex-shrink:0}
[dir="rtl"] .header-index svg{transform:scaleX(-1)}
.org:empty{display:none}
.header-home{display:flex;align-items:center;gap:1rem;text-decoration:none;color:inherit;transition:opacity .15s}
.header-home:hover{opacity:.85}

/* ── Layout ── */
.page{display:grid;grid-template-columns:280px 1fr;max-width:1300px;margin:0 auto;min-height:calc(100vh - 56px)}

/* ── Sidebar ── */
.sidebar{position:sticky;top:56px;height:calc(100vh - 56px);overflow-y:auto;padding:1rem .75rem;background:var(--surface);border-right:1px solid var(--border)}
[dir="rtl"] .sidebar{border-right:none;border-left:1px solid var(--border)}
.sidebar-card{background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);padding:.75rem;margin-bottom:1rem}
.sidebar-card h3{font-size:.65rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin-bottom:.5rem;font-weight:600;padding:0 .5rem}
.sidebar a{display:block;padding:.25rem .5rem;color:var(--text);text-decoration:none;font-size:.8rem;line-height:1.4;border-left:2px solid transparent;margin-bottom:1px;border-radius:0 4px 4px 0;transition:all .15s}
.sidebar a:hover{color:var(--accent);border-left-color:var(--accent);background:var(--accent-light)}
.sidebar a.toc-active{color:var(--accent);border-left-color:var(--accent);background:var(--accent-light);font-weight:600}
.sidebar a.h3-link{padding-left:1.5rem;font-size:.75rem;color:var(--muted)}
[dir="rtl"] .sidebar a{border-left:none;border-right:2px solid transparent;border-radius:4px 0 0 4px}
[dir="rtl"] .sidebar a:hover{border-left-color:transparent;border-right-color:var(--accent)}
[dir="rtl"] .sidebar a.toc-active{border-left-color:transparent;border-right-color:var(--accent)}
[dir="rtl"] .sidebar a.h3-link{padding-left:0;padding-right:1.5rem}
/* ── Collapsible TOC ── */
.sidebar details{margin-bottom:1px}
.sidebar details summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:.25rem;padding:.25rem .5rem;border-radius:0 4px 4px 0;transition:background .15s}
.sidebar details summary:hover{background:var(--accent-light)}
.sidebar details summary::-webkit-details-marker{display:none}
.sidebar details summary::before{content:'';display:block;width:0;height:0;border-top:4px solid transparent;border-bottom:4px solid transparent;border-left:5px solid var(--muted);flex-shrink:0;transition:transform .15s}
.sidebar details[open] summary::before{transform:rotate(90deg)}
.sidebar details summary::after{display:none}
.sidebar details summary a{display:block;flex:1;padding:0;margin:0;border:none;border-radius:0}
.sidebar details summary a:hover{background:none}
.sidebar details .h3-link{padding-left:1.5rem}
[dir="rtl"] .sidebar details summary{flex-direction:row-reverse;border-radius:4px 0 0 4px}
[dir="rtl"] .sidebar details summary::before{display:none}
[dir="rtl"] .sidebar details summary::after{content:'';display:block;width:0;height:0;border-top:4px solid transparent;border-bottom:4px solid transparent;border-right:5px solid var(--muted);flex-shrink:0;transition:transform .15s}
[dir="rtl"] .sidebar details[open] summary::after{transform:rotate(-90deg)}
[dir="rtl"] .sidebar details .h3-link{padding-left:0;padding-right:1.5rem}
/* ── Layout switcher ── */
.layout-toolbar{display:flex;gap:1px;align-items:center;background:rgba(255,255,255,.08);border-radius:6px;border:1px solid rgba(255,255,255,.15);overflow:hidden}
.layout-toolbar button{background:none;border:none;border-radius:0;padding:.3rem .5rem;font-size:.65rem;cursor:pointer;color:rgba(255,255,255,.7);transition:all .15s;font-weight:500}
.layout-toolbar button:hover{background:rgba(255,255,255,.12);color:rgba(255,255,255,.95)}
.layout-toolbar button.active{background:rgba(255,255,255,.2);color:#fff}
/* ── Direction toggle ── */
.dir-toggle{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.15);border-radius:6px;padding:.3rem .55rem;font-size:.65rem;cursor:pointer;color:rgba(255,255,255,.9);transition:all .15s;font-weight:600;letter-spacing:.02em}
.dir-toggle:hover{background:rgba(255,255,255,.22);color:#fff;border-color:rgba(255,255,255,.3)}
.page.layout-narrow .content{max-width:860px}
.page.layout-wide .content{max-width:1200px}
.page.layout-wide{max-width:1600px}
.page.layout-fluid{max-width:100%;margin:0;padding:0;display:block}
.page.layout-fluid .sidebar{position:fixed;top:56px;left:0;width:280px;height:calc(100vh - 56px);z-index:10}
.page.layout-fluid .content{max-width:100%;margin-left:280px;padding:2.5rem 3rem}
[dir="rtl"] .page.layout-fluid .sidebar{left:auto;right:0}
[dir="rtl"] .page.layout-fluid .content{margin-left:0;margin-right:280px}

/* ── Mobile TOC toggle ── */
.toc-toggle{display:none;position:fixed;bottom:1.5rem;right:1.5rem;z-index:100;background:var(--accent);color:#fff;border:none;border-radius:50%;width:48px;height:48px;font-size:1.3rem;cursor:pointer;box-shadow:0 3px 12px rgba(37,99,235,.4);transition:transform .2s}
.toc-toggle:hover{transform:scale(1.1)}
[dir="rtl"] .toc-toggle{right:auto;left:1.5rem}

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
ul.checklist{list-style:none;padding-left:0}
ul.checklist li{display:flex;align-items:baseline;gap:.4rem;padding:.25rem 0}
blockquote{border-left:3px solid var(--accent);padding:.75rem 1rem;margin:1rem 0;background:var(--accent-light);border-radius:0 var(--radius) var(--radius) 0}
.warning-box{border-left:4px solid #f59e0b;background:#fffbeb;padding:1rem;border-radius:0 var(--radius) var(--radius) 0;margin:1rem 0}
[dir="rtl"] ul,[dir="rtl"] ol{margin-left:0;padding-right:1.5rem}
[dir="rtl"] li input[type="checkbox"]{margin-right:0;margin-left:.4rem}
[dir="rtl"] ul.checklist{padding-right:0}
[dir="rtl"] blockquote{border-left:none;border-right:3px solid var(--accent);border-radius:var(--radius) 0 0 var(--radius)}
[dir="rtl"] .warning-box{border-left:none;border-right:4px solid #f59e0b;border-radius:var(--radius) 0 0 var(--radius)}

/* ── Code ── */
pre{background:var(--code-bg);color:var(--code-text);padding:1.15rem 1.25rem;border-radius:var(--radius);overflow-x:auto;margin:1rem 0;font-size:.85rem;box-shadow:inset 0 1px 3px rgba(0,0,0,.2)}
code{font-family:'JetBrains Mono',monospace;font-size:.85em}
p code,li code{background:#e8eaed;color:#c7254e;padding:.15rem .4rem;border-radius:4px}
pre code{background:transparent;color:inherit;padding:0}
[dir="rtl"] pre{direction:ltr;text-align:left;box-shadow:none;border:1px solid var(--border)}
[dir="rtl"] code{direction:ltr}

/* ── Tables ── */
table{width:100%;border-collapse:collapse;margin:1rem 0;font-size:.9rem}
th,td{border:1px solid var(--border);padding:.6rem .8rem;text-align:left}
th{background:var(--accent);color:#fff;font-weight:600}
tr:nth-child(even){background:#f5f6f8}
[dir="rtl"] th,[dir="rtl"] td{text-align:right}

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
{{NOTES_CSS}}
</style>
</head>
<body>
<header class="site-header">
  <a href="index.html" class="header-home">
    <div class="logo-circle">{{LOGO_TEXT}}</div>
    <div class="header-text">
      <h1>{{PROJECT_NAME}}</h1>
      <div class="org">{{ORG_NAME}}</div>
    </div>
  </a>
  <span class="doc-title">{{TITLE}}</span>
  <div class="header-right">
    <a href="index.html" class="header-index"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 12H5"/><polyline points="12 19 5 12 12 5"/></svg><span data-ltr="Back to Index" data-rtl="&#1495;&#1494;&#1512;&#1492; &#1500;&#1488;&#1497;&#1504;&#1491;&#1511;&#1505;">{{INDEX_LABEL}}</span></a>
    <button class="dir-toggle" onclick="toggleDir()" id="btn-dir">{{DIR_LABEL}}</button>
    <div class="layout-toolbar">
      <button onclick="setLayout('narrow')" id="btn-narrow" data-ltr="Narrow" data-rtl="&#1510;&#1512;">{{NARROW_LABEL}}</button>
      <button onclick="setLayout('wide')" id="btn-wide" data-ltr="Wide" data-rtl="&#1512;&#1495;&#1489;">{{WIDE_LABEL}}</button>
      <button onclick="setLayout('fluid')" id="btn-fluid" data-ltr="Full" data-rtl="&#1502;&#1500;&#1488;">{{FULL_LABEL}}</button>
    </div>
  </div>
</header>
<div class="page">
<nav class="sidebar" id="sidebar">
  <div class="sidebar-card">
    <h3 data-ltr="Contents" data-rtl="&#1514;&#1493;&#1499;&#1503; &#1506;&#1504;&#1497;&#1497;&#1504;&#1497;&#1501;">{{TOC_LABEL}}</h3>
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
<script type="text/plain" id="md-source">{{MD_SOURCE}}</script>
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
/* ── Direction toggle ── */
function toggleDir(){
  var html=document.documentElement;
  var newDir=html.dir==='rtl'?'ltr':'rtl';
  html.dir=newDir;
  html.lang=newDir==='rtl'?'he':'en';
  document.querySelectorAll('[data-ltr][data-rtl]').forEach(function(el){
    el.textContent=newDir==='rtl'?el.dataset.rtl:el.dataset.ltr;
  });
  document.getElementById('hljs-dark').disabled=(newDir==='rtl');
  document.getElementById('hljs-light').disabled=(newDir!=='rtl');
  document.getElementById('btn-dir').textContent=newDir==='rtl'?'LTR':'RTL';
  try{localStorage.setItem('doc-dir',newDir)}catch(e){}
}
(function(){
  var saved=localStorage.getItem('doc-dir');
  if(saved&&saved!==document.documentElement.dir){
    document.documentElement.dir=saved;
    document.documentElement.lang=saved==='rtl'?'he':'en';
    document.querySelectorAll('[data-ltr][data-rtl]').forEach(function(el){
      el.textContent=saved==='rtl'?el.dataset.rtl:el.dataset.ltr;
    });
    document.getElementById('btn-dir').textContent=saved==='rtl'?'LTR':'RTL';
  }
  var dir=document.documentElement.dir||'ltr';
  document.getElementById('hljs-dark').disabled=(dir==='rtl');
  document.getElementById('hljs-light').disabled=(dir!=='rtl');
})();
/* ── Layout switcher ── */
function setLayout(mode){
  var page=document.querySelector('.page');
  page.classList.remove('layout-narrow','layout-wide','layout-fluid');
  page.classList.add('layout-'+mode);
  document.querySelectorAll('.layout-toolbar button').forEach(function(b){b.classList.remove('active')});
  document.getElementById('btn-'+mode).classList.add('active');
  try{localStorage.setItem('doc-layout',mode)}catch(e){}
}
(function(){var m=localStorage.getItem('doc-layout')||'narrow';setLayout(m)})();
(function(){
  var dt=document.querySelector('.doc-title');
  var h1=document.querySelector('.doc-header h1');
  if(!dt||!h1)return;
  var obs=new IntersectionObserver(function(entries){
    dt.classList.toggle('visible',!entries[0].isIntersecting);
  },{threshold:0,rootMargin:'-56px 0px 0px 0px'});
  obs.observe(h1);
})();
</script>
<script>
(function(){
  var headings=document.querySelectorAll('.content h2[id], .content h3[id], .content h4[id]');
  if(!headings.length)return;
  var sidebar=document.getElementById('sidebar');
  if(!sidebar)return;
  var tocLinks=sidebar.querySelectorAll('a[href^="#"]');
  var linkMap={};
  tocLinks.forEach(function(a){linkMap[a.getAttribute('href').slice(1)]=a});
  var current=null;
  var observer=new IntersectionObserver(function(entries){
    entries.forEach(function(entry){
      if(entry.isIntersecting){
        if(current)current.classList.remove('toc-active');
        var link=linkMap[entry.target.id];
        if(link){link.classList.add('toc-active');current=link;
          var det=link.closest('details');
          if(det)det.open=true;
          link.scrollIntoView({block:'nearest',behavior:'smooth'});
        }
      }
    });
  },{rootMargin:'-80px 0px -60% 0px',threshold:0});
  headings.forEach(function(h){observer.observe(h)});
})();
</script>
<script type="module">
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
mermaid.initialize({startOnLoad:true,theme:document.documentElement.dir==='rtl'?'default':'dark'});
</script>
{{DIAGRAM_SCRIPTS}}
{{NOTES_JS}}
</body>
</html>
"""


INDEX_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script>if(location.pathname.slice(-1)!=='/'&&!location.pathname.match(/\\.html?$/i))location.replace(location.pathname+'/'+location.search+location.hash);</script>
<title>{{TITLE}}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f8f9fb;color:#1a1a2e;min-height:100vh}
.header{background:linear-gradient(135deg,{{HEADER_FROM}} 0%,{{HEADER_TO}} 100%);color:#fff;padding:2.5rem 2rem 2rem;position:relative;overflow:hidden}
.header::after{content:'';position:absolute;bottom:0;left:0;right:0;height:60px;background:linear-gradient(to bottom right,transparent 49.5%,#f8f9fb 50%)}
.header-inner{max-width:900px;margin:0 auto;display:flex;align-items:center;gap:1.25rem;position:relative;z-index:1}
.header-logo{width:52px;height:52px;background:rgba(255,255,255,.15);backdrop-filter:blur(8px);border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:22px;color:#fff;font-weight:700;flex-shrink:0;border:1px solid rgba(255,255,255,.2)}
.header-text h1{font-size:24px;font-weight:700;letter-spacing:-.02em}
.header-text p{font-size:14px;opacity:.8;margin-top:.15rem}
.container{max-width:900px;margin:0 auto;padding:1.5rem 2rem 2rem}
.section-label{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:#6b7280;margin-bottom:.75rem}
.section-grid{display:grid;grid-template-columns:1fr;gap:.5rem}
.section-card{background:#fff;border-radius:10px;border:1px solid #e5e7eb;text-decoration:none;color:inherit;display:flex;align-items:stretch;transition:all .15s ease;position:relative;overflow:hidden}
.section-card:hover{border-color:#c7d2fe;box-shadow:0 2px 12px rgba(99,102,241,.1);transform:translateX(2px)}
.card-stripe{width:4px;flex-shrink:0;border-radius:4px 0 0 4px}
.card-stripe.blue{background:#6366f1}
.card-stripe.green{background:#10b981}
.card-stripe.purple{background:#a855f7}
.card-body{padding:.875rem 1rem;flex:1;min-width:0;display:flex;align-items:center;gap:1rem}
.card-info{flex:1;min-width:0}
.card-info h2{font-size:15px;font-weight:600;margin-bottom:.15rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.card-info p{font-size:13px;color:#6b7280;line-height:1.5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.card-badges{display:flex;gap:.4rem;flex-shrink:0;align-items:center}
.card-badge{font-size:10px;font-weight:500;padding:.2rem .5rem;border-radius:6px;white-space:nowrap}
.card-badge.lang-he{background:#ecfdf5;color:#059669}
.card-badge.lang-en{background:#eef2ff;color:#4f46e5}
.card-badge.folder{background:#fef3c7;color:#b45309}
.card-icon{font-size:22px;flex-shrink:0;line-height:1}
.card-arrow{color:#d1d5db;font-size:14px;flex-shrink:0;transition:color .15s}
.section-card:hover .card-arrow{color:#6366f1}
.footer{text-align:center;padding:2rem;color:#9ca3af;font-size:12px;margin-top:1rem}
@media(max-width:480px){.header-inner{flex-direction:column;text-align:center}.container{padding:1rem}.card-badges{display:none}}
</style>
</head>
<body>
<header class="header">
  <div class="header-inner">
    <div class="header-logo">{{LOGO_TEXT}}</div>
    <div class="header-text">
      <h1>{{PROJECT_NAME}}</h1>
      {{ORG_HTML}}
    </div>
  </div>
</header>
<div class="container">
<div class="section-label">{{SUBTITLE}}</div>
<div class="section-grid">
{{CONTENT}}
</div>
</div>
<div class="footer">{{FOOTER_TEXT}} &mdash; {{GENERATION_DATE}}</div>
</body>
</html>
"""


INDEX_RTL_TEMPLATE = """\
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script>if(location.pathname.slice(-1)!=='/'&&!location.pathname.match(/\\.html?$/i))location.replace(location.pathname+'/'+location.search+location.hash);</script>
<title>{{TITLE}}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;500;600;700&family=Rubik:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Heebo','Rubik',system-ui,sans-serif;background:#f8f9fb;color:#1a1a2e;min-height:100vh;direction:rtl}
.header{background:linear-gradient(135deg,{{HEADER_FROM}} 0%,{{HEADER_TO}} 100%);color:#fff;padding:2.5rem 2rem 2rem;position:relative;overflow:hidden}
.header::after{content:'';position:absolute;bottom:0;left:0;right:0;height:60px;background:linear-gradient(to bottom left,transparent 49.5%,#f8f9fb 50%)}
.header-inner{max-width:900px;margin:0 auto;display:flex;align-items:center;gap:1.25rem;position:relative;z-index:1}
.header-logo{width:52px;height:52px;background:rgba(255,255,255,.15);backdrop-filter:blur(8px);border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:22px;color:#fff;font-weight:700;flex-shrink:0;border:1px solid rgba(255,255,255,.2)}
.header-text h1{font-size:24px;font-weight:700;letter-spacing:-.01em}
.header-text p{font-size:14px;opacity:.8;margin-top:.15rem}
.container{max-width:900px;margin:0 auto;padding:1.5rem 2rem 2rem}
.section-label{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.08em;color:#6b7280;margin-bottom:.75rem}
.section-grid{display:grid;grid-template-columns:1fr;gap:.5rem}
.section-card{background:#fff;border-radius:10px;border:1px solid #e5e7eb;text-decoration:none;color:inherit;display:flex;align-items:stretch;transition:all .15s ease;position:relative;overflow:hidden;flex-direction:row-reverse}
.section-card:hover{border-color:#c7d2fe;box-shadow:0 2px 12px rgba(99,102,241,.1);transform:translateX(-2px)}
.card-stripe{width:4px;flex-shrink:0;border-radius:0 4px 4px 0}
.card-stripe.blue{background:#6366f1}
.card-stripe.green{background:#10b981}
.card-stripe.purple{background:#a855f7}
.card-body{padding:.875rem 1rem;flex:1;min-width:0;display:flex;align-items:center;gap:1rem}
.card-info{flex:1;min-width:0}
.card-info h2{font-size:15px;font-weight:600;margin-bottom:.15rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.card-info p{font-size:13px;color:#6b7280;line-height:1.5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.card-badges{display:flex;gap:.4rem;flex-shrink:0;align-items:center}
.card-badge{font-size:10px;font-weight:500;padding:.2rem .5rem;border-radius:6px;white-space:nowrap}
.card-badge.lang-he{background:#ecfdf5;color:#059669}
.card-badge.lang-en{background:#eef2ff;color:#4f46e5}
.card-badge.folder{background:#fef3c7;color:#b45309}
.card-icon{font-size:22px;flex-shrink:0;line-height:1}
.card-arrow{color:#d1d5db;font-size:14px;flex-shrink:0;transition:color .15s}
.section-card:hover .card-arrow{color:#6366f1}
.footer{text-align:center;padding:2rem;color:#9ca3af;font-size:12px;margin-top:1rem}
@media(max-width:480px){.header-inner{flex-direction:column;text-align:center}.container{padding:1rem}.card-badges{display:none}}
</style>
</head>
<body>
<header class="header">
  <div class="header-inner">
    <div class="header-logo">{{LOGO_TEXT}}</div>
    <div class="header-text">
      <h1>{{PROJECT_NAME}}</h1>
      {{ORG_HTML}}
    </div>
  </div>
</header>
<div class="container">
<div class="section-label">{{SUBTITLE}}</div>
<div class="section-grid">
{{CONTENT}}
</div>
</div>
<div class="footer">{{FOOTER_TEXT}} &mdash; {{GENERATION_DATE}}</div>
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
    first_h1_skipped = False
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
        # Links: [text](url) — rewrite local .md links to .html
        def _rewrite_link(m):
            label, url = m.group(1), m.group(2)
            # Split anchor: foo.md#section → foo.html#section
            if not url.startswith(('http://', 'https://', 'mailto:', '#')):
                url = re.sub(r'\.md(#|$)', r'.html\1', url)
            return f'<a href="{url}">{label}</a>'
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', _rewrite_link, text)
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
            # Skip first h1 — it's rendered in the doc-header template
            if level == 1 and not first_h1_skipped:
                first_h1_skipped = True
                i += 1
                continue
            # Skip "Table of Contents" headings — sidebar handles TOC
            toc_names = {'table of contents', 'תוכן עניינים', 'toc'}
            if text.strip().lower() in toc_names:
                i += 1
                continue
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
                # Detect checkbox list: peek if first item starts with [ ] or [x]
                is_checklist = bool(re.match(r'^\[[ xX]\]', m.group(2)))
                cls = ' class="checklist"' if is_checklist else ''
                out.append(f'<ul{cls}>')
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

def parse_frontmatter(md: str) -> tuple:
    """Parse optional YAML frontmatter from markdown.

    Returns (frontmatter_dict, body_without_frontmatter).
    Supported fields: title, description, icon, accent, order.
    """
    fm = {}
    body = md
    if md.startswith('---'):
        end = md.find('\n---', 3)
        if end != -1:
            yaml_block = md[3:end].strip()
            body = md[end + 4:].lstrip('\n')
            for line in yaml_block.split('\n'):
                m = re.match(r'^(\w+)\s*:\s*(.+)$', line)
                if m:
                    fm[m.group(1).strip()] = m.group(2).strip().strip('"').strip("'")
    return fm, body


def strip_md(text: str) -> str:
    """Strip markdown formatting from text (bold, italic, links, images, code)."""
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', text)  # images
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)   # links
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)           # bold
    text = re.sub(r'__(.+?)__', r'\1', text)                # bold alt
    text = re.sub(r'\*(.+?)\*', r'\1', text)                # italic
    text = re.sub(r'_(.+?)_', r'\1', text)                  # italic alt
    text = re.sub(r'`(.+?)`', r'\1', text)                  # inline code
    text = re.sub(r'^#+\s+', '', text)                       # heading markers
    return text.strip()


def extract_metadata(md: str) -> tuple:
    """Extract title, subtitle, and frontmatter from markdown.

    Returns (title, subtitle, frontmatter_dict).
    Frontmatter fields (title, description) override auto-extraction.
    """
    fm, body = parse_frontmatter(md)

    title = fm.get('title', '')
    subtitle = fm.get('description', '')

    # Auto-extract from body if not in frontmatter
    for line in body.split('\n'):
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
    return strip_md(title) or 'Untitled', strip_md(subtitle), fm


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

    title, subtitle, fm = extract_metadata(md_text)
    _, body_without_fm = parse_frontmatter(md_text)
    content_html, headings = md_to_html(body_without_fm)
    toc_html = build_toc(headings)
    gen_date = datetime.now().strftime('%Y-%m-%d %H:%M')

    is_rtl = is_hebrew(md_text)
    template = UNIFIED_TEMPLATE

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
             .replace('{{MD_SOURCE}}', html.escape(body_without_fm))
             .replace('{{GENERATION_DATE}}', gen_date)
             .replace('{{PROJECT_NAME}}', html.escape(config['projectName']))
             .replace('{{ORG_NAME}}', html.escape(org_name) if org_name else '')
             .replace('{{LOGO_TEXT}}', html.escape(config['logoText']))
             .replace('{{BADGE_TEXT}}', html.escape(badge_text) if badge_text else '')
             .replace('{{FOOTER_TEXT}}', html.escape(config['footerText']))
             .replace('{{DIAGRAM_CSS}}', DIAGRAM_CSS if has_diagrams else '')
             .replace('{{DIAGRAM_SCRIPTS}}', DIAGRAM_SCRIPTS if has_diagrams else '')
             .replace('{{NOTES_CSS}}', NOTES_CSS if config.get('enableNotes', True) else '')
             .replace('{{NOTES_JS}}', NOTES_JS if config.get('enableNotes', True) else '')
             .replace('{{DIR}}', 'rtl' if is_rtl else 'ltr')
             .replace('{{LANG}}', 'he' if is_rtl else 'en'))

    # Bilingual labels based on initial direction
    if is_rtl:
        lbl = {'{{INDEX_LABEL}}': '&#1495;&#1494;&#1512;&#1492; &#1500;&#1488;&#1497;&#1504;&#1491;&#1511;&#1505;',
               '{{NARROW_LABEL}}': '&#1510;&#1512;', '{{WIDE_LABEL}}': '&#1512;&#1495;&#1489;',
               '{{FULL_LABEL}}': '&#1502;&#1500;&#1488;',
               '{{TOC_LABEL}}': '&#1514;&#1493;&#1499;&#1503; &#1506;&#1504;&#1497;&#1497;&#1504;&#1497;&#1501;',
               '{{DIR_LABEL}}': 'LTR'}
    else:
        lbl = {'{{INDEX_LABEL}}': 'Back to Index', '{{NARROW_LABEL}}': 'Narrow',
               '{{WIDE_LABEL}}': 'Wide', '{{FULL_LABEL}}': 'Full',
               '{{TOC_LABEL}}': 'Contents', '{{DIR_LABEL}}': 'RTL'}
    for key, val in lbl.items():
        final = final.replace(key, val)

    # Apply config-driven accent colors to :root CSS variables
    css_overrides = {
        '--accent:': ('accentColor', '#2563eb'),
        '--accent-light:': ('accentLight', '#dbeafe'),
        '--header-from:': ('headerFrom', '#1e3a5f'),
        '--header-to:': ('headerTo', '#2563eb'),
    }
    for css_var, (cfg_key, default_val) in css_overrides.items():
        custom_val = config.get(cfg_key, '')
        if custom_val and custom_val != default_val:
            # Replace e.g. --accent:#2563eb with --accent:#custom
            final = re.sub(
                re.escape(css_var) + r'#[0-9a-fA-F]{3,8}',
                css_var + custom_val,
                final,
                count=1,
            )

    out_path = md_path.with_suffix('.html')
    out_path.write_text(final, encoding='utf-8')
    return str(out_path)


# ─── Generate index ──────────────────────────────────────────────────────────

def generate_index(folder: str) -> str:
    """Generate index.html for a folder listing .md files and subfolders."""
    folder = Path(folder).resolve()
    out_path = folder / 'index.html'

    # Preserve custom index files
    if out_path.exists():
        existing = out_path.read_text(encoding='utf-8')
        if '<!-- custom-index -->' in existing:
            print(f'  skipped (custom index): {out_path}')
            return str(out_path)

    folder_name = folder.name or 'Docs'
    gen_date = datetime.now().strftime('%Y-%m-%d %H:%M')

    # Collect .md files
    md_files = sorted(folder.glob('*.md'))
    # Collect subdirectories that contain .md files (directly or in descendants)
    subdirs = sorted([d for d in folder.iterdir()
                      if d.is_dir() and not d.name.startswith('.')
                      and list(d.rglob('*.md'))])

    # Load config early for per-file/folder overrides
    idx_config = load_config(str(folder), title=folder_name)
    doc_overrides = idx_config.get('documents', {})   # {"filename.md": {title, description, icon, accent}}
    folder_overrides = idx_config.get('folders', {})   # {"foldername": {title, description, icon, accent}}

    cards_html = ''
    accent_colors = ['blue', 'green', 'purple']
    hebrew_count = 0
    total_count = 0

    if md_files:
        for idx, md in enumerate(md_files):
            text = md.read_text(encoding='utf-8')
            t, s, fm = extract_metadata(text)
            html_name = md.stem + '.html'
            is_heb = is_hebrew(text)
            if is_heb:
                hebrew_count += 1
            total_count += 1
            # Merge overrides: frontmatter < config documents override
            overrides = doc_overrides.get(md.name, {})
            card_title = overrides.get('title', fm.get('title', '')) or t
            card_desc = overrides.get('description', fm.get('description', '')) or s
            card_icon = overrides.get('icon', fm.get('icon', ''))
            card_accent = overrides.get('accent', fm.get('accent', '')) or accent_colors[idx % len(accent_colors)]
            lang_cls = 'he' if is_heb else 'en'
            lang_label = 'Hebrew' if is_heb else 'English'
            desc_html = f'<p>{html.escape(card_desc)}</p>' if card_desc else '<p></p>'
            icon_html = f'<span class="card-icon">{card_icon}</span>' if card_icon else ''
            cards_html += (
                f'<a class="section-card" href="{html_name}">'
                f'<div class="card-stripe {card_accent}"></div>'
                f'<div class="card-body">'
                f'{icon_html}'
                f'<div class="card-info">'
                f'<h2>{html.escape(card_title)}</h2>'
                f'{desc_html}'
                f'</div>'
                f'<div class="card-badges">'
                f'<span class="card-badge lang-{lang_cls}">{lang_label}</span>'
                f'</div>'
                f'<span class="card-arrow">&rsaquo;</span>'
                f'</div></a>\n'
            )

    if subdirs:
        for idx, d in enumerate(subdirs):
            md_count = len(list(d.rglob('*.md')))
            # Check language of first .md in subfolder
            first_md = next(d.rglob('*.md'), None)
            is_heb = False
            if first_md:
                sample = first_md.read_text(encoding='utf-8')[:500]
                is_heb = is_hebrew(sample)
            if is_heb:
                hebrew_count += 1
            total_count += 1
            # Merge overrides from config
            f_overrides = folder_overrides.get(d.name, {})
            card_title = f_overrides.get('title', d.name)
            card_desc = f_overrides.get('description', f'{md_count} document{"s" if md_count != 1 else ""}')
            card_icon = f_overrides.get('icon', '')
            card_accent = f_overrides.get('accent', accent_colors[(idx + len(md_files)) % len(accent_colors)])
            lang_cls = 'he' if is_heb else 'en'
            lang_label = 'Hebrew' if is_heb else 'English'
            icon_html = f'<span class="card-icon">{card_icon}</span>' if card_icon else ''
            cards_html += (
                f'<a class="section-card" href="{d.name}/index.html">'
                f'<div class="card-stripe {card_accent}"></div>'
                f'<div class="card-body">'
                f'{icon_html}'
                f'<div class="card-info">'
                f'<h2>{html.escape(card_title)}</h2>'
                f'<p>{html.escape(card_desc)}</p>'
                f'</div>'
                f'<div class="card-badges">'
                f'<span class="card-badge folder">{md_count} docs</span>'
                f'</div>'
                f'<span class="card-arrow">&rsaquo;</span>'
                f'</div></a>\n'
            )

    config = idx_config
    org_name = config.get('orgName', '')
    # Subtitle fallback chain: config.subtitle → orgName → empty
    subtitle_text = config.get('subtitle', '')
    org_html = ''
    if subtitle_text:
        org_html = f'<p>{html.escape(subtitle_text)}</p>'
    elif org_name:
        org_html = f'<p>{html.escape(org_name)}</p>'
    header_from = config.get('headerFrom', '#1e3a5f')
    header_to = config.get('headerTo', '#2563eb')

    # Pick RTL template if majority of docs are Hebrew
    use_rtl = total_count > 0 and hebrew_count > total_count / 2
    template = INDEX_RTL_TEMPLATE if use_rtl else INDEX_TEMPLATE

    final = (template
             .replace('{{TITLE}}', html.escape(folder_name))
             .replace('{{SUBTITLE}}', f'{total_count} item{"s" if total_count != 1 else ""}')
             .replace('{{CONTENT}}', cards_html)
             .replace('{{GENERATION_DATE}}', gen_date)
             .replace('{{PROJECT_NAME}}', html.escape(config['projectName']))
             .replace('{{LOGO_TEXT}}', html.escape(config['logoText']))
             .replace('{{ORG_HTML}}', org_html)
             .replace('{{FOOTER_TEXT}}', html.escape(config['footerText']))
             .replace('{{HEADER_FROM}}', header_from)
             .replace('{{HEADER_TO}}', header_to))

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
    # Generate indexes bottom-up — include intermediate dirs (no direct .md but have sub-dirs with .md)
    dirs_needing_index = set()
    for md in root.rglob('*.md'):
        # Add the directory containing the .md file
        dirs_needing_index.add(md.parent)
        # Add all ancestor directories up to (and including) root
        parent = md.parent.parent
        while parent >= root:
            dirs_needing_index.add(parent)
            if parent == root:
                break
            parent = parent.parent
    # Sort by depth descending so children are indexed before parents
    for d in sorted(dirs_needing_index, key=lambda p: len(p.parts), reverse=True):
        idx = generate_index(str(d))
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
