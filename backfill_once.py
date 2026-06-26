#!/usr/bin/env python3
"""Einmaliges Nachfüllen der HRV-, Ruhepuls- und Gewichts-Historie aus Garmin.
Lässt GARMIN_DATA (Empfehlung/Feedback) unangetastet – aktualisiert NUR GARMIN_HISTORY."""
import json
from datetime import date, timedelta
from update_plan import garmin_login, load_history, backfill_history, save_history

html_path = "index.html"
with open(html_path, encoding="utf-8") as f:
    html = f.read()

api = garmin_login()
today = date.today()
history = load_history(html)

# HRV + Ruhepuls 30 Tage
history = backfill_history(api, history, today, days=30)

# Gewicht 90 Tage – get_body_composition liefert die volle Historie
ninety = (today - timedelta(days=90)).isoformat()
try:
    comp = api.get_body_composition(ninety, today.isoformat())
    entries = (comp or {}).get("dateWeightList") or []
    wbyd = {}
    for e in entries:
        d_str = e.get("calendarDate") or e.get("date") or ""
        raw = e.get("weight")
        if d_str and raw:
            wbyd[d_str] = round(raw / 1000, 1)
    existing = {x["d"]: x for x in history.get("weight", [])}
    for d_str, kg in wbyd.items():
        existing[d_str] = {"d": d_str, "v": kg}
    history["weight"] = sorted(existing.values(), key=lambda x: x["d"], reverse=True)[:60]
    print(f"Gewicht: {len(wbyd)} Einträge aus Garmin")
except Exception as e:
    print(f"Gewicht-Fehler: {e}")

html = save_history(html, history)
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

print(f"\nHistorie aktualisiert: HRV={len(history.get('hrv',[]))}, "
      f"RHR={len(history.get('rhr',[]))}, Gewicht={len(history.get('weight',[]))} Punkte")
