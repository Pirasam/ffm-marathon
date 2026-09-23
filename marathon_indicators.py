#!/usr/bin/env python3
"""Marathon-Indikatoren-Komponente (ersetzt den Effizienz-Chart auf beiden Seiten).

Drei Kacheln mit den Werten, die für den Marathon zählen:
  - Durability (Ermüdungsresistenz): aerobes Decoupling auf langen Läufen
  - Aerobe Basis: Tempo am oberen Rand der individuellen Zone 2 (rollierend)
  - Laufökonomie: Kadenz, vertikales Verhältnis, Bodenkontakt
Charts laufen über Chart.js (dieselbe Bibliothek wie die HRV/Ruhepuls-Charts
weiter oben auf der Seite) statt einer eigenen SVG-Loesung - fuer eine echte,
beschriftete Achse und dieselbe Lesbarkeit wie der Rest des Dashboards.
Jede Serie ist so orientiert (Y-Achse ggf. gespiegelt), dass eine steigende
Linie IMMER eine Verbesserung zeigt; die angezeigten Zahlen/Labels bleiben
die echten, unveraenderten Werte.
Self-contained (Style + Daten inline), scoped unter .mind. Setzt voraus, dass
Chart.js bereits auf der Seite geladen ist (bei beiden Dashboards der Fall).
"""
import json


def marathon_indicators(marathon):
    m = marathon or {}
    dur = m.get("durability") or []
    ab = m.get("aerobic_base") or []
    ec = m.get("economy") or []
    if not (dur or ab or ec):
        return ""
    payload = json.dumps({
        "dur": dur, "ab": ab, "ec": ec,
        "ab_latest": m.get("aerobic_base_latest"),
        "ab_raw": m.get("aerobic_base_raw") or [],
        "ec_raw": m.get("economy_raw") or [],
    }, ensure_ascii=False)
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
.mind-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:14px}
.mcard{background:#fff;border:1px solid rgba(30,20,10,.08);border-radius:13px;
  padding:14px 15px;box-shadow:0 1px 3px rgba(40,30,20,.05)}
.mcard h3{font-size:.82rem;margin:0;color:var(--m-mut);font-weight:600;letter-spacing:.01em}
.mcard .big{font-size:1.7rem;font-weight:750;font-variant-numeric:tabular-nums;margin:3px 0 2px;
  display:flex;align-items:baseline;gap:7px}
.mcard .big small{font-size:.8rem;color:var(--m-mut);font-weight:500}
.mcard .arrow{font-size:.85rem;font-weight:700}
.ab-latest{font-size:.72rem;color:var(--m-mut);font-variant-numeric:tabular-nums;margin:-1px 0 2px}
.ab-latest b{color:var(--m-ink);font-weight:700}
.spark-wrap{position:relative;height:170px;margin:8px 0 4px}
.spark-wrap canvas{width:100%!important;height:100%!important}
.mcard .meaning{color:var(--m-mut);font-size:.74rem;line-height:1.4;margin-top:4px}
.eco-rows{display:flex;flex-direction:column;gap:10px;margin-top:2px}
.eco-row .lab{display:flex;justify-content:space-between;align-items:baseline;font-size:.76rem;color:var(--m-mut)}
.eco-row .lab .val{font-size:.92rem;font-weight:700;color:var(--m-ink);font-variant-numeric:tabular-nums}
.mini-wrap{position:relative;height:90px;margin-top:4px}
.mini-wrap canvas{width:100%!important;height:100%!important}
</style>
<h2 class="mind-h">Marathon-Indikatoren</h2>
<p class="mind-sub">Die Werte, die für den Marathon zählen – nicht VO₂max: Ermüdungsresistenz, aerobe Basis, Laufökonomie. 12 Monate.</p>
<div class="mind-rule">↑ auf jedem Chart = Verbesserung</div>
<div class="mind-grid">
  <div class="mcard" data-card="dur">
    <h3>Durability · Ermüdungsresistenz</h3>
    <div class="big"><span class="v">–</span><span class="arrow"></span></div>
    <div class="spark-wrap"><canvas class="spark"></canvas></div>
    <div class="meaning">Puls-Drift 2. vs. 1. Longrun-Hälfte. <b>≤ 5 % = stark</b>. Graue Punkte = einzelne Longruns, Linie = gleitender 3-Longrun-Schnitt.</div>
  </div>
  <div class="mcard" data-card="ab">
    <h3>Aerobe Basis · Tempo @ <span class="ab-ref">HF</span></h3>
    <div class="big"><span class="v">–</span><span class="arrow"></span></div>
    <div class="ab-latest"></div>
    <div class="spark-wrap"><canvas class="spark"></canvas></div>
    <div class="meaning">Graue Punkte = einzelne Läufe (echtes Tempo, nicht auf die Ziel-HF umgerechnet), Linie = geglätteter 90-Tage-Trend. Wächst durch Grundlage.</div>
  </div>
  <div class="mcard" data-card="eco">
    <h3>Laufökonomie</h3>
    <div class="eco-rows"></div>
    <div class="meaning">Niedrigeres vert. Verhältnis &amp; Bodenkontakt, höhere Kadenz = ökonomischer. Graue Punkte = einzelne Läufe, Linie = Monatsschnitt.</div>
  </div>
</div>
<script>
(function(){
  var D=__DATA__;
  var root=document.currentScript.closest(".mind");
  function fpace(s){s=Math.round(s);return Math.floor(s/60)+":"+("0"+(s%60)).slice(-2);}

  // Nur die letzten 12 Monate.
  var END=new Date();END.setHours(0,0,0,0);END=END.getTime();
  var START=END-365*864e5;

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

  // Chart.js-Chart mit zwei Datenreihen (rohe Einzelwerte + geglaetteter
  // Trend) auf einer gemeinsamen Zeitachse, echte beschriftete Y-Achse -
  // dieselbe Bibliothek/Optik wie die HRV/Ruhepuls-Charts weiter oben.
  // rawPts/trendPts: [{t, v}], t = Timestamp (ms), v = ECHTER Wert.
  // reverse: true dreht die Y-Achse (fuer "niedriger = besser"), sodass
  // "oben am Chart" immer eine Verbesserung bleibt; die Achsenzahlen zeigen
  // trotzdem die echten Werte (Chart.js macht das intern, kein Vorzeichentrick noetig).
  // min/max werden EXPLIZIT aus den echten Daten gesetzt (nicht Chart.js'
  // Auto-Skalierung ueberlassen) - sonst waehlt Chart.js bei enger Datenspanne
  // (z.B. Kadenz 150-165) zu grobe, "runde" Ticks (50/150) und die eigentliche
  // Schwankung verschwindet unlesbar in der Mitte des Charts.
  function renderChart(canvas,rawPts,trendPts,opts){
    opts=opts||{};
    var color=opts.color||"#2f8e9e";
    var fmtY=opts.fmtY||function(v){return Math.round(v);};
    var allT={};
    (rawPts||[]).forEach(function(p){allT[p.t]=1;});
    (trendPts||[]).forEach(function(p){allT[p.t]=1;});
    var times=Object.keys(allT).map(Number).sort(function(a,b){return a-b;});
    if(!times.length)return null;
    var labels=times.map(function(t){var d=new Date(t);return d.getDate()+"."+(d.getMonth()+1)+"."+String(d.getFullYear()).slice(2);});
    var rawMap={};(rawPts||[]).forEach(function(p){rawMap[p.t]=p.v;});
    var trendMap={};(trendPts||[]).forEach(function(p){trendMap[p.t]=p.v;});
    var rawData=times.map(function(t){return rawMap.hasOwnProperty(t)?rawMap[t]:null;});
    var trendData=times.map(function(t){return trendMap.hasOwnProperty(t)?trendMap[t]:null;});
    var allVals=(rawPts||[]).map(function(p){return p.v;}).concat((trendPts||[]).map(function(p){return p.v;}));
    var lo=Math.min.apply(0,allVals),hi=Math.max.apply(0,allVals);
    var pad=(hi-lo)*0.15||Math.abs(hi)*0.1||1;
    return new Chart(canvas,{
      type:"line",
      data:{labels:labels,datasets:[
        {label:"roh",data:rawData,borderColor:"transparent",backgroundColor:"rgba(124,115,106,0.55)",
         pointRadius:3,pointHoverRadius:4.5,showLine:false,order:2,spanGaps:false},
        {label:"Trend",data:trendData,borderColor:color,backgroundColor:color+"22",
         borderWidth:2.4,tension:.35,fill:true,pointRadius:0,pointHoverRadius:5,
         pointBackgroundColor:color,spanGaps:true,order:1}
      ]},
      options:{
        responsive:true,maintainAspectRatio:false,
        plugins:{legend:{display:false},
          tooltip:{callbacks:{label:function(c){
            return (c.dataset.label==="roh"?"Einzelner Lauf: ":"Trend: ")+fmtY(c.raw);
          }}}},
        scales:{
          x:{grid:{color:"rgba(0,0,0,0.04)"},ticks:{maxTicksLimit:6,maxRotation:0}},
          y:{reverse:!!opts.reverse,min:lo-pad,max:hi+pad,
             grid:{color:"rgba(0,0,0,0.04)"},ticks:{maxTicksLimit:5,callback:function(v){return fmtY(v);}}}
        }
      }
    });
  }

  // 1) DURABILITY (niedriger Decoupling = besser -> reverse:true)
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
    // Geglaetteter Trend (gleitender 3-Longrun-Schnitt) - Longruns sind
    // unregelmaessig, daher Ereignis- statt Zeitfenster fuer die Glaettung.
    var trend=raw.map(function(p,i){
      var w=raw.slice(Math.max(0,i-2),i+1);
      var avg=w.reduce(function(s,x){return s+x.v;},0)/w.length;
      return {t:p.t,v:avg};
    });
    renderChart(c.querySelector(".spark"),raw,trend,{reverse:true,color:"#2f8e9e",
      fmtY:function(v){return (v>=0?"+":"")+v.toFixed(1)+"%";}});
  })();

  // 2) AEROBE BASIS (schnelleres Tempo = besser -> reverse:true, da pace_s kleiner=schneller)
  (function(){
    var c=root.querySelector('[data-card="ab"]');
    var trend=(D.ab||[]).slice().sort(function(a,b){return a.m<b.m?-1:1;})
      .map(function(x){return {t:Date.parse(x.m+"-15"),v:x.pace_s,m:x.m,ref:x.ref};})
      .filter(function(p){return p.t>=START;});
    if(trend.length<2){c.style.display="none";return;}
    var vals=trend.map(function(p){return p.v;});
    var cur=vals[vals.length-1];
    var last=trend[trend.length-1];
    var refTxt=last.ref?last.ref:"HF";
    var rawRuns=(D.ab_raw||[])
      .map(function(x){return {t:Date.parse(x.date),v:x.pace_s,hf:x.hf,date:x.date};})
      .filter(function(p){return p.t>=START;});
    c.querySelector(".ab-ref").textContent="HF "+refTxt;
    c.querySelector(".v").innerHTML=fpace(cur)+' <small>/km @'+refTxt+'</small>';
    arrow(c.querySelector(".arrow"), trendArrow(vals,false));
    renderChart(c.querySelector(".spark"),rawRuns,trend,{reverse:true,color:"#2f8e9e",fmtY:fpace});
    // Zusaetzlich der ungeglaettete Rohwert: der tatsaechlich juengste Lauf,
    // nicht durch die 90-Tage-Regression geglaettet.
    var lr=D.ab_latest;
    if(lr && lr.pace_s){
      var days=Math.round((Date.now()-Date.parse(lr.date))/864e5);
      var when=days<=0?"heute":days===1?"gestern":"vor "+days+" Tagen";
      c.querySelector(".ab-latest").innerHTML="Letzter Lauf ("+when+"): <b>"+fpace(lr.pace_s)+"/km</b> bei <b>"+Math.round(lr.hf)+" bpm</b> – unangepasst";
    }
  })();

  // 3) ÖKONOMIE (Kadenz hoch=gut; vert & GCT niedrig=gut)
  (function(){
    var c=root.querySelector('[data-card="eco"]');
    var raw=(D.ec||[]).slice().sort(function(a,b){return a.m<b.m?-1:1;});
    var wrap=c.querySelector(".eco-rows");
    var rows=[
      {key:"cad",lab:"Kadenz",unit:" spm",higherBetter:true,rawKey:"cadence"},
      {key:"vr",lab:"Vert. Verhältnis",unit:" %",higherBetter:false,rawKey:"vertical_ratio"},
      {key:"gct",lab:"Bodenkontakt",unit:" ms",higherBetter:false,rawKey:"gct"}
    ];
    var ecRaw=D.ec_raw||[];
    var any=false;
    rows.forEach(function(r){
      var pts=raw.filter(function(x){return x[r.key]!=null;})
        .map(function(x){return {t:Date.parse(x.m+"-15"),v:x[r.key],m:x.m};})
        .filter(function(p){return p.t>=START;});
      if(pts.length<2)return;
      // Rohe Tageswerte fuer denselben Zeitraum - zeigt die Streuung hinter dem Monatsmittel.
      var rawPts=ecRaw.filter(function(x){return x[r.rawKey]!=null && x.d;})
        .map(function(x){return {t:Date.parse(x.d),v:x[r.rawKey]};})
        .filter(function(p){return p.t>=START;});
      any=true;
      var vals=pts.map(function(p){return p.v;});
      var cur=vals[vals.length-1];
      var diff=trendArrow(vals,r.higherBetter);
      var arrowTxt=diff>0?"▲":(diff<0?"▼":"");
      var arrowCol=diff>0?"var(--m-good)":(diff<0?"var(--m-bad)":"var(--m-mut)");
      var el=document.createElement("div");el.className="eco-row";
      el.innerHTML='<div class="lab"><span>'+r.lab+'</span><span class="val">'+cur+r.unit+
        ' <span style="color:'+arrowCol+'">'+arrowTxt+'</span></span></div>'+
        '<div class="mini-wrap"><canvas class="mini"></canvas></div>';
      wrap.appendChild(el);
      var fmtY=function(v){return (r.key==="vr"?v.toFixed(1):Math.round(v))+r.unit;};
      renderChart(el.querySelector(".mini"),rawPts,pts,{reverse:!r.higherBetter,color:"#7a6cf0",fmtY:fmtY});
    });
    if(!any)c.style.display="none";
  })();
})();
</script>
</section>"""
