#!/usr/bin/env python3
"""Geteilte Effizienz-Chart-Komponente fuer beide Dashboards (Samuel + Carina).

efficiency_chart(eff) -> HTML-Block (Sektion mit Style + SVG + JS, self-contained,
Daten inline). Standard-Ansicht: laengenkorrigiert. Beide Seiten sind hell, daher
eine feste helle Palette (Teal Punkte, Koralle Trendlinie), scoped unter .effc.
"""
import json


def efficiency_chart(eff, default_corrected=True):
    runs = (eff or {}).get("runs") or []
    if len(runs) < 2:
        return ('<section class="effc"><h2 class="effc-h">Laufeffizienz</h2>'
                '<p class="effc-empty">Noch zu wenige Läufe für den Effizienz-Verlauf – '
                'er erscheint automatisch, sobald mehr Läufe da sind.</p></section>')
    data_json = json.dumps(eff, ensure_ascii=False)
    default_mode = "ei_corr" if default_corrected else "ei"
    return _TEMPLATE.replace("__DATA_JSON__", data_json).replace("__DEFAULT__", default_mode)


_TEMPLATE = r"""<section class="effc">
<style>
.effc{--e-ink:#221f1c;--e-mut:#7c736a;--e-faint:#a89f95;--e-grid:#ece7e0;
  --e-hair:#e6e0d8;--e-teal:#2f8e9e;--e-teal-ink:#1f6b78;--e-coral:#dd5f35;
  --e-band:rgba(47,142,158,.08);--e-dot:rgba(47,142,158,.55);--e-surface:#fff;
  font-family:inherit;color:var(--e-ink);display:block;
  background:#fff;border:1px solid rgba(30,20,10,.08);border-radius:14px;
  padding:16px 16px 12px;margin:16px 0;box-shadow:0 1px 3px rgba(40,30,20,.05)}
.effc-head{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:6px}
.effc-h{font-size:1.05rem;margin:0;font-weight:700}
.effc-sub{color:var(--e-mut);font-size:.82rem;margin:0 0 12px}
.effc-tg{display:inline-flex;background:var(--e-grid);border-radius:8px;padding:3px;gap:2px}
.effc-tg button{font:inherit;font-size:.76rem;font-weight:500;border:0;background:transparent;
  color:var(--e-mut);padding:4px 10px;border-radius:6px;cursor:pointer}
.effc-tg button[aria-pressed="true"]{background:var(--e-surface);color:var(--e-ink);box-shadow:0 1px 2px rgba(0,0,0,.08)}
.effc svg{display:block;width:100%;height:auto}
.effc .gl{stroke:var(--e-grid);stroke-width:1}
.effc .ax{fill:var(--e-mut);font-size:11px;font-family:inherit}
.effc .band{fill:var(--e-band)}
.effc .trend{fill:none;stroke:var(--e-coral);stroke-width:2.4;stroke-linejoin:round;stroke-linecap:round}
.effc .dot{fill:var(--e-dot);stroke:var(--e-teal);stroke-width:1}
.effc .dot.cur{fill:var(--e-coral);stroke:var(--e-coral)}
.effc .anno{fill:var(--e-faint);font-size:10px;font-family:inherit}
.effc-lg{display:flex;gap:16px;flex-wrap:wrap;align-items:center;color:var(--e-mut);
  font-size:.76rem;margin-top:6px}
.effc-lg .ls{display:inline-flex;align-items:center;gap:6px}
.effc-lg .ll{width:18px;height:0;border-top:2.4px solid var(--e-coral)}
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
  line-height:1.4;box-shadow:0 6px 20px rgba(0,0,0,.25);max-width:210px}
@media (prefers-reduced-motion:reduce){.effc *{transition:none!important}}
</style>
<div class="effc-head">
  <h2 class="effc-h">Laufeffizienz</h2>
  <div class="effc-tg" role="group" aria-label="Korrektur">
    <button class="effc-braw" aria-pressed="false">Roh</button>
    <button class="effc-bcorr" aria-pressed="true">Längenkorrigiert</button>
  </div>
</div>
<p class="effc-sub">Tempo pro Herzschlag je Lauf, 12 Monate. Höher = mehr Speed bei weniger Puls.</p>
<svg class="effc-svg" viewBox="0 0 900 430" role="img" aria-label="Effizienz-Index je Lauf über 12 Monate"></svg>
<div class="effc-lg">
  <span class="ls"><span class="ll"></span> Trend (28 Tage)</span>
  <span class="ls"><svg width="12" height="12"><circle cx="6" cy="6" r="4.5" class="dot"/></svg> Lauf</span>
  <span class="effc-sz">Distanz:
    <span><i style="width:7px;height:7px"></i>5</span>
    <span><i style="width:12px;height:12px"></i>15</span>
    <span><i style="width:17px;height:17px"></i>25 km</span>
  </span>
</div>
<p class="effc-note effc-readout"></p>
<details><summary>Alle Läufe als Tabelle</summary>
  <div class="effc-tw"><table><thead><tr><th>Datum</th><th>km</th><th>Pace</th><th>Ø-Puls</th><th>EI roh</th><th>korr.</th></tr></thead><tbody class="effc-tb"></tbody></table></div>
</details>
<script>
(function(){
  var RAW=__DATA_JSON__, mode="__DEFAULT__";
  var root=document.currentScript.closest(".effc");
  var runs=RAW.runs.map(function(r){r.t=Date.parse(r.date);return r;});
  var drift=RAW.drift||0, refd=RAW.ref_dist||8;
  var svg=root.querySelector(".effc-svg"), NS="http://www.w3.org/2000/svg";
  var tip=document.createElement("div");tip.className="effc-tip";document.body.appendChild(tip);
  var W=900,H=430,m={l:44,r:16,t:16,b:36},iw=W-m.l-m.r,ih=H-m.t-m.b;
  var t0=Math.min.apply(0,runs.map(function(r){return r.t;})),
      t1=Math.max.apply(0,runs.map(function(r){return r.t;}));
  var pad=(t1-t0)*0.02||864e5, xmin=t0-pad, xmax=t1+pad;
  var allv=runs.reduce(function(a,r){a.push(r.ei,r.ei_corr);return a;},[]);
  var ymin=Math.floor(Math.min.apply(0,allv)-2), ymax=Math.ceil(Math.max.apply(0,allv)+2);
  function X(t){return m.l+(t-xmin)/(xmax-xmin)*iw;}
  function Y(v){return m.t+(ymax-v)/(ymax-ymin)*ih;}
  function rad(km){return 3+Math.min(Math.sqrt(km)*1.1,7);}
  function E(n,a){var e=document.createElementNS(NS,n);for(var k in a)e.setAttribute(k,a[k]);return e;}
  function pace(p){var mm=Math.floor(p),ss=Math.round((p-mm)*60);if(ss==60){mm++;ss=0;}return mm+":"+(ss<10?"0":"")+ss;}
  var NM=["Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"];
  function trend(){var win=28*864e5,s=runs.slice().sort(function(a,b){return a.t-b.t;}),o=[];
    s.forEach(function(r){var w=s.filter(function(q){return q.t<=r.t&&q.t>r.t-win;});
      o.push([r.t,w.reduce(function(a,q){return a+q[mode];},0)/w.length]);});return o;}
  function draw(){
    while(svg.firstChild)svg.removeChild(svg.firstChild);
    var bt=Y(ymax),bb=Y(94);
    if(bb>bt){svg.appendChild(E("rect",{x:m.l,y:bt,width:iw,height:bb-bt,"class":"band"}));
      var bl=E("text",{x:m.l+5,y:bt+13,"class":"anno"});bl.textContent="Formzone ≥ 94";svg.appendChild(bl);}
    for(var v=Math.ceil(ymin/4)*4;v<=ymax;v+=4){var y=Y(v);
      svg.appendChild(E("line",{x1:m.l,y1:y,x2:W-m.r,y2:y,"class":"gl"}));
      var t=E("text",{x:m.l-7,y:y+3.5,"class":"ax","text-anchor":"end"});t.textContent=v;svg.appendChild(t);}
    var d=new Date(xmin);d.setDate(1);d.setMonth(d.getMonth()+1);
    while(d.getTime()<xmax){var x=X(d.getTime());
      svg.appendChild(E("line",{x1:x,y1:m.t,x2:x,y2:m.t+ih,"class":"gl"}));
      var tx=E("text",{x:x,y:H-m.b+16,"class":"ax","text-anchor":"middle"});
      tx.textContent=NM[d.getMonth()]+(d.getMonth()===0?" "+String(d.getFullYear()).slice(2):"");
      svg.appendChild(tx);d.setMonth(d.getMonth()+1);}
    var tp=trend(),ds="M"+tp.map(function(p){return X(p[0]).toFixed(1)+","+Y(p[1]).toFixed(1);}).join(" L");
    svg.appendChild(E("path",{d:ds,"class":"trend"}));
    var cur=runs.slice().sort(function(a,b){return a.t-b.t;}).pop();
    runs.forEach(function(r){
      var c=E("circle",{cx:X(r.t),cy:Y(r[mode]),r:rad(r.dist),"class":"dot"+(r===cur?" cur":"")});
      c.addEventListener("mousemove",function(e){showTip(e,r);});
      c.addEventListener("mouseleave",function(){tip.style.opacity=0;});
      svg.appendChild(c);});
  }
  function showTip(e,r){tip.style.opacity=1;
    tip.style.left=Math.min(e.clientX+13,innerWidth-215)+"px";tip.style.top=(e.clientY+13)+"px";
    tip.innerHTML="<b>"+r.date+"</b><br>"+r.dist+" km · "+pace(r.pace)+"/km<br>Ø-Puls "+r.hf+
      "<br>EI roh "+r.ei+" · korr. "+r.ei_corr;}
  function setMode(mm){mode=mm;
    root.querySelector(".effc-braw").setAttribute("aria-pressed",mm==="ei");
    root.querySelector(".effc-bcorr").setAttribute("aria-pressed",mm==="ei_corr");draw();}
  root.querySelector(".effc-braw").onclick=function(){setMode("ei");};
  root.querySelector(".effc-bcorr").onclick=function(){setMode("ei_corr");};
  var byt=runs.slice().sort(function(a,b){return a.t-b.t;});
  var peak=runs.reduce(function(a,b){return b.ei_corr>a.ei_corr?b:a;});
  var last=byt.slice(-6),avg=last.reduce(function(s,o){return s+o.ei_corr;},0)/last.length;
  root.querySelector(".effc-readout").innerHTML="<b>Aktuell</b> Ø "+avg.toFixed(0)+
    " (letzte 6 Läufe) · <b>12-Monats-Hoch</b> "+peak.ei_corr.toFixed(0)+" ("+peak.date.slice(0,7)+
    ") · Herzdrift "+(drift>=0?"+":"")+drift.toFixed(2)+" bpm/km. Klettert der Wert Richtung 94+, ist der Puls wieder synchron.";
  var tb=root.querySelector(".effc-tb");
  runs.slice().sort(function(a,b){return b.t-a.t;}).forEach(function(r){
    var tr=document.createElement("tr");
    tr.innerHTML="<td>"+r.date+"</td><td>"+r.dist+"</td><td>"+pace(r.pace)+"</td><td>"+r.hf+"</td><td>"+r.ei+"</td><td>"+r.ei_corr+"</td>";
    tb.appendChild(tr);});
  addEventListener("scroll",function(){tip.style.opacity=0;},{passive:true});
  draw();
})();
</script>
</section>"""
