#!/usr/bin/env python3
"""Deterministischer Dashboard-Renderer fuer Carinas Halbmarathon-Seite.

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
import statistics
from datetime import date, timedelta

from marathon_indicators import marathon_indicators

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(REPO_DIR, "frau", "garmin_data.json")
HTML_PATH = os.path.join(REPO_DIR, "frau", "index.html")

RACE_DATE = date(2027, 9, 19)   # Tegernsee-Halbmarathon
RACE_NAME = "Tegernsee-Halbmarathon"
RACE_KM = 21.1

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

# ── Roadmap zum Halbmarathon ───────────────────────────────────────────────────
# runs: Laeufe/Woche (Ziel) · long: langer Lauf (Start, Ende der Phase) in km ·
# easy: lockerer Lauf in km. Die Tageskachel und die Fortschrittsanalyse lesen
# ihre Zielwerte von hier – Aenderungen am Plan also nur an dieser Stelle.
ROADMAP = [
    {"phase": "Basis & Rhythmus", "span": "Nov – Dez 2026", "start": date(2026, 10, 26),
     "active_until": date(2026, 12, 31), "runs": 2, "long": (7, 9), "easy": 5,
     "goal": "2 Läufe pro Woche als feste Gewohnheit. Alles locker (Z2), der lange "
             "Lauf wächst auf ~9 km. Wichtigstes Ziel: der Zyklus wirft dich nicht mehr raus."},
    {"phase": "Ausdauer", "span": "Jan – Mär 2027", "start": date(2027, 1, 1),
     "active_until": date(2027, 3, 31), "runs": 2, "long": (9, 12), "easy": 5.5,
     "goal": "2, gern 3 Läufe pro Woche. Langer Lauf auf 12 km. Am Ende lockerer Läufe "
             "ein paar kurze Steigerungen – immer ins Follikel-Fenster gelegt."},
    {"phase": "Aufbau", "span": "Apr – Jun 2027", "start": date(2027, 4, 1),
     "active_until": date(2027, 6, 30), "runs": 3, "long": (12, 16), "easy": 6,
     "goal": "3 Läufe pro Woche. Langer Lauf auf 16 km. 1× pro Woche ein ruhiger "
             "Tempo-Reiz (im Follikel-Fenster), Deload in der späten Lutealphase."},
    {"phase": "Halbmarathon-Block & Taper", "span": "Jul – 19. Sep 2027", "start": date(2027, 7, 1),
     "active_until": RACE_DATE, "runs": 3, "long": (16, 19), "easy": 7,
     "goal": "Längste Läufe 18–19 km, Renntempo-Abschnitte üben, Läufe bei Sommerhitze "
             "früh legen. Die letzten 2 Wochen Taper – am 19.9. frisch an den Tegernsee."},
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
    hz = m.get("hr_zones")
    today = date.today()
    days_to_race = (RACE_DATE - today).days
    weeks_to_race = days_to_race // 7
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
        week_plan = _week_plan(pk, cycle, hz)
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

    eff_chart = marathon_indicators(m.get("marathon"), race="Halbmarathon")
    today_card = _today_card(m, hist, cycle, hz, today)
    progress_card = _progress_card(m, hist, hz, today)

    return PAGE.format(
        updated=esc(synced or today.isoformat()),
        weeks=weeks_to_race, days=days_to_race,
        race=esc(RACE_NAME), race_date=RACE_DATE.strftime("%d.%m.%Y"),
        today_card=today_card, progress_card=progress_card,
        cycle_card=cycle_card, week_plan=week_plan,
        hr_zones_card=_hr_zones_card(hz),
        charts=charts, chips=chips, runs_table=runs_table, roadmap=road,
        eff_chart=eff_chart,
    )


# ── Gemeinsame Helfer fuer Tages- und Fortschrittskachel ──────────────────────
def _roadmap_phase(today):
    for r in ROADMAP:
        if today <= r["active_until"]:
            return r
    return ROADMAP[-1]


def _long_target(today, longest_recent):
    """Ziel fuer den langen Lauf: linear ueber die Roadmap-Phase, aber nie mehr
    als +1,5 km ueber dem laengsten Lauf der letzten 3 Wochen (Verletzungsschutz)."""
    r = _roadmap_phase(today)
    span = max(1, (r["active_until"] - r["start"]).days)
    prog = min(1.0, max(0.0, (today - r["start"]).days / span))
    lo, hi = r["long"]
    t = lo + (hi - lo) * prog
    if longest_recent:
        t = max(t, min(longest_recent, hi))
        t = min(t, longest_recent + 1.5)
    # Taper: die letzten 14 Tage vor dem Rennen kuerzer
    days_to_race = (RACE_DATE - today).days
    if 0 <= days_to_race <= 7:
        t = 6
    elif 7 < days_to_race <= 14:
        t = min(t, 12)
    return round(t * 2) / 2


def _all_runs(m):
    """Alle Laeufe (12 Monate) aus der Effizienz-Historie + die letzten 14 Tage aus
    recent_activities (die sind dort u.U. noch nicht eingetragen). Alt -> neu."""
    runs = {}
    for r in ((m.get("efficiency") or {}).get("runs") or []):
        try:
            d = date.fromisoformat(r["date"])
        except Exception:
            continue
        runs[(d, round(r.get("dist") or 0, 1))] = {
            "d": d, "km": r.get("dist") or 0, "hr": r.get("hf"), "pace": r.get("pace"),
            "ei": r.get("ei_corr") or r.get("ei")}
    for a in (m.get("recent_activities") or []):
        t = a.get("type") or ""
        if "running" not in t and "trail" not in t:
            continue
        try:
            d = date.fromisoformat(a["date"])
        except Exception:
            continue
        key = (d, round(a.get("distance_km") or 0, 1))
        if key not in runs:
            runs[key] = {"d": d, "km": a.get("distance_km") or 0, "hr": a.get("avg_hr"),
                         "pace": a.get("pace_min_km"), "ei": None}
    return sorted(runs.values(), key=lambda x: x["d"])


def _week_start(d):
    return d - timedelta(days=d.weekday())


def _rhr_baseline(hist, today):
    vals = [x.get("v") for x in (hist.get("rhr") or [])
            if x.get("v") and x.get("d") != today.isoformat()][:30]
    return statistics.median(vals) if len(vals) >= 5 else None


def _z2_text(hz):
    return f"{hz['z2_floor']}–{hz['z3_floor'] - 1} bpm" if hz and hz.get("z2_floor") else "locker (Sprechtempo)"


def _dur_text(km, pace):
    if not pace:
        return ""
    mins = int(round(km * pace / 5.0) * 5)
    return f" · ca. {mins} Min" if mins < 60 else f" · ca. {mins // 60}:{mins % 60:02d} h"


# ── Kachel: Heute ─────────────────────────────────────────────────────────────
def _today_card(m, hist, cycle, hz, today):
    runs = _all_runs(m)
    r = _roadmap_phase(today)
    pk = _phase_key(cycle) if cycle and cycle.get("tracked") else None
    luteal = bool(pk and pk.startswith("luteal"))
    last = runs[-1] if runs else None
    days_since = (today - last["d"]).days if last else None
    wk = [x for x in runs if x["d"] >= _week_start(today)]
    recent3w = [x["km"] for x in runs if (today - x["d"]).days <= 21]
    longest3w = max(recent3w) if recent3w else 0
    long_t = _long_target(today, longest3w)
    easy_t = r["easy"]
    long_done = any(x["km"] >= 0.85 * long_t for x in wk)
    paces = [x["pace"] for x in runs[-6:] if x.get("pace")]
    pace = statistics.median(paces) if paces else None
    z2 = _z2_text(hz)

    # Erholungssignale – in der Lutealphase sind etwas hoeherer Ruhepuls und
    # niedrigere HRV normal, daher dort toleranter.
    rhr = m.get("resting_hr"); base = _rhr_baseline(hist, today)
    rhr_d = (rhr - base) if (rhr is not None and base is not None) else None
    tol = 2 if luteal else 0
    hrv_st = m.get("hrv_status"); sleep = m.get("sleep_hours"); bb = m.get("body_battery")
    red, yellow, reasons = [], [], []
    if rhr_d is not None:
        if rhr_d >= 6 + tol: red.append(f"Ruhepuls {rhr} (+{rhr_d:g} über deinem Normalwert)")
        elif rhr_d >= 3 + tol: yellow.append(f"Ruhepuls leicht erhöht ({rhr}, +{rhr_d:g})")
        else: reasons.append(f"Ruhepuls {rhr} – normal für dich")
    if hrv_st in ("LOW", "POOR"):
        red.append(f"HRV niedrig ({m.get('hrv_value')} ms)")
    elif hrv_st == "UNBALANCED" and not luteal:
        yellow.append(f"HRV unausgeglichen ({m.get('hrv_value')} ms)")
    elif m.get("hrv_value") is not None:
        reasons.append(f"HRV {m.get('hrv_value')} ms – im grünen Bereich" if hrv_st == "BALANCED"
                       else f"HRV {m.get('hrv_value')} ms – in der Lutealphase normal niedriger")
    if sleep is not None:
        if sleep < 5: red.append(f"nur {sleep:g} h Schlaf")
        elif sleep < 6.5: yellow.append(f"wenig Schlaf ({sleep:g} h)")
        else: reasons.append(f"{sleep:g} h Schlaf")
    if bb is not None:
        if bb < 25: red.append(f"Body Battery {bb}")
        elif bb < 50: yellow.append(f"Body Battery nur {bb}")

    def card(kind, color, title, detail, why):
        why_li = "".join(f"<li>{esc(w)}</li>" for w in why[:5])
        return f"""
      <section class="today" style="--tc:{color}" data-day="{today.isoformat()}">
        <div class="today-head"><span class="today-tag">Heute · {esc(kind)}</span>
          <span class="today-date">{today.strftime('%d.%m.')}</span></div>
        <h2 class="today-title">{esc(title)}</h2>
        <p class="today-detail">{detail}</p>
        <ul class="today-why">{why_li}</ul>
        <p class="today-stale" hidden>Diese Empfehlung ist vom {today.strftime('%d.%m.')} – die neue kommt mit dem nächsten Sync.</p>
      </section>"""

    # Renn-Woche: kurz und frisch, Renntag eigene Botschaft
    dtr = (RACE_DATE - today).days
    if dtr == 0:
        return card("Renntag", "#d64d6e", "Tegernsee – heute ist dein Tag! 🏞️",
                    "Frühstück ~3 h vor dem Start, ruhig loslaufen, die ersten 5 km bewusst langsamer als "
                    "du möchtest. Ab km 15 darfst du freigeben. Genieß den See!", [])
    if dtr == 1:
        return card("Vor dem Rennen", "#7a6cf0", "Ausschütteln oder Ruhe.",
                    "Höchstens 15 Min ganz locker mit 2 kurzen Steigerungen. Startunterlagen, Kleidung und "
                    "Verpflegung bereitlegen, kohlenhydratreich essen, früh ins Bett.", [])
    if 1 < dtr <= 7:
        easy_t, long_done = 4, True

    phase_why = []
    if pk:
        phase_why.append(f"{PHASES[pk]['label']} (Zyklustag {cycle.get('day_in_cycle')})")
    week_why = f"Diese Woche: {len(wk)} von {r['runs']} Läufen"

    if red:
        return card("Erholung", "#d64d6e", "Heute ist Erholung dran.",
                    "Kein Lauf heute. Ein Spaziergang, sanftes Dehnen oder Pilates tun gut – "
                    "dein Körper meldet, dass er Pause braucht. Bei Fieber oder Krankheitsgefühl: ganz ruhen.",
                    red + phase_why)
    if last and days_since == 0:
        return card("Erledigt", "#1f9d6b", f"Lauf erledigt – {last['km']:g} km ✓",
                    "Jetzt erholen: etwas mit Kohlenhydraten und Eiweiß essen, trinken, früh schlafen.",
                    [week_why] + phase_why)
    if days_since == 1:
        return card("Pause", "#7a6cf0", "Pause nach dem gestrigen Lauf.",
                    "Zwischen zwei Läufen liegt in dieser Phase immer ein Tag ohne Laufen – da passiert die "
                    "Anpassung. Wenn du dich bewegen magst: Spaziergang, Pilates oder 20 Min Kräftigung "
                    "(Po, Rumpf, Waden).", [f"Gestern: {last['km']:g} km", week_why] + phase_why)
    if len(wk) >= r["runs"] and long_done:
        return card("Optional", "#1f9d6b", "Wochenziel erreicht 🎉",
                    "Heute ist alles freiwillig: Ruhe, Spaziergang oder Kräftigung. Ein zusätzlicher Lauf "
                    "ist nicht nötig – Konstanz schlägt Extra-Kilometer.", [week_why] + phase_why)
    if pk == "menstruation" and (cycle.get("day_in_cycle") or 9) <= 3:
        return card("Nach Gefühl", PHASES["menstruation"]["color"], "Nach Gefühl – kurz oder Pause.",
                    f"Wenn es gut tut: {max(3, easy_t - 2):g} km ganz locker ({z2}){_dur_text(max(3, easy_t - 2), pace)}. "
                    "Wenn nicht: Pause oder Spaziergang ist genauso richtig.",
                    phase_why + reasons + yellow)

    # Lauf heute: lang oder locker?
    days_left = 6 - today.weekday()  # inkl. heute
    weekend = today.weekday() >= 5
    want_long = (not long_done) and (pk in ("follikel", "fruchtbar") or weekend or days_left <= 2)
    if pk == "luteal_late":
        want_long = False
    km = long_t if want_long else (easy_t - 1 if pk == "luteal_late" else easy_t)
    if yellow:
        km = round(min(km, easy_t) * 0.75 * 2) / 2
        want_long = False
    kind = "Langer Lauf" if want_long else "Lockerer Lauf"
    title = (f"Langer Lauf · {km:g} km" if want_long else f"Lockerer Lauf · {km:g} km")
    detail = f"Ziel-Puls {z2}{_dur_text(km, pace)}. "
    if want_long:
        detail += "Ruhig starten, gleichmäßig bleiben – Gehpausen sind erlaubt. Ab 75 Min Wasser mitnehmen."
    elif luteal:
        detail += "Bewusst ruhiger als sonst – ein etwas höherer Puls ist in dieser Phase normal."
    elif pk in ("follikel", "fruchtbar") and r["phase"] != "Basis & Rhythmus":
        detail += "Am Ende 4× 20 Sekunden zügig (Steigerungen), dazwischen locker traben."
    else:
        detail += "Sprechtempo: ganze Sätze müssen möglich sein."
    if yellow:
        detail += " Heute kürzer, weil die Erholung nicht ganz da ist."
    why = (yellow + phase_why + [week_why] +
           ([f"Letzter Lauf vor {days_since} Tagen ({last['km']:g} km)"] if last and days_since else []) +
           reasons)
    return card(kind, "#1f9d6b" if not yellow else "#d9971a", title, detail, why)


def _de(x, nd=1):
    return f"{x:.{nd}f}".replace(".", ",")


def _month(ym):
    mn = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
    try:
        y, mo = ym.split("-")
        return f"{mn[int(mo) - 1]} {y[2:]}"
    except Exception:
        return ym


# ── Kachel: Fortschritt & Tipps ───────────────────────────────────────────────
def _progress_card(m, hist, hz, today):
    runs = _all_runs(m)
    if len(runs) < 4:
        return ""
    r = _roadmap_phase(today)
    ws = _week_start(today)
    # 8 abgeschlossene Wochen (ohne die laufende)
    weeks = []
    for i in range(8, 0, -1):
        a = ws - timedelta(weeks=i); b = a + timedelta(days=7)
        wr = [x for x in runs if a <= x["d"] < b]
        weeks.append((a, len(wr), sum(x["km"] for x in wr)))
    runs_4 = sum(w[1] for w in weeks[-4:]) / 4
    km_4 = sum(w[2] for w in weeks[-4:]) / 4
    km_prev4 = sum(w[2] for w in weeks[:4]) / 4
    good_weeks = sum(1 for w in weeks if w[1] >= r["runs"])
    longest28 = max([x["km"] for x in runs if (today - x["d"]).days <= 28] or [0])
    long_t = _long_target(today, max([x["km"] for x in runs if (today - x["d"]).days <= 21] or [0]))

    # Aerobe Effizienz (Meter pro Minute je Herzschlag): letzte 5 vs. die 10 davor
    eis = [x["ei"] for x in runs if x.get("ei")]
    ei_delta = None
    if len(eis) >= 10:
        recent, before = statistics.mean(eis[-5:]), statistics.mean(eis[-15:-5])
        ei_delta = (recent / before - 1) * 100
    z3 = (hz or {}).get("z3_floor")
    hr_runs = [x for x in runs[-10:] if x.get("hr")]
    easy_share = (sum(1 for x in hr_runs if x["hr"] < z3) / len(hr_runs)) if (z3 and hr_runs) else None
    vo2 = (m.get("efficiency") or {}).get("vo2max") or []
    vo2_delta = (vo2[-1]["v"] - vo2[0]["v"]) if len(vo2) >= 2 else None

    good, todo = [], []
    if good_weeks >= 6:
        good.append(f"Konstanz: in {good_weeks} der letzten 8 Wochen {r['runs']}+ Läufe – genau das bringt dich an den Tegernsee.")
    else:
        todo.append(f"Konstanz ist der größte Hebel: nur {good_weeks} von 8 Wochen hatten {r['runs']} Läufe "
                    f"(Ø {_de(runs_4)}/Woche). Zwei feste Lauftermine in den Kalender – z.B. Di + Sa – "
                    "und den zweiten Lauf notfalls nur 3 km kurz halten.")
    if longest28 >= long_t - 0.5:
        good.append(f"Langer Lauf: {longest28:g} km in den letzten 4 Wochen – im Plan (Ziel jetzt ~{long_t:g} km).")
    else:
        todo.append(f"Langer Lauf: zuletzt max. {longest28:g} km, Ziel jetzt ~{long_t:g} km. "
                    "Pro Woche um höchstens 1 km verlängern, am liebsten im Follikel-Fenster.")
    # Erst ab nennenswertem Umfang warnen – 7 → 11 km/Woche ist kein Risiko.
    if km_prev4 > 0 and km_4 >= 15 and km_4 > km_prev4 * 1.3 and km_4 - km_prev4 > 6:
        todo.append(f"Umfang ist schnell gestiegen ({km_prev4:.0f} → {km_4:.0f} km/Woche). "
                    "Eine ruhigere Woche einplanen, bevor du weiter steigerst – das schützt Sehnen und Knochen.")
    elif km_4 > km_prev4 and km_prev4 > 0:
        good.append(f"Umfang wächst behutsam: {km_prev4:.0f} → {km_4:.0f} km pro Woche.")
    if ei_delta is not None:
        if ei_delta >= 2:
            good.append(f"Effizienz +{ei_delta:.0f} %: du läufst bei gleichem Puls schneller als vor ein paar Wochen.")
        elif ei_delta <= -3:
            todo.append(f"Effizienz {ei_delta:.0f} %: bei gleichem Puls etwas langsamer als zuvor. Oft stecken "
                        "Lutealphase, Wärme oder wenig Schlaf dahinter – kein Grund zur Sorge, Konstanz dreht das.")
    if easy_share is not None:
        if easy_share >= 0.7:
            good.append(f"Locker laufen klappt: {easy_share * 100:.0f} % der letzten Läufe im lockeren Pulsbereich (unter {z3} bpm).")
        else:
            todo.append(f"Nur {easy_share * 100:.0f} % der letzten Läufe waren wirklich locker (unter {z3} bpm). "
                        "Langsamer laufen baut die Ausdauer schneller auf als zu schnelles Laufen.")
    if vo2_delta is not None and vo2_delta <= -1:
        todo.append(f"VO₂max {vo2[0]['v']:g} ({_month(vo2[0]['m'])}) → {vo2[-1]['v']:g}: sinkt, wenn Wochen ohne Laufen dabei sind. "
                    "Mit 2 Läufen pro Woche steigt sie meist innerhalb von 6–8 Wochen wieder.")
    elif vo2_delta is not None and vo2_delta >= 1:
        good.append(f"VO₂max steigt: {vo2[0]['v']:g} ({_month(vo2[0]['m'])}) → {vo2[-1]['v']:g}.")
    # Phasen-Tipp fuer das Rennen
    phase_tip = {
        "Basis & Rhythmus": "Kräftigung 1× pro Woche (Po, Rumpf, Waden, 20 Min) macht dich robust für die längeren Läufe ab Januar.",
        "Ausdauer": "Ab jetzt 1× pro Woche am Ende eines lockeren Laufs 4–6 Steigerungen (20 s zügig) – das macht den Schritt ökonomischer.",
        "Aufbau": "Einmal im Monat einen langen Lauf mit Gel oder Riegel üben – ab 90 Minuten braucht dein Körper Nachschub.",
        "Halbmarathon-Block & Taper": "Die Strecke um den Tegernsee vorher anschauen (Höhenmeter!) und lange Läufe bei Hitze früh morgens legen.",
    }[r["phase"]]
    todo.append(phase_tip)

    kpis = "".join([
        _chip("Läufe/Woche", _de(runs_4)),
        _chip("km/Woche", f"{km_4:.0f}"),
        _chip("Längster (4 Wo.)", f"{longest28:g} km"),
        _chip("Effizienz", f"{ei_delta:+.0f} %" if ei_delta is not None else "–"),
    ])
    bars = "".join(
        f'<div class="pw"><div class="pw-bar" style="height:{min(100, n / max(r["runs"], 1) * 70):.0f}%;'
        f'background:{"#1f9d6b" if n >= r["runs"] else "#d9971a" if n else "#ece4ee"}"></div>'
        f'<span>{n}</span></div>' for _, n, _ in weeks)
    good_li = "".join(f"<li>{esc(x)}</li>" for x in good[:4]) or "<li>Noch zu wenig Daten für eine Stärken-Analyse.</li>"
    todo_li = "".join(f"<li>{esc(x)}</li>" for x in todo[:4])
    return f"""
  <section class="progress">
    <h2>Dein Fortschritt</h2>
    <p class="p-sub">Phase „{esc(r['phase'])}“ · Ziel: {r['runs']} Läufe/Woche, langer Lauf ~{long_t:g} km</p>
    <div class="chips">{kpis}</div>
    <div class="pweeks" title="Läufe pro Woche, letzte 8 Wochen">{bars}</div>
    <div class="pw-cap">Läufe pro Woche · letzte 8 Wochen (grün = Ziel erreicht)</div>
    <div class="pcols">
      <div><h3>Das läuft gut</h3><ul class="pgood">{good_li}</ul></div>
      <div><h3>So wirst du besser</h3><ul class="ptodo">{todo_li}</ul></div>
    </div>
  </section>"""


def _week_plan(phase_key, cycle, hz=None):
    nfi = cycle.get("next_follicular_in_days")
    # Konkrete Ziel-HF statt nur "locker"/"Puls" - aus ihren echten Garmin-Zonen.
    z2 = f"{hz['z2_floor']}–{hz['z3_floor']-1} bpm" if hz and hz.get("z2_floor") else "locker"
    plans = {
        "menstruation": [
            f"Wenn's gut tut: 1 kurzer, lockerer Lauf ({z2}, 3–4 km). Sonst Pause.",
            "Pilates oder ein Spaziergang sind heute vollwertiges Training.",
            "Kein Druck – die ersten Tage darfst du ruhig angehen.",
        ],
        "follikel": [
            f"2 Läufe: 1× locker ({z2}, 4–5 km) + 1× dein längster der Woche.",
            "Am langen Lauf optional 3–4 kurze Steigerungen (je ~15 s zügig).",
            "Dein Aufbau-Fenster – hier darf es sich etwas fordernder anfühlen.",
        ],
        "fruchtbar": [
            f"Leg deinen längsten Lauf jetzt ({z2}) – du hast die meiste Energie.",
            "Dazu 1 kurzer, lockerer Lauf.",
            "Sauber laufen, ebenes Terrain – die Bänder sind etwas lockerer.",
        ],
        "luteal": [
            f"2 lockere Läufe ({z2}) – Tempo bewusst rausnehmen.",
            "Distanz wie sonst, aber ruhiger; ein höherer Puls ist völlig ok.",
            "Kein Tempo-Training nötig – ruhig und gleichmäßig reicht.",
        ],
        "luteal_late": [
            f"1 kurzer, leichter Lauf ({z2}, 3–4 km) oder eine bewusste Ruhewoche.",
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


def _hr_zones_card(hz):
    """Ihre echten, in Garmin hinterlegten HF-Zonen - keine erfundene Formel.
    Gleiches Prinzip wie bei Samuels Dashboard, aber mit ihren eigenen Zahlen."""
    if not hz or not hz.get("z2_floor"):
        return ""
    rows = [
        ("Z1 · Sehr locker", hz["z1_floor"], hz["z2_floor"] - 1, "#1f9d6b"),
        ("Z2 · Locker (Grundlage)", hz["z2_floor"], hz["z3_floor"] - 1, "#1f9d6b"),
        ("Z3 · Moderat", hz["z3_floor"], hz["z4_floor"] - 1, "#2980b9"),
        ("Z4 · Tempo/Schwelle", hz["z4_floor"], hz["z5_floor"] - 1, "#7a6cf0"),
        ("Z5 · Intensiv", hz["z5_floor"], hz.get("max_hr", hz["z5_floor"] + 20), "#dd5f35"),
    ]
    lines = "".join(
        f'<div style="display:flex;align-items:center;gap:8px;padding:4px 0;">'
        f'<span style="width:8px;height:8px;border-radius:2px;background:{c};flex-shrink:0;"></span>'
        f'<span style="font-size:.82rem;color:#4a4356;flex:1;">{esc(n)}</span>'
        f'<span style="font-size:.82rem;font-weight:700;color:{c};font-variant-numeric:tabular-nums;">{lo}–{hi} bpm</span></div>'
        for n, lo, hi, c in rows
    )
    meth = "Laktatschwelle" if hz.get("method") == "LACTATE_THRESHOLD" else "% Maximalpuls"
    return f"""
  <section>
    <h2>Deine HF-Zonen</h2>
    <p class="effc-sub" style="color:#8a8398;font-size:.82rem;margin:0 0 10px;">
      Direkt aus Garmin ({esc(meth)}) · Max {hz.get('max_hr')} · Ruhe {hz.get('resting_hr')}
      {f" · Schwelle {hz['lthr']}" if hz.get('lthr') else ""}
    </p>
    {lines}
  </section>"""


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
<title>Carinas Halbmarathon</title>
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
.today{{border-left:4px solid var(--tc);background:linear-gradient(180deg,color-mix(in srgb,var(--tc) 9%,#fff),#fff)}}
.today-head{{display:flex;justify-content:space-between;align-items:baseline}}
.today-tag{{font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;color:var(--tc);font-weight:800}}
.today-date{{color:var(--mut);font-size:.8rem}}
.today-title{{margin:4px 0 6px;font-size:1.3rem}}
.today-detail{{margin:0 0 10px;color:#4a4356}}
ul.today-why{{margin:0;padding-left:18px;color:var(--mut);font-size:.84rem}}
ul.today-why li{{margin:2px 0}}
.today-stale{{margin:10px 0 0;font-size:.8rem;color:#b5452f;font-weight:600}}
.p-sub{{color:var(--mut);font-size:.85rem;margin:-6px 0 4px}}
.pweeks{{display:flex;gap:6px;align-items:flex-end;height:64px;margin-top:16px}}
.pw{{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%}}
.pw-bar{{width:100%;max-width:34px;border-radius:4px 4px 0 0;min-height:3px}}
.pw span{{font-size:.7rem;color:var(--mut);margin-top:3px}}
.pw-cap{{color:var(--mut);font-size:.72rem;margin-top:4px}}
.pcols{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px;margin-top:16px}}
.pcols h3{{font-size:.95rem;margin:0 0 6px}}
.pcols ul{{margin:0;padding-left:18px;font-size:.9rem;color:#4a4356}}
.pcols li{{margin:6px 0}}
ul.pgood li::marker{{color:#1f9d6b}} ul.ptodo li::marker{{color:#d9971a}}
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
</head>
<body>
<div class="wrap">
  <header class="top">
    <h1>Carinas Halbmarathon 🏞️</h1>
    <div class="count">
      <div><b>{weeks}</b> <span>Wochen</span></div>
      <div><b>{days}</b> <span>Tage</span></div>
    </div>
    <div class="sub">Ziel: {race} · {race_date} · 21,1 km</div>
  </header>

  {today_card}

  {cycle_card}

  <section>
    <h2>Diese Woche</h2>
    {week_plan}
  </section>

  {hr_zones_card}

  <section>
    <h2>Deine Verläufe</h2>
    <div class="grid">{charts}</div>
    <div class="chips">{chips}</div>
  </section>

  <section>
    <h2>Letzte Läufe</h2>
    {runs_table}
  </section>

  {progress_card}

  {eff_chart}

  <section>
    <h2>Der Weg zum Halbmarathon</h2>
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
<script>
// Tagesempfehlung gilt nur fuer den Tag, an dem gerendert wurde.
(function(){{var c=document.querySelector('.today');if(!c)return;
var t=new Date(),iso=t.getFullYear()+'-'+String(t.getMonth()+1).padStart(2,'0')+'-'+String(t.getDate()).padStart(2,'0');
if(c.dataset.day!==iso)c.querySelector('.today-stale').hidden=false;}})();
</script>
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
