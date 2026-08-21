#!/usr/bin/env python3
"""Deterministischer Dashboard-Renderer fuer Carinas Marathon-Seite.

Liest frau/garmin_data.json und schreibt frau/index.html. Braucht KEINEN
API-Key und KEINE Cloud – die zyklus-basierten Empfehlungen sind hier fest und
medizinisch sauber hinterlegt (nicht taeglich neu von einer KI erfunden).

Kernidee: die zyklische Schwankung normalisieren. Carina soll sehen, dass ein
schwererer Lauf in der Lutealphase Physiologie ist, kein Rueckschritt – und dass
sie NICHT jeden Monat von vorne anfaengt. Die Werte werden als Verlauf gezeigt
(Trend-Charts), nicht als Momentaufnahme.

Aufruf (lokal oder in Carinas Sync-Job):
    python3 render_frau.py
"""
import json
import os
from datetime import date

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(REPO_DIR, "frau", "garmin_data.json")
HTML_PATH = os.path.join(REPO_DIR, "frau", "index.html")

MARATHON_DATE = date(2027, 10, 31)   # Frankfurt Marathon
MARATHON_NAME = "Frankfurt Marathon"

# ── Zyklusphasen: Botschaft + Trainingsfokus (fest, medizinisch fundiert) ──────
PHASES = {
    "menstruation": {
        "label": "Menstruation", "emoji": "🌑", "color": "#d64d6e",
        "tag": "Nach Gefühl",
        "headline": "Nach Gefühl trainieren – kein Leistungsdruck.",
        "body": ("Die ersten Tage dürfen ganz ruhig sein. Wenn ein kurzer, lockerer "
                 "Lauf gut tut: gern. Wenn nicht: Spaziergang, Pilates oder Pause "
                 "sind genauso richtig. Achte jetzt auf eisenreiche Ernährung."),
        "training": "0–1 sehr lockerer Lauf · sonst Ruhe/Pilates",
    },
    "follikel": {
        "label": "Follikelphase", "emoji": "🌱", "color": "#1f9d6b",
        "tag": "Bestes Fenster",
        "headline": "Dein stärkstes Fenster – hier darf's etwas mehr sein.",
        "body": ("Steigende Östrogene = beste Erholung und Anpassung. Hier gehört "
                 "dein längster Lauf der Woche hin, und wenn du magst ein paar kurze "
                 "Steigerungen. Dein Körper baut in dieser Phase am meisten auf."),
        "training": "Dein längster Lauf + 1 lockerer · optional Steigerungen",
    },
    "fruchtbar": {
        "label": "Fruchtbares Fenster / Eisprung", "emoji": "☀️", "color": "#d9971a",
        "tag": "Hohe Energie",
        "headline": "Viel Energie – idealer Tag für den langen Lauf.",
        "body": ("Rund um den Eisprung fühlst du dich oft am leistungsfähigsten. "
                 "Ein kleiner Hinweis: die Bänder sind minimal lockerer – lauf "
                 "sauber und meide sehr unebenes Gelände, dann ist alles gut."),
        "training": "Langer Lauf jetzt legen · gelenkschonend bleiben",
    },
    "luteal": {
        "label": "Lutealphase", "emoji": "🌙", "color": "#7a6cf0",
        "tag": "Ruhiger laufen",
        "headline": "Schwerer bei gleichem Tempo? Völlig normal.",
        "body": ("Höhere Körpertemperatur, höherer gefühlter Puls, mehr Ermüdung – "
                 "das ist die Lutealphase, kein Rückschritt. Lauf ruhiger und nach "
                 "Puls. Dass es sich anstrengender anfühlt, liegt nicht an dir."),
        "training": "1–2 lockere Läufe nach Puls · kein Tempo",
    },
    "luteal_late": {
        "label": "Späte Lutealphase (PMS)", "emoji": "🌘", "color": "#9b7cf0",
        "tag": "Erholung",
        "headline": "Ruhige Woche. Sei gut zu dir – das ist eingeplant.",
        "body": ("Die letzten Tage vor der Periode: weniger machen, mehr schlafen, "
                 "mehr Kohlenhydrate und Flüssigkeit. Eine ruhigere Woche jetzt ist "
                 "Teil des Plans – kein Versagen. Danach kommt deine Kraft zurück."),
        "training": "1 kurzer leichter Lauf oder Ruhe · Fokus Regeneration",
    },
}

# ── Roadmap zum Marathon ───────────────────────────────────────────────────────
ROADMAP = [
    {"phase": "Basis & Rhythmus", "span": "Aug – Dez 2026", "active_until": date(2026, 12, 31),
     "goal": "Konstante 2×/Woche als feste Gewohnheit etablieren – später ganz "
             "sanft Richtung 3×. Lockeres Laufen (Z2), langer Lauf wächst auf "
             "~8–10 km. Wichtigstes Ziel: der Zyklus wirft dich nicht mehr raus."},
    {"phase": "Ausdauer", "span": "Jan – Apr 2027", "active_until": date(2027, 4, 30),
     "goal": "2–3×/Woche. Langer Lauf auf 14–16 km. Erste sanfte Tempo-Reize – "
             "immer ins Follikel-Fenster gelegt."},
    {"phase": "Marathon-Aufbau", "span": "Mai – Aug 2027", "active_until": date(2027, 8, 31),
     "goal": "3–4×/Woche. Langer Lauf auf 24–28 km. Strukturiert, aber weiter "
             "zyklus-periodisiert: mehr im Follikel, Deload in der Lutealphase."},
    {"phase": "Marathonblock & Taper", "span": "Sep – Okt 2027", "active_until": date(2027, 10, 31),
     "goal": "Längste Läufe (30–32 km), dann Taper. Am 31.10. entspannt an die "
             "Startlinie in Frankfurt."},
]


def _phase_key(cycle):
    ph = (cycle or {}).get("phase")
    if ph == "luteal":
        npi = cycle.get("next_period_in_days")
        if npi is not None and npi <= 4:
            return "luteal_late"
    return ph


def _fmt(v, suffix="", dash="–"):
    return f"{v}{suffix}" if v is not None else dash


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# ── Mini-Charts (inline SVG, keine externen Libs) ──────────────────────────────
def _linechart(points, color, band=None, w=300, h=70):
    """points: Liste (label, wert) alt->neu. band: (low, high) fuer Baseline."""
    vals = [v for _, v in points if v is not None]
    if len(vals) < 2:
        return '<div class="nochart">Verlauf erscheint, sobald mehr Tage da sind.</div>'
    lo, hi = min(vals), max(vals)
    if band:
        lo = min(lo, band[0]); hi = max(hi, band[1])
    pad = (hi - lo) * 0.18 or 1
    lo -= pad; hi += pad
    n = len(points)
    def X(i): return round(i / (n - 1) * (w - 8) + 4, 1)
    def Y(v): return round(h - 6 - (v - lo) / (hi - lo) * (h - 12), 1)
    pts = [(X(i), Y(v)) for i, (_, v) in enumerate(points) if v is not None]
    line = " ".join(f"{px},{py}" for px, py in pts)
    area = (f"M{pts[0][0]},{h} L" + " L".join(f"{px},{py}" for px, py in pts)
            + f" L{pts[-1][0]},{h} Z")
    bandrect = ""
    if band:
        by1, by2 = Y(band[1]), Y(band[0])
        bandrect = (f'<rect x="0" y="{by1}" width="{w}" height="{max(1,by2-by1):.1f}" '
                    f'fill="{color}" opacity="0.13"/>')
    dot = f'<circle cx="{pts[-1][0]}" cy="{pts[-1][1]}" r="3.4" fill="{color}"/>'
    return (f'<svg viewBox="0 0 {w} {h}" class="chart" preserveAspectRatio="none">'
            f'{bandrect}<path d="{area}" fill="{color}" opacity="0.12"/>'
            f'<polyline points="{line}" fill="none" stroke="{color}" stroke-width="2.2" '
            f'stroke-linejoin="round" stroke-linecap="round"/>{dot}</svg>')


def _barchart(pairs, color, w=300, h=70):
    """pairs: Liste (label, wert) alt->neu."""
    if not pairs:
        return '<div class="nochart">Noch keine Wochen erfasst.</div>'
    vals = [v for _, v in pairs]
    hi = max(vals) or 1
    n = len(pairs); slot = w / max(n, 1); bw = min(slot * 0.55, 46)
    bars = ""
    for i, (lab, v) in enumerate(pairs):
        bh = (v / hi) * (h - 22)
        bx = i * slot + (slot - bw) / 2
        by = h - 16 - bh
        bars += (f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" '
                 f'rx="3" fill="{color}"/>'
                 f'<text x="{bx+bw/2:.1f}" y="{by-3:.1f}" class="bval">{v:g}</text>'
                 f'<text x="{bx+bw/2:.1f}" y="{h-3:.1f}" class="blab">{esc(lab)}</text>')
    return f'<svg viewBox="0 0 {w} {h}" class="chart">{bars}</svg>'


def _hist_points(hist, key, n=28):
    """Historie (neueste zuerst) -> Liste (datum, wert) alt->neu, letzte n."""
    items = list(reversed((hist.get(key) or [])[:n]))
    return [(x.get("d", ""), x.get("v")) for x in items]


def build_html(data):
    m = data.get("metrics", {}) or {}
    hist = data.get("history", {}) or {}
    cycle = m.get("cycle")
    today = date.today()
    days_to_marathon = (MARATHON_DATE - today).days
    weeks_to_marathon = days_to_marathon // 7
    synced = data.get("synced_at", "")[:16].replace("T", " ")

    # ── Zyklus-Kompass ────────────────────────────────────────────────────────
    if cycle and cycle.get("tracked"):
        pk = _phase_key(cycle)
        ph = PHASES.get(pk, PHASES["luteal"])
        day_in = cycle.get("day_in_cycle")
        clen = cycle.get("predicted_cycle_length") or 28
        npi = cycle.get("next_period_in_days")
        nfi = cycle.get("next_follicular_in_days")
        pct = min(100, round((day_in or 0) / clen * 100))
        next_period = cycle.get("next_period_date")
        cycle_card = f"""
      <section class="compass" style="--phase:{ph['color']}">
        <div class="compass-head">
          <span class="phase-emoji">{ph['emoji']}</span>
          <div>
            <div class="phase-tag">{esc(ph['tag'])}</div>
            <h2 class="phase-label">{esc(ph['label'])}</h2>
            <div class="phase-day">Zyklustag {esc(day_in)} von ~{esc(clen)}</div>
          </div>
        </div>
        <div class="cycle-bar"><div class="cycle-fill" style="width:{pct}%"></div></div>
        <p class="phase-headline">{esc(ph['headline'])}</p>
        <p class="phase-body">{esc(ph['body'])}</p>
        <div class="phase-training"><span>Diese Phase:</span> {esc(ph['training'])}</div>
        <div class="compass-preview">
          <div><b>{_fmt(npi)}</b><span>Tage bis zur Periode<br>(~{esc(next_period)})</span></div>
          <div><b>{_fmt(nfi)}</b><span>Tage bis zum nächsten<br>Follikel-Fenster</span></div>
        </div>
      </section>"""
        week_plan = _week_plan(pk, cycle)
    else:
        cycle_card = """
      <section class="compass compass-empty">
        <h2>Zyklus-Kompass</h2>
        <p>Noch keine Zyklusdaten von Natural Cycles empfangen. Sobald der erste
        Zyklus synchronisiert ist, erscheinen hier deine phasen-genauen
        Empfehlungen.</p>
      </section>"""
        week_plan = "<p>Sobald Zyklusdaten da sind, steht hier deine Wochen-Empfehlung.</p>"

    # ── Verlaufs-Charts statt Tageswerte ──────────────────────────────────────
    hrv_pts = _hist_points(hist, "hrv")
    rhr_pts = _hist_points(hist, "rhr")
    wt_pts = _hist_points(hist, "weight", 60)
    wk = list(reversed((hist.get("weekly_km") or [])[:8]))
    wk_pairs = [("KW " + x["w"].split("-W")[1], x["v"]) for x in wk]

    hrv = m.get("hrv_value"); hrv_lo = m.get("hrv_balanced_low"); hrv_hi = m.get("hrv_balanced_high")
    band = (hrv_lo, hrv_hi) if (hrv_lo and hrv_hi) else None
    in_luteal = cycle and _phase_key(cycle).startswith("luteal")
    hrv_note = (f"Baseline {_fmt(hrv_lo)}–{_fmt(hrv_hi)} · "
                + ("in der Lutealphase normal niedriger" if in_luteal else "je höher, desto erholter"))

    charts = "".join([
        _chart_card("HRV (Nacht)", _fmt(hrv), hrv_note, _linechart(hrv_pts, "#7a6cf0", band)),
        _chart_card("Ruhepuls", _fmt(m.get("resting_hr"), " bpm"), "30-Tage-Verlauf · je ruhiger, desto erholter",
                    _linechart(rhr_pts, "#d64d6e")),
        _chart_card("Wochenkilometer", _fmt(wk_pairs[-1][1] if wk_pairs else None, " km"),
                    "Lauf-km pro Woche · Konstanz zählt", _barchart(wk_pairs, "#1f9d6b")),
        _chart_card("Gewicht", _fmt(m.get("weight_kg"), " kg"), "Trend zählt, nicht der einzelne Tag",
                    _linechart(wt_pts, "#d9971a")),
    ])

    # Momentaufnahme heute (klein) – Schlaf/Energie
    chips = "".join([
        _chip("Schlaf", _fmt(m.get("sleep_hours"), " h")),
        _chip("Body Battery", _fmt(m.get("body_battery"))),
        _chip("Training Readiness", _fmt(m.get("training_readiness"))),
    ])

    # ── Läufe ─────────────────────────────────────────────────────────────────
    runs = [a for a in (m.get("recent_activities") or [])
            if "running" in (a.get("type") or "") or "trail" in (a.get("type") or "")][:6]
    if runs:
        rows = "".join(
            f"<tr><td>{esc(a.get('date'))}</td><td>{_fmt(a.get('distance_km'),' km')}</td>"
            f"<td>{_pace(a.get('pace_min_km'))}</td><td>{_fmt(a.get('avg_hr'),' bpm')}</td></tr>"
            for a in runs)
        runs_table = f"""<table class="runs"><thead><tr><th>Datum</th><th>Distanz</th>
          <th>Pace</th><th>Ø Puls</th></tr></thead><tbody>{rows}</tbody></table>"""
    else:
        runs_table = "<p>Noch keine Läufe erfasst.</p>"

    # ── Roadmap ───────────────────────────────────────────────────────────────
    road = ""
    active_found = False
    for r in ROADMAP:
        is_active = (not active_found) and today <= r["active_until"]
        if is_active:
            active_found = True
        road += f"""
        <div class="road {'road-active' if is_active else ''}">
          <div class="road-span">{esc(r['span'])}{' · jetzt' if is_active else ''}</div>
          <div class="road-phase">{esc(r['phase'])}</div>
          <div class="road-goal">{esc(r['goal'])}</div>
        </div>"""

    return PAGE.format(
        updated=esc(synced or today.isoformat()),
        weeks=weeks_to_marathon, days=days_to_marathon,
        marathon=esc(MARATHON_NAME), marathon_date="31.10.2027",
        cycle_card=cycle_card, week_plan=week_plan,
        charts=charts, chips=chips, runs_table=runs_table, roadmap=road,
    )


def _week_plan(phase_key, cycle):
    nfi = cycle.get("next_follicular_in_days")
    plans = {
        "menstruation": [
            "Wenn's gut tut: 1 kurzer, lockerer Lauf (3–4 km). Sonst Pause.",
            "Pilates oder ein Spaziergang sind heute vollwertiges Training.",
            "Kein Druck – die ersten Tage darfst du ruhig angehen.",
        ],
        "follikel": [
            "2 Läufe: 1× locker (4–5 km) + 1× dein längster der Woche.",
            "Am langen Lauf optional 3–4 kurze Steigerungen (je ~15 s zügig).",
            "Dein Aufbau-Fenster – hier darf es sich etwas fordernder anfühlen.",
        ],
        "fruchtbar": [
            "Leg deinen längsten Lauf jetzt – du hast die meiste Energie.",
            "Dazu 1 kurzer, lockerer Lauf.",
            "Sauber laufen, ebenes Terrain – die Bänder sind etwas lockerer.",
        ],
        "luteal": [
            "2 lockere Läufe nach Puls – Tempo bewusst rausnehmen.",
            "Distanz wie sonst, aber ruhiger; ein höherer Puls ist völlig ok.",
            "Kein Tempo-Training nötig – ruhig und gleichmäßig reicht.",
        ],
        "luteal_late": [
            "1 kurzer, leichter Lauf (3–4 km) oder eine bewusste Ruhewoche.",
            "Priorität: Schlaf, Kohlenhydrate, Flüssigkeit.",
            "Kein Leistungsdruck – nächste Woche kommt deine Kraft zurück.",
        ],
    }
    items = plans.get(phase_key, plans["luteal"])
    li = "".join(f"<li>{esc(x)}</li>" for x in items)
    outlook = ""
    if phase_key in ("luteal", "luteal_late") and nfi is not None:
        outlook = (f'<p class="outlook">🌱 In ~{nfi} Tagen beginnt dein '
                   f'Follikel-Fenster – <b>dann</b> legen wir den längeren Lauf '
                   f'und die erste Steigerung hin.</p>')
    return f"<ul class='week'>{li}</ul>{outlook}"


def _chart_card(label, value, hint, svg):
    return (f'<div class="card"><div class="c-top"><div class="c-label">{esc(label)}</div>'
            f'<div class="c-value">{esc(value)}</div></div>{svg}'
            f'<div class="c-hint">{esc(hint)}</div></div>')


def _chip(label, value):
    return (f'<div class="chip"><span>{esc(label)}</span><b>{esc(value)}</b></div>')


def _pace(p):
    if not p:
        return "–"
    mm = int(p); ss = int(round((p - mm) * 60))
    if ss == 60:
        mm += 1; ss = 0
    return f"{mm}:{ss:02d}/km"


PAGE = """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Carinas erster Marathon</title>
<style>
:root{{--bg:#f7f3f5;--card:#ffffff;--soft:#f1ecf1;--txt:#2c2733;--mut:#8a8398;
--line:#ece4ee;--accent:#d64d6e;--shadow:0 1px 3px rgba(60,40,70,.06),0 6px 20px rgba(60,40,70,.05);}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--txt);
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
line-height:1.5;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:760px;margin:0 auto;padding:22px 16px 60px}}
header.top{{text-align:center;padding:6px 0 4px}}
header.top h1{{font-size:1.55rem;margin:0 0 8px;letter-spacing:-.02em}}
.count{{display:inline-flex;gap:20px;align-items:baseline;background:var(--card);
border:1px solid var(--line);border-radius:14px;padding:10px 22px;box-shadow:var(--shadow)}}
.count b{{font-size:1.9rem;color:var(--accent);font-variant-numeric:tabular-nums}}
.count span{{color:var(--mut);font-size:.82rem}}
.sub{{color:var(--mut);font-size:.8rem;margin-top:10px}}
section{{background:var(--card);border:1px solid var(--line);border-radius:16px;
padding:20px;margin-top:16px;box-shadow:var(--shadow)}}
h2{{margin:0 0 12px;font-size:1.15rem}}
.compass{{border-left:4px solid var(--phase);
background:linear-gradient(180deg,color-mix(in srgb,var(--phase) 8%,#fff),#fff)}}
.compass-head{{display:flex;gap:14px;align-items:center;margin-bottom:14px}}
.phase-emoji{{font-size:2.4rem;line-height:1}}
.phase-tag{{display:inline-block;font-size:.72rem;text-transform:uppercase;
letter-spacing:.08em;color:var(--phase);font-weight:800}}
.phase-label{{margin:2px 0;font-size:1.35rem}}
.phase-day{{color:var(--mut);font-size:.85rem}}
.cycle-bar{{height:8px;background:var(--soft);border-radius:99px;overflow:hidden;margin:4px 0 16px}}
.cycle-fill{{height:100%;background:var(--phase);border-radius:99px}}
.phase-headline{{font-size:1.1rem;font-weight:650;margin:0 0 8px}}
.phase-body{{color:#5c5568;margin:0 0 14px}}
.phase-training{{background:var(--soft);border-radius:10px;padding:10px 14px;font-size:.92rem}}
.phase-training span{{color:var(--phase);font-weight:800}}
.compass-preview{{display:flex;gap:12px;margin-top:16px}}
.compass-preview>div{{flex:1;background:var(--soft);border-radius:12px;padding:12px;text-align:center}}
.compass-preview b{{display:block;font-size:1.6rem;color:var(--phase)}}
.compass-preview span{{color:var(--mut);font-size:.74rem}}
ul.week{{margin:0;padding-left:20px}}
ul.week li{{margin:7px 0}}
.outlook{{background:color-mix(in srgb,#1f9d6b 12%,#fff);border:1px solid color-mix(in srgb,#1f9d6b 25%,#fff);
border-radius:10px;padding:12px 14px;margin:14px 0 0;font-size:.92rem}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px}}
.c-top{{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px}}
.c-label{{color:var(--mut);font-size:.82rem;font-weight:600}}
.c-value{{font-size:1.35rem;font-weight:750;font-variant-numeric:tabular-nums}}
.chart{{width:100%;height:70px;display:block}}
.c-hint{{color:var(--mut);font-size:.74rem;margin-top:6px}}
.nochart{{color:var(--mut);font-size:.8rem;height:70px;display:flex;align-items:center}}
.bval{{fill:var(--mut);font-size:9px;text-anchor:middle;font-weight:700}}
.blab{{fill:var(--mut);font-size:9px;text-anchor:middle}}
.chips{{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}}
.chip{{background:var(--soft);border-radius:10px;padding:8px 14px;font-size:.85rem;
display:flex;gap:8px;align-items:baseline}}
.chip span{{color:var(--mut)}} .chip b{{font-variant-numeric:tabular-nums}}
table.runs{{width:100%;border-collapse:collapse;font-size:.9rem}}
table.runs th{{text-align:left;color:var(--mut);font-weight:600;font-size:.78rem;
padding:6px 8px;border-bottom:1px solid var(--line)}}
table.runs td{{padding:8px;border-bottom:1px solid var(--line);font-variant-numeric:tabular-nums}}
.road{{border-left:3px solid var(--line);padding:4px 0 16px 16px;position:relative}}
.road:before{{content:"";position:absolute;left:-7px;top:6px;width:11px;height:11px;
border-radius:50%;background:#d8cfdd}}
.road-active{{border-left-color:var(--accent)}}
.road-active:before{{background:var(--accent);box-shadow:0 0 0 4px color-mix(in srgb,var(--accent) 22%,transparent)}}
.road-span{{font-size:.76rem;color:var(--mut);text-transform:uppercase;letter-spacing:.05em}}
.road-active .road-span{{color:var(--accent);font-weight:700}}
.road-phase{{font-weight:750;font-size:1.05rem;margin:2px 0}}
.road-goal{{color:#5c5568;font-size:.9rem}}
.reframe{{background:linear-gradient(135deg,#f6effc,#fdf1f5);border-color:#ecdcf2}}
.reframe h2{{color:#7a4da8}}
.reframe p{{color:#4a4356;margin:0}}
footer{{text-align:center;color:var(--mut);font-size:.75rem;margin-top:28px}}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <h1>Carinas erster Marathon 🏁</h1>
    <div class="count">
      <div><b>{weeks}</b> <span>Wochen</span></div>
      <div><b>{days}</b> <span>Tage</span></div>
    </div>
    <div class="sub">Ziel: {marathon} · {marathon_date}</div>
  </header>

  {cycle_card}

  <section>
    <h2>Diese Woche</h2>
    {week_plan}
  </section>

  <section>
    <h2>Deine Verläufe</h2>
    <div class="grid">{charts}</div>
    <div class="chips">{chips}</div>
  </section>

  <section>
    <h2>Letzte Läufe</h2>
    {runs_table}
  </section>

  <section>
    <h2>Der Weg zum Marathon</h2>
    {roadmap}
  </section>

  <section class="reframe">
    <h2>Du fängst nicht jeden Monat von vorne an.</h2>
    <p>Dein Zyklus ist kein Störfaktor – er ist ein Trainingsplan-Werkzeug. Die
    stärkeren Wochen kommen in der Follikelphase, die ruhigen in der Lutealphase.
    Beides ist Fortschritt. Wenn ein Lauf sich schwer anfühlt, schau auf deinen
    Zyklustag oben – meistens erklärt er alles. Konstanz über Monate schlägt jede
    perfekte einzelne Woche.</p>
  </section>

  <footer>Automatisch aus Garmin &amp; Natural Cycles · Stand {updated}</footer>
</div>
</body>
</html>"""


def main():
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    html = build_html(data)
    os.makedirs(os.path.dirname(HTML_PATH), exist_ok=True)
    tmp = HTML_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(html)
    os.replace(tmp, HTML_PATH)
    print(f"OK: {HTML_PATH} geschrieben ({len(html)} Zeichen).")


if __name__ == "__main__":
    main()
