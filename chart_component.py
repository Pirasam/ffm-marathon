#!/usr/bin/env python3
"""Geteilte Effizienz-Chart-Komponente fuer beide Dashboards (Samuel + Carina).

Zeigt NUR den tempo-normierten Wert (Δ Tempo = erwarteter Puls fuers Tempo minus
tatsaechlicher Puls; positiv = effizienter, NICHT vom langsamen Laufen austricksbar).
Optional eine blasse VO2max-Kontextlinie (eigene Skala) zum Gegenchecken.
Beide Seiten sind hell -> feste helle Palette, scoped unter .effc.
"""
import json


def efficiency_chart(eff):
    runs = (eff or {}).get("runs") or []
    if len(runs) < 2 or "dev" not in (runs[0] or {}):
        return ('<section class="effc"><h2 class="effc-h">Laufeffizienz</h2>'
                '<p class="effc-empty">Noch zu wenige Läufe für den Effizienz-Verlauf – '
                'er erscheint automatisch, sobald mehr Läufe da sind.</p></section>')
    return _TEMPLATE.replace("__DATA_JSON__", json.dumps(eff, ensure_ascii=False))


_TEMPLATE = r"""<section class="effc">
<style>
.effc{--e-ink:#221f1c;--e-mut:#7c736a;--e-faint:#a89f95;--e-grid:#ece7e0;
  --e-hair:#e6e0d8;--e-teal:#2f8e9e;--e-teal-ink:#1f6b78;--e-coral:#dd5f35;
  --e-band:rgba(47,142,158,.08);--e-dot:rgba(47,142,158,.55);--e-zero:#b8afa4;
  --e-vo2:#9a8fb0;font-family:inherit;color:var(--e-ink);display:block;
  background:#fff;border:1px solid rgba(30,20,10,.08);border-radius:14px;
  padding:16px 16px 12px;margin:16px 0;box-shadow:0 1px 3px rgba(40,30,20,.05)}
.effc-h{font-size:1.05rem;margin:0;font-weight:700}
.effc-sub{color:var(--e-mut);font-size:.82rem;margin:4px 0 12px}
.effc svg{display:block;width:100%;height:auto}
.effc .gl{stroke:var(--e-grid);stroke-width:1}
.effc .zero{stroke:var(--e-zero);stroke-width:1.3;stroke-dasharray:4 3}
.effc .ax{fill:var(--e-mut);font-size:11px;font-family:inherit}
.effc .band{fill:var(--e-band)}
.effc .trend{fill:none;stroke:var(--e-coral);stroke-width:2.4;stroke-linejoin:round;stroke-linecap:round}
.effc .dot{fill:var(--e-dot);stroke:var(--e-teal);stroke-width:1}
.effc .dot.cur{fill:var(--e-coral);stroke:var(--e-coral)}
.effc .vo2{fill:none;stroke:var(--e-vo2);stroke-width:1.6;stroke-dasharray:5 4;opacity:.75}
.effc .vo2lab{fill:var(--e-vo2);font-size:9.5px;font-weight:600}
.effc .anno{fill:var(--e-faint);font-size:10px;font-family:inherit}
.effc-lg{display:flex;gap:16px;flex-wrap:wrap;align-items:center;color:var(--e-mut);
  font-size:.76rem;margin-top:6px}
.effc-lg .ls{display:inline-flex;align-items:center;gap:6px}
.effc-lg .ll{width:18px;height:0;border-top:2.4px solid var(--e-coral)}
.effc-lg .lv{width:18px;height:0;border-top:1.6px dashed var(--e-vo2)}
.effc-sz{display:inline-flex;align-items:flex-end;gap:8px}
.effc-sz span{display:inline-flex;flex-direction:column;align-items:center;gap:2px;line-height:1}
.effc-sz i{display:block;border-radius:50%;background:var(--e-dot);border:1px solid var(--e-teal)}
.effc-note{color:var(--e-mut);font-size:.82rem;margin:12px 0 0}
.effc-note b{color:var(--e-ink)}
.effc-empty{color:var(--e-mut);font-size:.9rem}
.effc details{margin-top:10px}
.effc summary{cursor:pointer;color:var(--e-teal-ink);font-size:.84rem}
.effc table{border-collapse:collapse;width:100%;margin-top:8px;font-size:.78rem;font-variant-numeric:tabular-nums}
.effc th,.effc td{text-align:right;padding:4px 7px;border-bottom:1px solid var(--e-hair)}
.effc th:first-child,.effc td:first-child{text-align:left}
.effc th{color:var(--e-mut);font-weight:500}
.effc-tw{max-height:280px;overflow:auto;border:1px solid var(--e-hair);border-radius:9px;margin-top:8px}
.effc-tip{position:fixed;pointer-events:none;opacity:0;transition:opacity .1s;z-index:50;
  background:var(--e-ink);color:#fff;border-radius:8px;padding:7px 10px;font-size:.75rem;
  line-height:1.4;box-shadow:0 6px 20px rgba(0,0,0,.25);max-width:220px}
@media (prefers-reduced-motion:reduce){.effc *{transition:none!important}}
</style>
<h2 class="effc-h">Laufeffizienz</h2>
<p class="effc-sub">Puls fürs jeweilige Tempo, je Lauf über 12 Monate. Höher = effizienter – unabhängig davon, wie schnell du läufst.</p>
<svg class="effc-svg" viewBox="0 0 900 430" role="img" aria-label="Tempo-normierte Laufeffizienz je Lauf über 12 Monate"></svg>
<div class="effc-lg">
  <span class="ls"><span class="ll"></span> Trend (28 Tage)</span>
  <span class="ls"><svg width="12" height="12"><circle cx="6" cy="6" r="4.5" class="dot"/></svg> Lauf</span>
  <span class="ls effc-vo2lg" style="display:none"><span class="lv"></span> VO₂max (Kontext, eigene Skala)</span>
  <span class="effc-sz">Distanz:
    <span><i style="width:7px;height:7px"></i>5</span>
    <span><i style="width:12px;height:12px"></i>15</span>
    <span><i style="width:17px;height:17px"></i>25 km</span>
  </span>
</div>
<p class="effc-note effc-readout"></p>
<details><summary>Alle Läufe als Tabelle</summary>
  <div class="effc-tw"><table><thead><tr><th>Datum</th><th>km</th><th>Pace</th><th>Ø-Puls</th><th>Δ Tempo</th></tr></thead><tbody class="effc-tb"></tbody></table></div>
</details>
<script>
(function(){
  var RAW=__DATA_JSON__;
  var root=document.currentScript.closest(".effc");
  var runs=RAW.runs.map(function(r){r.t=Date.parse(r.date);return r;});
  var vo=(RAW.vo2max||[]).filter(function(o){return o.v;});
  var svg=root.querySelector(".effc-svg"), NS="http://www.w3.org/2000/svg";
  var tip=document.createElement("div");tip.className="effc-tip";document.body.appendChild(tip);
  var W=900,H=430,m={l:44,r:16,t:16,b:36},iw=W-m.l-m.r,ih=H-m.t-m.b;
  var t0=Math.min.apply(0,runs.map(function(r){return r.t;})),
      t1=Math.max.apply(0,runs.map(function(r){return r.t;}));
  var pad=(t1-t0)*0.02||864e5, xmin=t0-pad, xmax=t1+pad;
  function X(t){return m.l+(t-xmin)/(xmax-xmin)*iw;}
  var vs=runs.map(function(r){return r.dev;});
  var ymin=Math.min.apply(0,vs), ymax=Math.max.apply(0,vs);
  ymin=Math.min(ymin,0);ymax=Math.max(ymax,0);
  var pdv=(ymax-ymin)*0.12||1;ymin=Math.floor(ymin-pdv);ymax=Math.ceil(ymax+pdv);
  function Y(v){return m.t+(ymax-v)/(ymax-ymin)*ih;}
  function rad(km){return 3+Math.min(Math.sqrt(km)*1.1,7);}
  function E(n,a){var e=document.createElementNS(NS,n);for(var k in a)e.setAttribute(k,a[k]);return e;}
  function pace(p){var mm=Math.floor(p),ss=Math.round((p-mm)*60);if(ss==60){mm++;ss=0;}return mm+":"+(ss<10?"0":"")+ss;}
  function sgn(v){return(v>=0?"+":"")+v;}
  var NM=["Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"];
  function trend(){var win=28*864e5,s=runs.slice().sort(function(a,b){return a.t-b.t;}),o=[];
    s.forEach(function(r){var w=s.filter(function(q){return q.t<=r.t&&q.t>r.t-win;});
      o.push([r.t,w.reduce(function(a,q){return a+q.dev;},0)/w.length]);});return o;}
  // Grid + band + zero
  var bt=Y(ymax),bb=Y(0);
  if(bb>bt){svg.appendChild(E("rect",{x:m.l,y:bt,width:iw,height:bb-bt,"class":"band"}));
    var bl=E("text",{x:m.l+5,y:bt+13,"class":"anno"});bl.textContent="besser als dein Schnitt";svg.appendChild(bl);}
  var lo=Math.ceil(ymin/3)*3;
  for(var v=lo;v<=ymax;v+=3){var y=Y(v);
    svg.appendChild(E("line",{x1:m.l,y1:y,x2:W-m.r,y2:y,"class":"gl"}));
    var t=E("text",{x:m.l-7,y:y+3.5,"class":"ax","text-anchor":"end"});t.textContent=v;svg.appendChild(t);}
  svg.appendChild(E("line",{x1:m.l,y1:Y(0),x2:W-m.r,y2:Y(0),"class":"zero"}));
  var d=new Date(xmin);d.setDate(1);d.setMonth(d.getMonth()+1);
  while(d.getTime()<xmax){var x=X(d.getTime());
    svg.appendChild(E("line",{x1:x,y1:m.t,x2:x,y2:m.t+ih,"class":"gl"}));
    var tx=E("text",{x:x,y:H-m.b+16,"class":"ax","text-anchor":"middle"});
    tx.textContent=NM[d.getMonth()]+(d.getMonth()===0?" "+String(d.getFullYear()).slice(2):"");
    svg.appendChild(tx);d.setMonth(d.getMonth()+1);}
  // VO2max-Kontextlinie (eigene Skala, in den mittleren 70% der Plothoehe)
  if(vo.length>=2){
    root.querySelector(".effc-vo2lg").style.display="inline-flex";
    var vv=vo.map(function(o){return o.v;});
    var vmin=Math.min.apply(0,vv), vmax=Math.max.apply(0,vv);
    var top=m.t+ih*0.14, bot=m.t+ih*0.86;
    function VY(x){return vmax===vmin?(top+bot)/2:bot-(x-vmin)/(vmax-vmin)*(bot-top);}
    function MX(mk){var p=mk.split("-");return X(Date.parse(p[0]+"-"+p[1]+"-15"));}
    var vpts=vo.map(function(o){return MX(o.m).toFixed(1)+","+VY(o.v).toFixed(1);});
    svg.appendChild(E("path",{d:"M"+vpts.join(" L"),"class":"vo2"}));
    var f=vo[0], l=vo[vo.length-1];
    var lf=E("text",{x:MX(f.m)+3,y:VY(f.v)-4,"class":"vo2lab"});lf.textContent="VO₂max "+f.v;svg.appendChild(lf);
    var ll=E("text",{x:MX(l.m)-3,y:VY(l.v)-4,"class":"vo2lab","text-anchor":"end"});ll.textContent=l.v;svg.appendChild(ll);
  }
  // Trend + Punkte
  var tp=trend(),ds="M"+tp.map(function(p){return X(p[0]).toFixed(1)+","+Y(p[1]).toFixed(1);}).join(" L");
  svg.appendChild(E("path",{d:ds,"class":"trend"}));
  var cur=runs.slice().sort(function(a,b){return a.t-b.t;}).pop();
  runs.forEach(function(r){
    var c=E("circle",{cx:X(r.t),cy:Y(r.dev),r:rad(r.dist),"class":"dot"+(r===cur?" cur":"")});
    c.addEventListener("mousemove",function(e){showTip(e,r);});
    c.addEventListener("mouseleave",function(){tip.style.opacity=0;});
    svg.appendChild(c);});
  function showTip(e,r){tip.style.opacity=1;
    tip.style.left=Math.min(e.clientX+13,innerWidth-225)+"px";tip.style.top=(e.clientY+13)+"px";
    tip.innerHTML="<b>"+r.date+"</b><br>"+r.dist+" km · "+pace(r.pace)+"/km<br>Ø-Puls "+r.hf+
      "<br>Δ Tempo "+sgn(r.dev)+" bpm";}
  // Readout
  var byt=runs.slice().sort(function(a,b){return a.t-b.t;});
  var last=byt.slice(-6),avg=last.reduce(function(s,o){return s+o.dev;},0)/last.length;
  var g={};runs.forEach(function(r){var k=r.date.slice(0,7);(g[k]=g[k]||[]).push(r.dev);});
  var bm=Object.keys(g).map(function(k){var a=g[k];return [k,a.reduce(function(s,v){return s+v;},0)/a.length];})
    .reduce(function(a,b){return b[1]>a[1]?b:a;});
  function f1(x){return(x>=0?"+":"")+x.toFixed(1);}
  root.querySelector(".effc-readout").innerHTML="<b>Aktuell</b> Ø "+f1(avg)+" bpm ggü. deiner Tempo-Norm "+
    "(letzte 6 Läufe) · <b>Bestmonat</b> "+f1(bm[1])+" ("+bm[0]+"). Über 0 = effizienter als dein "+
    "Jahresschnitt. Klettert der Trend Richtung +5, ist der Puls wieder synchron → grünes Licht fürs Tempo.";
  var tb=root.querySelector(".effc-tb");
  runs.slice().sort(function(a,b){return b.t-a.t;}).forEach(function(r){
    var tr=document.createElement("tr");
    tr.innerHTML="<td>"+r.date+"</td><td>"+r.dist+"</td><td>"+pace(r.pace)+"</td><td>"+r.hf+"</td><td>"+sgn(r.dev)+"</td>";
    tb.appendChild(tr);});
  addEventListener("scroll",function(){tip.style.opacity=0;},{passive:true});
})();
</script>
</section>"""
