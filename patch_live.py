#!/usr/bin/env python3
"""Einmaliger Patch der Live-Seite:
- HRV-Historie mit korrektem lastNightAvg neu laden
- heutige GARMIN_DATA-Werte (HRV, Body Battery) korrigieren
- Texte plan-konform setzen (heute Ruhetag), bis der nächste Workflow mit
  dem verbesserten Sonnet-Prompt läuft."""
import re, json
from datetime import date, timedelta
from update_plan import garmin_login, load_history, save_history, backfill_history

html_path = "index.html"
with open(html_path, encoding="utf-8") as f:
    html = f.read()

api = garmin_login()
today = date.today()

# 1) HRV-Historie komplett neu (lastNightAvg statt Spitzenwert)
history = load_history(html)
history["hrv"] = []  # leeren → backfill holt alle 30 Tage neu mit lastNightAvg
history = backfill_history(api, history, today, days=30)
html = save_history(html, history)
print(f"HRV-Historie neu: {[x['v'] for x in history['hrv'][:6]]} …")

# 2) Heutige Werte korrigieren
yesterday = (today - timedelta(days=1)).isoformat()
hrv = api.get_hrv_data(yesterday)
s = (hrv or {}).get("hrvSummary", {})
hrv_avg = s.get("lastNightAvg") or s.get("lastNight5MinHigh")
hrv_status = s.get("status")

bb_data = api.get_body_battery(yesterday, today.isoformat())
today_levels, all_levels = [], []
for day in (bb_data or []):
    d_date = day.get("date") if isinstance(day, dict) else None
    for pair in (day.get("bodyBatteryValuesArray") or []):
        if isinstance(pair, list) and len(pair) >= 2 and pair[1] is not None:
            all_levels.append(pair[1])
            if d_date == today.isoformat():
                today_levels.append(pair[1])
bb_peak = max(today_levels) if today_levels else (max(all_levels) if all_levels else None)

# 3) GARMIN_DATA patchen
m = re.search(r"(window\.GARMIN_DATA = )({.*?})(;)", html, re.DOTALL)
data = json.loads(m.group(2))
data["hrv_value"] = hrv_avg
data["hrv_status"] = hrv_status
if bb_peak:
    data["body_battery"] = bb_peak

# Plan-konforme Texte (heute = Ruhetag im W1-Plan)
data["recommendation"] = (
    "Heute ist Ruhetag – kein Laufen, kein Rad. Deine Erholung ist gut "
    "(HRV ausgeglichen), aber nach den Belastungen der letzten Tage braucht "
    "der Körper die Pause; optional lockere Mobilität oder ein Spaziergang."
)
data["training_intensity"] = "Ruhe"
data["run_feedback"] = (
    f"Solider 7,2-km-Lauf bei 7:42/km – die 142 bpm zeigen aber oberen "
    f"GA1/GA2-Bereich, nicht reines Zone 2. Die nächsten Läufe bewusst "
    f"langsamer (8:30–9:00/km): so sinkt der Puls Richtung 130–135 und du "
    f"baust effizienter Grundlagenausdauer auf."
)
# on_track konsistent machen: Finish 5:05 > 5:00 → Score < 70
data["on_track_score"] = 63
data["on_track_note"] = (
    "Mit aktuell ~5:05 h liegst du knapp über dem 5-Stunden-Ziel – machbar, "
    "aber noch nicht gesichert. Größter Hebel: mehr Lauf-Kilometer (zurzeit "
    "viel Rad, wenig Lauf) in den kommenden Wochen."
)

new_block = m.group(1) + json.dumps(data, ensure_ascii=False, indent=2) + m.group(3)
html = html[:m.start()] + new_block + html[m.end():]

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

print(f"Gepatcht: HRV={hrv_avg} ({hrv_status}), Body Battery Peak={bb_peak}, "
      f"on_track=63, Ruhetag-Empfehlung gesetzt.")
