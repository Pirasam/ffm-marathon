#!/usr/bin/env python3
"""Selbsttest + Pruef-Banner fuer beide Dashboards (Kontrollschleife).

Das Snippet gehoert in den <head> (damit es JavaScript-Fehler von Anfang an
mitbekommt):
  - sammelt JS-Fehler
  - prueft nach dem Laden alle Chart.js-Charts auf Punkte ausserhalb der
    Zeichenflaeche und schreibt das Ergebnis in <pre id="selfcheck"> –
    check_dashboards.py liest das per Headless-Browser aus
  - laedt checks/<profil>.json nach und zeigt bei Problemen oben ein Banner
"""

SNIPPET = r"""<!-- SELFCHECK:START -->
<script>
(function(){
  var SC={errors:[],outside:[],charts:0};
  window.addEventListener('error',function(e){SC.errors.push((e.message||'Fehler')+(e.filename?' @'+e.filename.split('/').pop()+':'+e.lineno:''));});
  window.addEventListener('unhandledrejection',function(e){SC.errors.push('Promise: '+(e.reason&&e.reason.message||e.reason));});
  function chartName(ch){
    var c=ch.canvas, s=c.closest('section,.mcard,.card,div[id]');
    var h=s&&s.querySelector('h2,h3,.c-label');
    return (c.id||'')+(h?' ('+h.textContent.trim().slice(0,40)+')':'');
  }
  function selfcheck(){
    if(typeof Chart!=='undefined'&&Chart.instances){
      Object.keys(Chart.instances).forEach(function(k){
        var ch=Chart.instances[k], a=ch.chartArea;
        if(!a||ch.width===0)return;
        SC.charts++;
        var n=0;
        ch.data.datasets.forEach(function(ds,i){
          var meta=ch.getDatasetMeta(i); if(meta.hidden)return;
          if(meta.type==='bar')return;
          (meta.data||[]).forEach(function(el){
            if(!el||el.skip||isNaN(el.x)||isNaN(el.y))return;
            if(el.x<a.left-3||el.x>a.right+3||el.y<a.top-3||el.y>a.bottom+3)n++;
          });
        });
        if(n)SC.outside.push({chart:chartName(ch),n:n});
      });
    }
    var pre=document.getElementById('selfcheck');
    if(!pre){pre=document.createElement('pre');pre.id='selfcheck';pre.hidden=true;document.body.appendChild(pre);}
    pre.textContent=JSON.stringify(SC);
  }
  function banner(){
    if(location.protocol==='file:')return;
    fetch('__CHECKS_URL__?t='+Date.now(),{cache:'no-store'}).then(function(r){return r.ok?r.json():null;}).then(function(c){
      if(!c||!c.issues||!c.issues.length)return;
      var errs=c.issues.filter(function(i){return i.sev==='error';}), warns=c.issues.filter(function(i){return i.sev!=='error';});
      var esc=function(s){return String(s).replace(/[&<>]/g,function(x){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[x];});};
      var li=function(l){return l.map(function(i){return '<li>'+esc(i.msg)+'</li>';}).join('');};
      var when=(c.checked_at||'').slice(0,16).replace('T',' ');
      var b=document.createElement('div');
      b.setAttribute('style','margin:10px auto;max-width:760px;padding:10px 14px;border-radius:10px;font:13px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;'+
        (errs.length?'background:#fff4f1;border:1px solid #f3c3b6;color:#7a2a17':'background:#f7f5fb;border:1px solid #e4dff0;color:#555'));
      b.innerHTML=(errs.length?'<b>⚠ Automatische Prüfung: '+errs.length+' Problem'+(errs.length>1?'e':'')+'</b> – wird bei der täglichen Wartung automatisch repariert.<ul style="margin:6px 0 0 18px;padding:0">'+li(errs)+'</ul>':'')+
        (warns.length?'<details'+(errs.length?' style="margin-top:6px"':'')+'><summary style="cursor:pointer">'+warns.length+' Hinweis'+(warns.length>1?'e':'')+' der automatischen Prüfung</summary><ul style="margin:6px 0 0 18px;padding:0">'+li(warns)+'</ul></details>':'')+
        '<div style="opacity:.6;font-size:11px;margin-top:4px">Stand '+esc(when)+'</div>';
      document.body.insertBefore(b,document.body.firstChild);
    }).catch(function(){});
  }
  window.addEventListener('load',function(){setTimeout(selfcheck,2500);banner();});
})();
</script>
<!-- SELFCHECK:END -->"""


def snippet(checks_url):
    return SNIPPET.replace("__CHECKS_URL__", checks_url)


def inject(html, checks_url):
    """Snippet in den <head> setzen bzw. ersetzen (idempotent)."""
    import re
    block = snippet(checks_url)
    if "<!-- SELFCHECK:START -->" in html:
        return re.sub(r"<!-- SELFCHECK:START -->.*?<!-- SELFCHECK:END -->",
                      lambda m: block, html, count=1, flags=re.S)
    return html.replace("</head>", block + "\n</head>", 1)
