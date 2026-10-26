#!/usr/bin/env python3
"""Erzeugt den Jahresplan fuer den Frankfurt Marathon 31.10.2027 und spleisst ihn
in index.html (const weeks / const weekStarts / const MARATHON).

Stand 26.10.2026, einen Tag nach dem ersten Marathon (25.10.2026, 5:15:19,
Ø HF 162, ab km 29 Gehpausen). Lehren daraus, die in den Plan eingebaut sind:
  - Mehr Laenge: fuenf Longruns >= 30 km statt einem, Peak 3 Wochen vorher.
  - Marathontempo im Training ueben (Bloecke im Longrun), Renn-HF kennenlernen.
  - Verpflegung (~50-60 g KH/h) auf jedem Longrun > 2 h ueben.
  - Kraft durchgehend (Beine waren ab km 29 der Engpass, nicht der Kreislauf).

Prinzipien wie bisher: Mittwoch Pflichtpause, nie zwei Lauftage in Folge,
Rad = Erholung (Mo/Fr Pendeln), 3:1-Rhythmus, Tempo wird bei Belastung zuerst
gestrichen.

Aufruf:  python3 build_plan_2027.py
"""
import json
import re
from datetime import date, timedelta

RACE = date(2027, 10, 31)
FIRST_MONDAY = date(2026, 10, 26)
DAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
PREFIX = "y27"  # eigene IDs, damit alte Abhak-Staende (localStorage) nicht durchschlagen

RAD = ("Rad-Pendeln locker", ["bike", "z2"], "Locker pendeln, Puls <130 – Erholung, kein Reiz.")
KRAFT = ("Kraft · Beine & Rumpf", ["kraft", "rest"],
         "Kniebeugen, RDL, Ausfallschritte, Wadenheben, Nordic Curls, Rumpf. Kein Lauf.")
REST = ("Ruhetag", ["rest"], "Pause. Erholung ist Teil des Aufbaus.")

# Longrun je Woche (Index 1..53). None = kein klassischer Longrun.
# 0 = Regeneration, "T10"/"T21" = Formtest, "MT<n>" = Longrun mit Marathontempo-Block.
LONGRUN = {
    1: None, 2: 8,
    3: 10, 4: 11, 5: 12, 6: 9,
    7: 13, 8: 14, 9: 15, 10: 10,
    11: 15, 12: 16, 13: 17, 14: 12,
    15: 17, 16: 18, 17: 19, 18: 13,
    19: 18, 20: 20, 21: 21, 22: "T10",
    23: 20, 24: 21, 25: 22, 26: 15,
    27: 22, 28: 23, 29: 24, 30: 16,
    31: 24, 32: 25, 33: 26, 34: "T21",
    35: 22, 36: 24, 37: 26, 38: 18,
    39: 28, 40: 30, 41: "MT24", 42: 18,
    43: 30, 44: 32, 45: "MT26", 46: 20,
    47: 32, 48: 20, 49: "MT28", 50: 35,
    51: 24, 52: 16, 53: "RACE",
}
DELOAD = {6, 10, 14, 18, 22, 26, 30, 34, 38, 42, 46, 48}


def phase(i):
    if i <= 2:
        return "regen"
    if i <= 10:
        return "basis1"
    if i <= 22:
        return "basis2"
    if i <= 34:
        return "aufbau"
    if i <= 50:
        return "block"
    return "taper"


PHASE_NAME = {
    "regen": "Regeneration", "basis1": "Basis I", "basis2": "Basis II",
    "aufbau": "Aufbau", "block": "Marathonblock", "taper": "Taper",
}

# Lockere Wochenlaeufe Di/Do (km) je Phase, Entlastung ~70 %
EASY = {"basis1": (6, 7), "basis2": (8, 8), "aufbau": (9, 9), "block": (10, 10), "taper": (8, 6)}

# Qualitaet am Donnerstag (nur Aufbau/Block, nicht in Entlastungswochen) – rotierend
QUALITY_AUFBAU = [
    ("Schwelle · 9 km", ["run", "lt"], "2 km einlaufen, 2× 10 Min an der Schwelle (2 Min Trabpause), Rest locker."),
    ("Fahrtspiel · 9 km", ["run", "z2"], "Locker mit 6× 1 Min zügig nach Gefühl, dazwischen 2 Min locker."),
    ("Schwelle · 10 km", ["run", "lt"], "2 km einlaufen, 3× 10 Min an der Schwelle (2 Min Trabpause), Rest locker."),
]
QUALITY_BLOCK = [
    ("Marathonbelastung · 10 km", ["run", "z2"], "2× 20 Min im Marathontempo, 5 Min locker dazwischen. Puls notieren."),
    ("Schwelle · 10 km", ["run", "lt"], "2 km einlaufen, 2× 15 Min an der Schwelle, Rest locker."),
    ("Marathonbelastung · 12 km", ["run", "z2"], "3× 20 Min im Marathontempo, 4 Min locker dazwischen."),
]


def run(title, badges, desc):
    return (title, badges, desc)


def longrun_day(i, lr, ph):
    if lr is None:
        return ("Spaziergang · 45 Min", ["rest"], "Bewegen statt laufen. Beine lockern, Kopf frei.")
    if lr == "T10":
        return ("Formtest · 10 km", ["run", "lt"],
                "10 km zügig, aber kontrolliert (gleichmäßig, letzte 2 km frei). Zeit + Ø Puls notieren – "
                "Grundlage für die Tempo-Bereiche im Aufbau.")
    if lr == "T21":
        return ("Formtest · Halbmarathon 21 km", ["run", "lt"],
                "Halbmarathon als Test: erste 10 km im geplanten Marathontempo, danach frei steigern. "
                "Renn-Verpflegung + Frühstück wie am Marathontag üben.")
    if lr == "RACE":
        return ("MARATHON FRANKFURT", ["run", "lt"],
                "31.10.! Erste 10 km bewusst ruhig, bis km 25 im Zielbereich, ab km 30 freigeben. "
                "Gel alle ~30 Min, Wasser dazu. Diesmal mit fünf 30ern in den Beinen – genieß es.")
    if isinstance(lr, str) and lr.startswith("MT"):
        km = int(lr[2:])
        mt = {24: 12, 26: 16, 28: 18}[km]
        # Titel bewusst ohne "Marathonbelastung": dayHrTarget() zeigt dann Z2 mit
        # MT-Zusatz (Desc enthaelt "Marathontempo") statt nur den MT-Bereich.
        return (f"Longrun · {km} km mit MT-Block", ["run", "z2", "longrun"],
                f"Erst locker, dann {mt} km im Marathontempo, letzte km locker aus. Rennverpflegung "
                f"(Gel alle 30 Min) und Renn-Schuhe testen. Puls im MT-Block notieren.")
    desc = "Zone 2, gleichmäßig. "
    if lr >= 30:
        desc = ("Ruhig starten (8:00+/km), Zone 2. Gel alle 30 Min ab Min 30, Salz bei Wärme. "
                "Die 30er sind der Hauptgrund für dieses Jahr – Beine an die Länge gewöhnen.")
    elif lr >= 18:
        desc += "Verpflegung üben: Gel ab Min 45, dann alle 30 Min."
    elif lr >= 14:
        desc += "Wasser mitnehmen, bei Bedarf 1 Gel."
    else:
        desc += "Sprechtempo."
    if ph in ("basis2", "aufbau") and isinstance(lr, int) and lr >= 15 and i % 2 == 0:
        desc += " Letzte 2 km leicht zügiger."
    return (f"Longrun · {lr} km", ["run", "z2", "longrun"], desc)


def regen_week(i):
    if i == 1:
        return [
            ("Ruhetag", ["rest"], "Tag nach dem Marathon: essen, trinken, Beine hoch."),
            ("Spaziergang · 30 Min", ["rest"], "Lockeres Gehen fördert die Durchblutung. Kein Laufen."),
            REST,
            ("Rad locker · 30 Min", ["bike", "z2"], "Nur wenn die Beine es zulassen. Puls <120."),
            REST,
            ("Spaziergang oder Rad · 45 Min", ["rest"], "Weiter kein Laufen. Muskelkater muss weg sein."),
            ("Mobilität · 20 Min", ["rest"], "Sanftes Dehnen, Faszienrolle. Bilanz: alles schmerzfrei?"),
        ]
    return [
        RAD,
        ("Locker · 5 km", ["run", "z2"], "Erster Lauf nach dem Marathon. Sehr locker, bei Schmerz abbrechen."),
        REST,
        ("Locker · 6 km", ["run", "z2"], "Nur wenn Di gut war. Gehpausen sind ok."),
        RAD,
        longrun_day(i, LONGRUN[i], "regen"),
        ("Kraft · leicht", ["kraft", "rest"], "Halbe Sätze, kein Muskelkater provozieren."),
    ]


def taper_week(i):
    if i == 53:
        return [
            REST,
            ("Locker · 6 km + Steigerungen", ["run", "z2"], "Kurz, 4× 20 s zügig."),
            REST,
            ("Locker · 4 km", ["run", "z2"], "Ganz kurz lockern. Carb Load ab Freitag."),
            ("Ruhetag", ["rest"], "Carb Load Tag 1 (~8 g KH/kg). Früh ins Bett – wichtigste Nacht."),
            ("Ausschütteln · 3 km", ["run", "z2"], "15 Min locker + 2 Steigerungen. Carb Load Tag 2, Ausrüstung bereitlegen."),
            longrun_day(i, "RACE", "taper"),
        ]
    km = 8 if i == 51 else 6
    q = ("Marathonbelastung · 8 km", ["run", "z2"], "2× 10 Min im Marathontempo, sonst locker.") \
        if i == 51 else ("Locker · 6 km + Steigerungen", ["run", "z2"], "4× 20 s zügig, sonst ruhig.")
    return [
        RAD,
        (f"Locker · {km} km", ["run", "z2"], "Ruhig, Frische sammeln."),
        REST,
        q,
        RAD,
        longrun_day(i, LONGRUN[i], "taper"),
        ("Kraft · leicht", ["kraft", "rest"], "Halber Umfang, keine neuen Übungen."),
    ]


def normal_week(i, ph):
    deload = i in DELOAD
    a, b = EASY[ph]
    if deload:
        a, b = max(5, round(a * 0.7)), max(5, round(b * 0.7))
    tue = (f"Rücklauf · {a} km", ["run", "z2"], "Locker, Sprechtempo. Frequenz Richtung 168.")
    if deload or ph in ("basis1",):
        thu = (f"Rücklauf · {b} km", ["run", "z2"], "Locker." if deload else
               "Locker, am Ende 4× 20 s Steigerungen.")
    elif ph == "basis2":
        thu = (f"Rücklauf · {b} km + Steigerungen", ["run", "z2"],
               "Locker, am Ende 6× 20 s Steigerungen (zügig, nicht sprinten).")
    elif ph == "aufbau":
        thu = QUALITY_AUFBAU[i % len(QUALITY_AUFBAU)]
    else:
        thu = QUALITY_BLOCK[i % len(QUALITY_BLOCK)]
    return [RAD, tue, REST, thu, RAD, longrun_day(i, LONGRUN[i], ph), KRAFT]


def km_of(title):
    m = re.search(r"(\d+)\s*km", title)
    return int(m.group(1)) if m else 0


def build():
    weeks, starts = [], []
    for i in range(1, 54):
        ws = FIRST_MONDAY + timedelta(weeks=i - 1)
        ph = phase(i)
        if ph == "regen":
            days = regen_week(i)
        elif ph == "taper":
            days = taper_week(i)
        else:
            days = normal_week(i, ph)
        run_km = sum(km_of(t) for t, bd, _ in days if "run" in bd and t != "MARATHON FRANKFURT")
        lr = LONGRUN[i]
        lr_txt = ("–" if lr is None else "42,2 km" if lr == "RACE" else "10 km Test" if lr == "T10"
                  else "21 km Test" if lr == "T21" else f"{lr[2:]} km (MT)" if isinstance(lr, str)
                  else f"{lr} km")
        intensity = {"regen": "keine", "basis1": "nur locker", "basis2": "locker + Steigerungen",
                     "aufbau": "1× Qualität", "block": "1× Qualität", "taper": "kurz & frisch"}[ph]
        if i in DELOAD:
            intensity = "Entlastung"
        focus = f"{PHASE_NAME[ph]}{' · Entlastung' if i in DELOAD else ''} ({run_km} km)" if ph != "regen" \
            else "Regeneration nach dem Marathon"
        if i == 53:
            focus = "Frisch bleiben · MARATHON"
        week = {
            "label": f"W{i}",
            "name": f"Woche {i}" if i != 53 else "Renn-Woche",
            "focus": focus,
            "stats": [{"l": "Laufen", "v": f"~{run_km} km" if run_km else "0 km"},
                      {"l": "Rad", "v": "Pendeln" if ph != "regen" or i == 2 else "locker"},
                      {"l": "Intensität", "v": intensity},
                      {"l": "Longrun", "v": lr_txt}],
            "days": [],
            "note": NOTES.get(i) or PHASE_NOTE[ph],
        }
        for d_i, (title, badges, desc) in enumerate(days):
            d = {"id": f"{PREFIX}w{i}{DAYS[d_i].lower()}", "name": DAYS[d_i],
                 "title": title, "badges": [b for b in badges if b != "longrun"], "desc": desc}
            if "longrun" in badges:
                d["longrun"] = True
            week["days"].append(d)
        weeks.append(week)
        starts.append(ws.isoformat())
    assert starts[-1] <= RACE.isoformat() < (date.fromisoformat(starts[-1]) + timedelta(days=7)).isoformat()
    return weeks, starts


PHASE_NOTE = {
    "regen": "Zwei Wochen Regeneration nach dem Marathon. Erst laufen, wenn Treppen wieder normal gehen. "
             "Brustdruck, Herzstolpern oder Fieber → Arzt, kein Training.",
    "basis1": "Basis I: Laufen wieder zur Routine machen. Alles locker, Gewicht Richtung 87 kg ohne hartes Defizit.",
    "basis2": "Basis II: Longrun wächst langsam. Steigerungen halten die Beine schnell, ohne zu ermüden.",
    "aufbau": "Aufbau: 1 Qualitätseinheit pro Woche (Do). Fühlt sich die Woche schwer an, Qualität zuerst streichen.",
    "block": "Marathonblock: Die 30er sind das Wichtigste. Verpflegung jedes Mal üben (~50–60 g KH/h).",
    "taper": "Taper: Umfang runter, Frische rauf. Keine neuen Schuhe, kein neues Essen.",
}
NOTES = {
    10: "Weihnachten/Silvester: Entlastungswoche, Longrun gern flexibel verschieben.",
    22: "Formtest 10 km: Ergebnis legt die Tempobereiche für den Aufbau fest.",
    34: "Formtest Halbmarathon: realistische Marathon-Prognose ≈ HM-Zeit × 2,2 (für Erstlings-Marathonis eher × 2,25).",
    40: "Erster 30er des Jahres. 2026 gab es nur einen – dieses Mal werden es fünf.",
    50: "Peak-Longrun 35 km, drei Wochen vor dem Rennen. Danach beginnt der Taper.",
    53: "Renn-Woche. Carb Load Fr+Sa, Frühstück bis 7 Uhr, Pacing nach Zwischenzeiten + Puls.",
}


def splice(html, weeks, starts):
    weeks_js = "const weeks = " + json.dumps(weeks, ensure_ascii=False, indent=2) + ";"
    html, n1 = re.subn(r"const weeks = \[.*?\n\];", lambda m: weeks_js, html, count=1, flags=re.DOTALL)
    html, n2 = re.subn(r"const weekStarts = \[.*?\];",
                       lambda m: "const weekStarts = " + json.dumps(starts) + ";", html, count=1)
    html, n3 = re.subn(r"const MARATHON = new Date\('[\d-]+'\);",
                       lambda m: f"const MARATHON = new Date('{RACE.isoformat()}');", html, count=1)
    if (n1, n2, n3) != (1, 1, 1):
        raise SystemExit(f"Splice fehlgeschlagen: weeks={n1} weekStarts={n2} MARATHON={n3}")
    return html


if __name__ == "__main__":
    weeks, starts = build()
    with open("index.html", encoding="utf-8") as f:
        html = f.read()
    html = splice(html, weeks, starts)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    peak = max((km_of(d["title"]), w["label"]) for w in weeks for d in w["days"] if d.get("longrun"))
    print(f"OK: {len(weeks)} Wochen ({starts[0]} – {starts[-1]}), Peak-Longrun {peak[0]} km in {peak[1]}")
