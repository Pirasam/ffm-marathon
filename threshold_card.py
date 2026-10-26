#!/usr/bin/env python3
"""Kachel "Schwelle": Laktatschwellen-Tempo im 12-Monats-Verlauf (beide Seiten).

Nur das TEMPO, nicht der Schwellenpuls: der Puls an der Schwelle haengt am
(groesstenteils angeborenen) Maximalpuls und bewegt sich durch Training kaum –
das Tempo an der Schwelle ist dagegen der direkteste Fortschrittsmesser fuer
Halbmarathon/Marathon.

Self-contained (Style + Daten inline, scoped unter .thr). Setzt Chart.js voraus
(auf beiden Dashboards geladen). Y-Achse gespiegelt: steigende Linie = schneller.
"""
import json

# Renntempo grob als Anteil der Schwellengeschwindigkeit. Freizeitlaeufer auf
# diesem Niveau halten im Marathon ~85 %, im Halbmarathon ~90 %.
RACE_FACTOR = {"Marathon": 0.85, "Halbmarathon": 0.90}
RACE_KM = {"Marathon": 42.195, "Halbmarathon": 21.0975}


def _mmss(sec):
    sec = int(round(sec))
    return f"{sec // 60}:{sec % 60:02d}"


def _hmm(sec):
    sec = int(round(sec / 60.0)) * 60
    return f"{sec // 3600}:{(sec % 3600) // 60:02d}"


def threshold_card(threshold, race="Marathon"):
    pts = [p for p in (threshold or []) if p.get("pace_s")]
    if not pts:
        return f"""<section class="thr" style="margin:16px 0">
<h2 style="font-size:1.05rem;margin:0 0 6px">Schwellentempo</h2>
<p style="color:#7c736a;font-size:.85rem;margin:0">Noch kein Wert von Garmin. Die Uhr ermittelt die
Schwelle automatisch bei Läufen mit Brustgurt (Pulszonen auf „Laktatschwelle“ gestellt) – oder
direkt mit dem geführten Schwellentest auf der Uhr.</p></section>"""

    cur = pts[-1]
    # Vergleich: Wert von vor ~90 Tagen (letzter Punkt davor)
    ref = next((p for p in reversed(pts) if p["d"] <= _days_before(cur["d"], 90)), pts[0])
    delta = cur["pace_s"] - ref["pace_s"]   # negativ = schneller = besser
    if delta < -2:
        arrow, col, txt = "↑", "#2f8a5b", f"{-delta} s/km schneller als vor 3 Monaten"
    elif delta > 2:
        arrow, col, txt = "↓", "#c0492f", f"{delta} s/km langsamer als vor 3 Monaten"
    else:
        arrow, col, txt = "→", "#7c736a", "stabil gegenüber vor 3 Monaten"
    best = min(pts, key=lambda p: p["pace_s"])

    f = RACE_FACTOR.get(race, 0.85)
    race_pace = cur["pace_s"] / f
    race_time = race_pace * RACE_KM.get(race, 42.195)

    payload = json.dumps([{"d": p["d"], "v": p["pace_s"]} for p in pts])
    return f"""<section class="thr">
<style>
.thr{{display:block;margin:16px 0;background:#fff;border:1px solid rgba(30,20,10,.08);border-radius:13px;
  padding:14px 15px;box-shadow:0 1px 3px rgba(40,30,20,.05);color:#221f1c;font-family:inherit}}
.thr h2{{font-size:1.05rem;margin:0;font-weight:700}}
.thr .sub{{color:#7c736a;font-size:.8rem;margin:3px 0 8px}}
.thr .row{{display:flex;flex-wrap:wrap;gap:18px;align-items:baseline}}
.thr .big{{font-size:1.8rem;font-weight:750;font-variant-numeric:tabular-nums}}
.thr .big small{{font-size:.8rem;color:#7c736a;font-weight:500}}
.thr .delta{{font-size:.82rem;font-weight:700}}
.thr .meta{{color:#7c736a;font-size:.78rem;font-variant-numeric:tabular-nums}}
.thr .meta b{{color:#221f1c}}
.thr .wrap{{position:relative;height:170px;margin:10px 0 4px}}
.thr .wrap canvas{{width:100%!important;height:100%!important}}
.thr .note{{color:#7c736a;font-size:.74rem;line-height:1.4}}
</style>
<h2>Schwellentempo</h2>
<p class="sub">Tempo an der Laktatschwelle · Garmin-Schätzung · 12 Monate · ↑ = schneller</p>
<div class="row">
  <div class="big">{_mmss(cur['pace_s'])} <small>/km</small></div>
  <div class="delta" style="color:{col}">{arrow} {txt}</div>
</div>
<div class="meta">Bestwert {_mmss(best['pace_s'])}/km ({best['d'][8:10]}.{best['d'][5:7]}.{best['d'][2:4]}) ·
abgeleitetes {race}-Tempo ≈ <b>{_mmss(race_pace)}/km</b> (≈ {_hmm(race_time)} h an einem guten Tag)</div>
<div class="wrap"><canvas id="thr-chart"></canvas></div>
<div class="note">Je schneller dein Schwellentempo, desto schneller dein Renntempo bei gleicher Anstrengung.
Es steigt durch Konstanz, Umfang und Schwellen-Einheiten – und fällt nach Trainingspausen. Das {race}-Tempo
ist eine grobe Faustregel (~{round(f * 100)} % der Schwellengeschwindigkeit) und setzt passende Longruns voraus.</div>
<script>
(function(){{
  var D={payload};
  function draw(){{
    if(typeof Chart==='undefined'){{return setTimeout(draw,200);}}
    var el=document.getElementById('thr-chart'); if(!el)return;
    var mm=function(s){{s=Math.round(s);return Math.floor(s/60)+':'+String(s%60).padStart(2,'0');}};
    new Chart(el,{{type:'line',data:{{labels:D.map(function(p){{var x=p.d.split('-');return x[2]+'.'+x[1]+'.';}}),
      datasets:[{{data:D.map(function(p){{return p.v;}}),borderColor:'#2f8e9e',backgroundColor:'rgba(47,142,158,.10)',
      borderWidth:2,stepped:true,fill:'start',pointRadius:0,pointHitRadius:8}}]}},
      options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}},
        tooltip:{{callbacks:{{label:function(c){{return mm(c.raw)+' /km';}}}}}}}},
        scales:{{x:{{grid:{{color:'#ece7e0'}},ticks:{{maxTicksLimit:6,maxRotation:0,font:{{size:9}}}}}},
          y:{{reverse:true,grid:{{color:'#ece7e0'}},ticks:{{maxTicksLimit:5,font:{{size:9}},callback:function(v){{return mm(v);}}}}}}}}}}}});
  }}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',draw);else draw();
}})();
</script>
</section>"""


def _days_before(iso, n):
    from datetime import date, timedelta
    return (date.fromisoformat(iso) - timedelta(days=n)).isoformat()
