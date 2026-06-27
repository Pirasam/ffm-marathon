#!/usr/bin/env python3
"""Einmaliger Patch: Laufdynamik in die Live-Seite ergänzen.
Lässt die vom täglichen Workflow generierten Felder (Empfehlung, HRV, on_track …)
unangetastet – fügt nur run_dynamics + run_dyn-Historie hinzu."""
import re, json
from datetime import date
from update_plan import garmin_login, load_history, save_history, fetch_run_dynamics

html_path = "index.html"
with open(html_path, encoding="utf-8") as f:
    html = f.read()

api = garmin_login()
today = date.today()

# Laufaktivitäten der letzten ~6 Wochen für Dynamik + Historie
acts = api.get_activities(0, 30)
running = [a for a in acts if "running" in (a.get("activityType") or {}).get("typeKey", "")
           or "trail" in (a.get("activityType") or {}).get("typeKey", "")]
dyn = fetch_run_dynamics(api, running)

# 1) Historie ergänzen
history = load_history(html)
if dyn and dyn.get("history"):
    existing = {x["d"]: x for x in history.get("run_dyn", [])}
    for d_str, vals in dyn["history"].items():
        existing[d_str] = {"d": d_str, **vals}
    history["run_dyn"] = sorted(existing.values(), key=lambda x: x["d"], reverse=True)[:40]
    html = save_history(html, history)
    print(f"run_dyn-Historie: {len(history['run_dyn'])} Läufe")

# 2) GARMIN_DATA.run_dynamics setzen (ohne verschachtelte Historie)
m = re.search(r"(window\.GARMIN_DATA = )({.*?})(;)", html, re.DOTALL)
data = json.loads(m.group(2))
if dyn:
    data["run_dynamics"] = {k: v for k, v in dyn.items() if k != "history"}
new_block = m.group(1) + json.dumps(data, ensure_ascii=False, indent=2) + m.group(3)
html = html[:m.start()] + new_block + html[m.end():]

with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

print("Laufdynamik gepatcht:", json.dumps(data.get("run_dynamics"), ensure_ascii=False))
