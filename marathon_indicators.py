#!/usr/bin/env python3
"""Marathon-Indikatoren-Komponente (ersetzt den Effizienz-Chart auf beiden Seiten).

Drei Kacheln mit den Werten, die für den Marathon zählen:
  - Durability (Ermüdungsresistenz): aerobes Decoupling auf langen Läufen
  - Aerobe Basis: Tempo bei HF 145 (rollierend)
  - Laufökonomie: Kadenz, vertikales Verhältnis, Bodenkontakt
Self-contained (Style + inline-SVG-Sparklines + Daten inline), scoped unter .mind.
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
.mind-sub{color:var(--m-mut);font-size:.82rem;margin:4px 0 12px}
.mind-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:12px}
.mcard{background:#fff;border:1px solid rgba(30,20,10,.08);border-radius:13px;
  padding:14px 15px;box-shadow:0 1px 3px rgba(40,30,20,.05)}
.mcard h3{font-size:.82rem;margin:0;color:var(--m-mut);font-weight:600;letter-spacing:.01em}
.mcard .big{font-size:1.7rem;font-weight:750;font-variant-numeric:tabular-nums;margin:3px 0 2px;
  display:flex;align-items:baseline;gap:7px}
.mcard .big small{font-size:.8rem;color:var(--m-mut);font-weight:500}
.mcard .arrow{font-size:.85rem;font-weight:700}
.mcard .spark{display:block;width:100%;height:38px;margin:6px 0 4px}
.mcard .meaning{color:var(--m-mut);font-size:.74rem;line-height:1.4}
.mind .sp-line{fill:none;stroke:var(--m-line);stroke-width:2;stroke-linejoin:round;stroke-linecap:round}
.mind .sp-dot{fill:var(--m-line)}
.mind .sp-good{stroke:var(--m-good)} .mind .sp-good.d{fill:var(--m-good)}
.mind .sp-zone{stroke:var(--m-hair);stroke-width:1;stroke-dasharray:3 3}
.eco-rows{display:flex;flex-direction:column;gap:9px;margin-top:2px}
.eco-row{display:grid;grid-template-columns:1fr auto;gap:8px;align-items:center}
.eco-row .lab{font-size:.76rem;color:var(--m-mut)}
.eco-row .val{font-size:.98rem;font-weight:700;font-variant-numeric:tabular-nums;text-align:right}
.eco-row .mini{grid-column:1/-1;height:22px;width:100%}
.mtip{position:fixed;pointer-events:none;opacity:0;transition:opacity .1s;z-index:50;
  background:var(--m-ink);color:#fff;border-radius:7px;padding:5px 9px;font-size:.72rem;
  line-height:1.35;box-shadow:0 6px 18px rgba(0,0,0,.25)}
@media (prefers-reduced-motion:reduce){.mind *{transition:none!important}}
</style>
<h2 class="mind-h">Marathon-Indikatoren</h2>
<p class="mind-sub">Die Werte, die für den Marathon zählen – nicht VO₂max: Ermüdungsresistenz, aerobe Basis, Laufökonomie.</p>
<div class="mind-grid">
  <div class="mcard" data-card="dur">
    <h3>Durability · Ermüdungsresistenz</h3>
    <div class="big"><span class="v">–</span><span class="arrow"></span></div>
    <svg class="spark" viewBox="0 0 200 38" preserveAspectRatio="none"></svg>
    <div class="meaning">Puls-Drift 2. vs. 1. Longrun-Hälfte. <b>≤ 5 % = stark</b>, darunter läufst du das Tempo bis zum Schluss.</div>
  </div>
  <div class="mcard" data-card="ab">
    <h3>Aerobe Basis · Tempo @ HF 145</h3>
    <div class="big"><span class="v">–</span><span class="arrow"></span></div>
    <svg class="spark" viewBox="0 0 200 38" preserveAspectRatio="none"></svg>
    <div class="meaning">Wie schnell du bei Puls 145 läufst. <b>Schneller = fittere Basis</b> – wächst durch Grundlage, nicht durch Tempo.</div>
  </div>
  <div class="mcard" data-card="eco">
    <h3>Laufökonomie</h3>
    <div class="eco-rows"></div>
    <div class="meaning" style="margin-top:8px">Niedrigeres vert. Verhältnis &amp; Bodenkontakt, höhere Kadenz = ökonomischer.</div>
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
  function hookTip(el,txt){el.addEventListener("mousemove",function(e){tip.style.opacity=1;
    tip.style.left=Math.min(e.clientX+12,innerWidth-160)+"px";tip.style.top=(e.clientY+12)+"px";tip.textContent=txt;});
    el.addEventListener("mouseleave",function(){tip.style.opacity=0;});}
  // Generische Sparkline in ein svg (values chronologisch); goodClass optional
  function spark(svg,vals,opts){
    opts=opts||{};var W=200,H=parseFloat(svg.getAttribute("viewBox").split(" ")[3]),pad=4;
    var v=vals.filter(function(x){return x!=null;});
    if(v.length<2){return;}
    var lo=Math.min.apply(0,v),hi=Math.max.apply(0,v),rng=(hi-lo)||1;
    function Y(x){return H-pad-(x-lo)/rng*(H-2*pad);}
    function X(i){return pad+i/(vals.length-1)*(W-2*pad);}
    if(opts.zone!=null&&opts.zone>=lo&&opts.zone<=hi){
      var zy=Y(opts.zone);svg.appendChild(E("line",{x1:0,y1:zy,x2:W,y2:zy,"class":"sp-zone"}));}
    var pts=[];vals.forEach(function(x,i){if(x!=null)pts.push([X(i),Y(x)]);});
    var cls="sp-line"+(opts.good?" sp-good":"");
    svg.appendChild(E("path",{d:"M"+pts.map(function(p){return p[0].toFixed(1)+","+p[1].toFixed(1);}).join(" L"),"class":cls}));
    var last=pts[pts.length-1];
    svg.appendChild(E("circle",{cx:last[0],cy:last[1],r:2.8,"class":"sp-dot"+(opts.good?" sp-good d":"")}));
  }
  function arrow(el,better){el.textContent=better>0?"▲":(better<0?"▼":"");
    el.style.color=better>0?"var(--m-good)":(better<0?"var(--m-bad)":"var(--m-mut)");}

  // 1) DURABILITY (niedrig=gut)
  (function(){
    var c=root.querySelector('[data-card="dur"]');
    var d=(D.dur||[]).slice().sort(function(a,b){return a.d<b.d?-1:1;});
    if(!d.length){c.style.display="none";return;}
    var vals=d.map(function(x){return x.decoup;});
    var cur=vals[vals.length-1];
    var col=cur<=5?"var(--m-good)":(cur<=8?"var(--m-warn)":"var(--m-bad)");
    var vEl=c.querySelector(".v");vEl.textContent=(cur>=0?"+":"")+cur+"%";vEl.style.color=col;
    // besser = niedriger -> vergleiche letzten mit Mittel der vorherigen bis zu 3
    var prev=vals.slice(-4,-1);var pm=prev.length?prev.reduce(function(a,b){return a+b;},0)/prev.length:cur;
    arrow(c.querySelector(".arrow"), pm-cur);  // gesunken (pm>cur) = besser
    var svg=c.querySelector(".spark");spark(svg,vals,{zone:5,good:cur<=5});
    hookTip(svg, d[d.length-1].d+": "+(cur>=0?"+":"")+cur+"% ("+d[d.length-1].km+" km)");
  })();

  // 2) AEROBE BASIS (schneller/niedrigere pace_s = gut)
  (function(){
    var c=root.querySelector('[data-card="ab"]');
    var d=(D.ab||[]).slice().sort(function(a,b){return a.m<b.m?-1:1;});
    if(d.length<2){c.style.display="none";return;}
    var vals=d.map(function(x){return x.pace_s;});
    var cur=vals[vals.length-1];
    c.querySelector(".v").innerHTML=fpace(cur)+' <small>/km @145</small>';
    var prev=vals.slice(-4,-1);var pm=prev.reduce(function(a,b){return a+b;},0)/prev.length;
    arrow(c.querySelector(".arrow"), pm-cur);  // schneller (pm>cur) = besser
    var svg=c.querySelector(".spark");
    // fuer Sparkline invertieren, damit "oben = schneller"
    spark(svg,vals.map(function(x){return -x;}),{good:false});
    hookTip(svg, d[d.length-1].m+": "+fpace(cur)+"/km bei HF 145");
  })();

  // 3) ÖKONOMIE (Kadenz hoch=gut; vert & GCT niedrig=gut)
  (function(){
    var c=root.querySelector('[data-card="eco"]');
    var d=(D.ec||[]).slice().sort(function(a,b){return a.m<b.m?-1:1;});
    if(!d.length){c.style.display="none";return;}
    var wrap=c.querySelector(".eco-rows");
    var rows=[
      {key:"cad",lab:"Kadenz",unit:" spm",better:1},
      {key:"vr",lab:"Vert. Verhältnis",unit:" %",better:-1},
      {key:"gct",lab:"Bodenkontakt",unit:" ms",better:-1}
    ];
    rows.forEach(function(r){
      var vals=d.map(function(x){return x[r.key];}).filter(function(x){return x!=null;});
      if(vals.length<2)return;
      var cur=vals[vals.length-1];
      var el=document.createElement("div");el.className="eco-row";
      el.innerHTML='<span class="lab">'+r.lab+'</span><span class="val">'+cur+r.unit+' <span class="ar"></span></span>'+
        '<svg class="mini" viewBox="0 0 200 22" preserveAspectRatio="none"></svg>';
      wrap.appendChild(el);
      var prev=vals.slice(-4,-1);var pm=prev.reduce(function(a,b){return a+b;},0)/prev.length;
      var better=(cur-pm)*r.better;  // >0 = verbessert
      var ar=el.querySelector(".ar");ar.textContent=better>0?"▲":(better<0?"▼":"");
      ar.style.color=better>0?"var(--m-good)":(better<0?"var(--m-bad)":"var(--m-mut)");
      ar.style.fontSize=".72rem";
      var svg=el.querySelector(".mini");
      spark(svg, r.better<0?vals.map(function(x){return -x;}):vals, {});
      hookTip(svg, r.lab+" "+d[d.length-1].m+": "+cur+r.unit);
    });
  })();
  addEventListener("scroll",function(){tip.style.opacity=0;},{passive:true});
})();
</script>
</section>"""
