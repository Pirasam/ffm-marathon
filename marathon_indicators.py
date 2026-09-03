#!/usr/bin/env python3
"""Marathon-Indikatoren-Komponente (ersetzt den Effizienz-Chart auf beiden Seiten).

Drei Kacheln mit den Werten, die für den Marathon zählen:
  - Durability (Ermüdungsresistenz): aerobes Decoupling auf langen Läufen
  - Aerobe Basis: Tempo bei HF 145 (rollierend)
  - Laufökonomie: Kadenz, vertikales Verhältnis, Bodenkontakt
Alle Mini-Charts teilen eine echte 12-Monats-Zeitachse mit Monats-Ticks, und
jede Serie ist so orientiert, dass eine steigende Linie IMMER eine Verbesserung
zeigt (Durability/GCT/vert. Verhältnis werden dafür invertiert geplottet; die
angezeigten Zahlen/Labels bleiben die echten, unveränderten Werte).
Self-contained (Style + inline-SVG-Mini-Charts + Daten inline), scoped unter .mind.
"""
import json


def marathon_indicators(marathon):
    m = marathon or {}
    dur = m.get("durability") or []
    ab = m.get("aerobic_base") or []
    ec = m.get("economy") or []
    if not (dur or ab or ec):
        return ""
    payload = json.dumps({"dur": dur, "ab": ab, "ec": ec}, ensure_ascii=False)
    return _TEMPLATE.replace("__DATA__", payload)


_TEMPLATE = r"""<section class="mind">
<style>
.mind{--m-ink:#221f1c;--m-mut:#7c736a;--m-hair:#e6e0d8;--m-grid:#ece7e0;
  --m-good:#2f8a5b;--m-warn:#c08a1e;--m-bad:#c0492f;--m-line:#2f8e9e;
  font-family:inherit;color:var(--m-ink);display:block;margin:16px 0}
.mind-h{font-size:1.05rem;margin:0;font-weight:700}
.mind-sub{color:var(--m-mut);font-size:.82rem;margin:4px 0 4px}
.mind-rule{display:inline-flex;align-items:center;gap:5px;color:var(--m-good);
  font-size:.74rem;font-weight:700;background:rgba(47,138,91,.09);border-radius:6px;
  padding:3px 8px;margin-bottom:10px}
.mind-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:12px}
.mcard{background:#fff;border:1px solid rgba(30,20,10,.08);border-radius:13px;
  padding:14px 15px;box-shadow:0 1px 3px rgba(40,30,20,.05)}
.mcard h3{font-size:.82rem;margin:0;color:var(--m-mut);font-weight:600;letter-spacing:.01em}
.mcard .big{font-size:1.7rem;font-weight:750;font-variant-numeric:tabular-nums;margin:3px 0 2px;
  display:flex;align-items:baseline;gap:7px}
.mcard .big small{font-size:.8rem;color:var(--m-mut);font-weight:500}
.mcard .arrow{font-size:.85rem;font-weight:700}
.mcard .spark{display:block;width:100%;height:56px;margin:6px 0 2px}
.mcard .meaning{color:var(--m-mut);font-size:.74rem;line-height:1.4;margin-top:4px}
.mind .sp-line{fill:none;stroke:var(--m-line);stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.mind .sp-dot{fill:var(--m-line)}
.mind .sp-gl{stroke:var(--m-grid);stroke-width:1}
.mind .sp-ax{fill:var(--m-mut);font-size:8.5px;font-family:inherit}
.eco-rows{display:flex;flex-direction:column;gap:10px;margin-top:2px}
.eco-row .lab{display:flex;justify-content:space-between;align-items:baseline;font-size:.76rem;color:var(--m-mut)}
.eco-row .lab .val{font-size:.92rem;font-weight:700;color:var(--m-ink);font-variant-numeric:tabular-nums}
.eco-row .mini{display:block;width:100%;height:38px;margin-top:2px}
.mtip{position:fixed;pointer-events:none;opacity:0;transition:opacity .1s;z-index:50;
  background:var(--m-ink);color:#fff;border-radius:7px;padding:5px 9px;font-size:.72rem;
  line-height:1.35;box-shadow:0 6px 18px rgba(0,0,0,.25)}
@media (prefers-reduced-motion:reduce){.mind *{transition:none!important}}
</style>
<h2 class="mind-h">Marathon-Indikatoren</h2>
<p class="mind-sub">Die Werte, die für den Marathon zählen – nicht VO₂max: Ermüdungsresistenz, aerobe Basis, Laufökonomie. 12 Monate.</p>
<div class="mind-rule">↑ auf jedem Chart = Verbesserung</div>
<div class="mind-grid">
  <div class="mcard" data-card="dur">
    <h3>Durability · Ermüdungsresistenz</h3>
    <div class="big"><span class="v">–</span><span class="arrow"></span></div>
    <svg class="spark" viewBox="0 0 200 56" preserveAspectRatio="none"></svg>
    <div class="meaning">Puls-Drift 2. vs. 1. Longrun-Hälfte. <b>≤ 5 % = stark</b>, darunter läufst du das Tempo bis zum Schluss.</div>
  </div>
  <div class="mcard" data-card="ab">
    <h3>Aerobe Basis · Tempo @ HF 145</h3>
    <div class="big"><span class="v">–</span><span class="arrow"></span></div>
    <svg class="spark" viewBox="0 0 200 56" preserveAspectRatio="none"></svg>
    <div class="meaning">Wie schnell du bei Puls 145 läufst. <b>Schneller = fittere Basis</b> – wächst durch Grundlage, nicht durch Tempo.</div>
  </div>
  <div class="mcard" data-card="eco">
    <h3>Laufökonomie</h3>
    <div class="eco-rows"></div>
    <div class="meaning">Niedrigeres vert. Verhältnis &amp; Bodenkontakt, höhere Kadenz = ökonomischer.</div>
  </div>
</div>
<script>
(function(){
  var D=__DATA__;
  var root=document.currentScript.closest(".mind");
  var tip=document.createElement("div");tip.className="mtip";document.body.appendChild(tip);
  var NS="http://www.w3.org/2000/svg";
  function E(n,a){var e=document.createElementNS(NS,n);for(var k in a)e.setAttribute(k,a[k]);return e;}
  function fpace(s){s=Math.round(s);return Math.floor(s/60)+":"+("0"+(s%60)).slice(-2);}
  function fmtD(iso){var p=iso.split("-");return p[2]+"."+p[1]+"."+p[0].slice(2);}
  function hookTip(el,txt){el.addEventListener("mousemove",function(e){tip.style.opacity=1;
    tip.style.left=Math.min(e.clientX+12,innerWidth-170)+"px";tip.style.top=(e.clientY+12)+"px";tip.textContent=txt;});
    el.addEventListener("mouseleave",function(){tip.style.opacity=0;});}

  // Feste 12-Monats-Zeitachse, gemeinsam fuer alle Charts.
  var NM=["Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"];
  var END=new Date();END.setHours(0,0,0,0);END=END.getTime();
  var START=END-365*864e5;

  // pts: [{t, v}] chronologisch, v = ECHTER Wert (fuer Anzeige/Tooltip).
  // invert:true zeichnet -v, damit "oben am Chart" immer Verbesserung heisst.
  function drawSpark(svg,pts,invert,quarterly){
    while(svg.firstChild)svg.removeChild(svg.firstChild);
    var vb=svg.getAttribute("viewBox").split(" ").map(Number);
    var W=vb[2],H=vb[3],padL=2,padR=2,padT=4,axH=12,plotH=H-axH;
    function X(t){return padL+(t-START)/(END-START)*(W-padL-padR);}
    var vals=pts.map(function(p){return invert?-p.v:p.v;});
    var lo=Math.min.apply(0,vals),hi=Math.max.apply(0,vals);
    var pad=(hi-lo)*0.15||1;lo-=pad;hi+=pad;
    function Y(v){return padT+(hi-v)/(hi-lo)*(plotH-padT);}
    // horizontale Nulllinie/Grid dezent (2 Linien)
    svg.appendChild(E("line",{x1:padL,y1:padT,x2:W-padR,y2:padT,"class":"sp-gl"}));
    svg.appendChild(E("line",{x1:padL,y1:plotH,x2:W-padR,y2:plotH,"class":"sp-gl"}));
    // X-Achslinie
    svg.appendChild(E("line",{x1:padL,y1:plotH,x2:W-padR,y2:plotH,"class":"sp-gl"}));
    // Monats-Ticks (quartalsweise oder alle 2 Monate je nach Platz)
    var step=quarterly?3:2;
    var d=new Date(START);d.setDate(1);
    // ersten Tick auf naechstes Vielfaches ausrichten, dann step-weise
    while(d.getTime()<END){
      var x=X(d.getTime());
      if(x>=padL-1 && x<=W-padR+1){
        var tx=E("text",{x:x,y:H-1,"class":"sp-ax","text-anchor":x<padL+14?"start":(x>W-padR-14?"end":"middle")});
        tx.textContent=NM[d.getMonth()];
        svg.appendChild(tx);
      }
      d.setMonth(d.getMonth()+step);
    }
    if(pts.length<2){
      var only=pts[0];
      svg.appendChild(E("circle",{cx:X(only.t),cy:Y(invert?-only.v:only.v),r:3,"class":"sp-dot"}));
      return;
    }
    var line=pts.map(function(p,i){return X(p.t).toFixed(1)+","+Y(vals[i]).toFixed(1);});
    svg.appendChild(E("path",{d:"M"+line.join(" L"),"class":"sp-line"}));
    var lastI=pts.length-1;
    var dot=E("circle",{cx:X(pts[lastI].t),cy:Y(vals[lastI]),r:3.2,"class":"sp-dot"});
    svg.appendChild(dot);
  }

  function arrow(el,better){el.textContent=better>0?"▲":(better<0?"▼":"");
    el.style.color=better>0?"var(--m-good)":(better<0?"var(--m-bad)":"var(--m-mut)");}
  function trendArrow(vals,higherIsBetter){
    var n=vals.length;var cur=vals[n-1];
    var prev=vals.slice(Math.max(0,n-4),n-1);
    if(!prev.length)return 0;
    var pm=prev.reduce(function(a,b){return a+b;},0)/prev.length;
    var diff=(cur-pm)*(higherIsBetter?1:-1);
    return diff;
  }

  // 1) DURABILITY (niedriger Decoupling = besser -> invert=true)
  (function(){
    var c=root.querySelector('[data-card="dur"]');
    var raw=(D.dur||[]).slice().sort(function(a,b){return a.d<b.d?-1:1;})
      .map(function(x){return {t:Date.parse(x.d),v:x.decoup,km:x.km,d:x.d};})
      .filter(function(p){return p.t>=START;});
    if(raw.length<1){c.style.display="none";return;}
    var vals=raw.map(function(p){return p.v;});
    var cur=vals[vals.length-1];
    var col=cur<=5?"var(--m-good)":(cur<=8?"var(--m-warn)":"var(--m-bad)");
    var vEl=c.querySelector(".v");vEl.textContent=(cur>=0?"+":"")+cur+"%";vEl.style.color=col;
    arrow(c.querySelector(".arrow"), trendArrow(vals,false));
    var svg=c.querySelector(".spark");drawSpark(svg,raw,true,true);
    var last=raw[raw.length-1];
    hookTip(svg, fmtD(last.d)+": "+(last.v>=0?"+":"")+last.v+"% ("+last.km+" km)");
  })();

  // 2) AEROBE BASIS (schnelleres Tempo = besser -> invert=true, da pace_s kleiner=schneller)
  (function(){
    var c=root.querySelector('[data-card="ab"]');
    var raw=(D.ab||[]).slice().sort(function(a,b){return a.m<b.m?-1:1;})
      .map(function(x){return {t:Date.parse(x.m+"-15"),v:x.pace_s,m:x.m};})
      .filter(function(p){return p.t>=START;});
    if(raw.length<2){c.style.display="none";return;}
    var vals=raw.map(function(p){return p.v;});
    var cur=vals[vals.length-1];
    c.querySelector(".v").innerHTML=fpace(cur)+' <small>/km @145</small>';
    arrow(c.querySelector(".arrow"), trendArrow(vals,false));
    var svg=c.querySelector(".spark");drawSpark(svg,raw,true,true);
    var last=raw[raw.length-1];
    hookTip(svg, last.m+": "+fpace(last.v)+"/km bei HF 145");
  })();

  // 3) ÖKONOMIE (Kadenz hoch=gut; vert & GCT niedrig=gut)
  (function(){
    var c=root.querySelector('[data-card="eco"]');
    var raw=(D.ec||[]).slice().sort(function(a,b){return a.m<b.m?-1:1;});
    var wrap=c.querySelector(".eco-rows");
    var rows=[
      {key:"cad",lab:"Kadenz",unit:" spm",higherBetter:true},
      {key:"vr",lab:"Vert. Verhältnis",unit:" %",higherBetter:false},
      {key:"gct",lab:"Bodenkontakt",unit:" ms",higherBetter:false}
    ];
    var any=false;
    rows.forEach(function(r){
      var pts=raw.filter(function(x){return x[r.key]!=null;})
        .map(function(x){return {t:Date.parse(x.m+"-15"),v:x[r.key],m:x.m};})
        .filter(function(p){return p.t>=START;});
      if(pts.length<2)return;
      any=true;
      var vals=pts.map(function(p){return p.v;});
      var cur=vals[vals.length-1];
      var diff=trendArrow(vals,r.higherBetter);
      var arrowTxt=diff>0?"▲":(diff<0?"▼":"");
      var arrowCol=diff>0?"var(--m-good)":(diff<0?"var(--m-bad)":"var(--m-mut)");
      var el=document.createElement("div");el.className="eco-row";
      el.innerHTML='<div class="lab"><span>'+r.lab+'</span><span class="val">'+cur+r.unit+
        ' <span style="color:'+arrowCol+'">'+arrowTxt+'</span></span></div>'+
        '<svg class="mini" viewBox="0 0 200 38" preserveAspectRatio="none"></svg>';
      wrap.appendChild(el);
      var svg=el.querySelector(".mini");
      drawSpark(svg,pts,!r.higherBetter,false);
      var last=pts[pts.length-1];
      hookTip(svg, r.lab+" "+last.m+": "+last.v+r.unit);
    });
    if(!any)c.style.display="none";
  })();
  addEventListener("scroll",function(){tip.style.opacity=0;},{passive:true});
})();
</script>
</section>"""
