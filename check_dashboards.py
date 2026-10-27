#!/usr/bin/env python3
"""Automatische Pruefung der Dashboards (Kontrollschleife, Stufe 1).

Laeuft nach jedem Sync auf dem Mac (daily_sync*.sh) und taeglich in der Cloud
(Wartungs-Routine). Schreibt checks/<profil>.json; die Dashboards laden die
Datei beim Oeffnen nach und zeigen bei Problemen ein Banner.

Geprueft wird:
  - Daten: Alter, Sync-Fehler, fehlende Kernwerte, Plausibilitaet, Daten in
    der Zukunft, Wochen-km gegen die einzelnen Laeufe
  - Seite: im Headless-Browser gerendert – JavaScript-Fehler und Chart-Punkte
    ausserhalb der Achsen (per Selbsttest-Skript auf der Seite)
  - Samuels Seite: aktuelle Planwoche vorhanden, Renndatum, KI-Fehlerfeld

Aufruf:
  python3 check_dashboards.py --profile samuel [--html-from-origin] [--no-page]
  python3 check_dashboards.py --profile frau
Exit-Code 0 = keine Fehler (Warnungen erlaubt), 1 = mindestens ein Fehler.
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone

REPO = os.path.dirname(os.path.abspath(__file__))
PROFILES = {
    "samuel": {"data": "garmin_data.json", "html": "index.html"},
    "frau": {"data": "frau/garmin_data.json", "html": "frau/index.html"},
}
RACE_DATE = {"samuel": "2027-10-31", "frau": "2027-09-19"}


class Report:
    def __init__(self):
        self.issues = []

    def add(self, sev, code, msg):
        self.issues.append({"sev": sev, "code": code, "msg": msg})

    def err(self, code, msg):
        self.add("error", code, msg)

    def warn(self, code, msg):
        self.add("warn", code, msg)


def _iso_week(d):
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


# ── Daten ─────────────────────────────────────────────────────────────────────
def check_data(r, data, today, profile):
    m = data.get("metrics") or {}
    h = data.get("history") or {}

    # Alter
    try:
        synced = datetime.fromisoformat(data.get("synced_at"))
        age_h = (datetime.now(synced.tzinfo or timezone.utc) - synced).total_seconds() / 3600
        if age_h > 36:
            r.err("stale", f"Garmin-Daten sind {age_h:.0f} h alt – der Mac-Sync läuft nicht.")
    except Exception:
        r.err("stale", "Sync-Zeitpunkt fehlt oder ist unlesbar.")

    # Sync-Fehler, die der Sync selbst gemeldet hat
    for e in m.get("_errors") or []:
        r.warn("sync_error", f"Sync-Fehler: {e}")

    # Kernwerte, die normalerweise immer da sind
    for key, label in (("hr_zones", "HF-Zonen"), ("vo2max", "VO₂max"), ("efficiency", "Laufhistorie"),
                       ("marathon", "Indikatoren"), ("threshold", "Schwellentempo"),
                       ("run_dynamics", "Laufdynamik")):
        if not m.get(key):
            r.warn("missing", f"{label} fehlt in den Daten.")
    rd = m.get("run_dynamics") or {}
    if rd and rd.get("performance_condition") is None:
        r.warn("missing", "Leistungszustand des letzten Laufs fehlt.")
    for key, label in (("rhr", "Ruhepuls"), ("hrv", "HRV")):
        hist = h.get(key) or []
        if hist:
            last = max(x.get("d", "") for x in hist)
            if (today - date.fromisoformat(last)).days > 3:
                r.warn("missing", f"{label}: letzter Wert vom {last}.")

    # Plausibilitaet
    def rng(val, lo, hi, label):
        if val is not None and not (lo <= val <= hi):
            r.err("implausible", f"{label} unplausibel: {val}")
    rng(m.get("resting_hr"), 30, 100, "Ruhepuls")
    rng(m.get("hrv_value"), 5, 200, "HRV")
    rng(m.get("weight_kg"), 35, 160, "Gewicht")
    rng(m.get("vo2max"), 20, 80, "VO₂max")
    for t in m.get("threshold") or []:
        rng(t.get("pace_s"), 180, 720, f"Schwellentempo ({t.get('d')})")
    for w in h.get("weekly_km") or []:
        rng(w.get("v"), 0, 250, f"Wochen-km ({w.get('w')})")

    # Keine Daten in der Zukunft
    tomorrow = (today + timedelta(days=1)).isoformat()
    for key in ("hrv", "rhr", "weight", "efficiency", "durability"):
        for x in h.get(key) or []:
            if (x.get("d") or "") > tomorrow:
                r.err("future", f"Historie '{key}' enthält ein Datum in der Zukunft: {x.get('d')}")
                break

    # Wochen-km gegen die einzelnen Laeufe: die Wochensumme darf nicht kleiner
    # sein als die Summe der erfassten Laeufe (genau der Fehler vom 27.10.2026).
    # Laeufe sammeln; derselbe Lauf kann aus zwei Quellen mit leicht anderer
    # Rundung kommen (6,65 vs. 6,6 km) -> gleicher Tag und < 0,3 km Differenz = Duplikat.
    by_day = {}
    src = [(x.get("date"), x.get("dist") or 0) for x in ((m.get("efficiency") or {}).get("runs") or [])]
    src += [(a.get("date"), a.get("distance_km") or 0) for a in m.get("recent_activities") or []
            if "running" in (a.get("type") or "") or "trail" in (a.get("type") or "")]
    for d, km in src:
        lst = by_day.setdefault(d, [])
        if not any(abs(k - km) < 0.3 for k in lst):
            lst.append(km)
    per_week = {}
    for d, lst in by_day.items():
        try:
            wk = _iso_week(date.fromisoformat(d))
        except Exception:
            continue
        per_week[wk] = per_week.get(wk, 0) + sum(lst)
    weekly = {w["w"]: w["v"] for w in h.get("weekly_km") or []}
    for wk, km in sorted(weekly.items()):
        expect = per_week.get(wk, 0)
        if km + max(1.0, expect * 0.05) < expect:
            r.err("weekly_km", f"Wochen-km {wk}: Dashboard {km:g} km, Läufe ergeben {expect:.1f} km.")
    if weekly:
        ws = sorted(weekly)
        # Lueckenlosigkeit der letzten 12 Wochen
        cur = today - timedelta(days=today.weekday())
        expected = {_iso_week(cur - timedelta(weeks=k)) for k in range(12)}
        missing = sorted(expected - set(ws))
        if missing:
            r.warn("weekly_km", f"Wochen-km: fehlende Wochen {', '.join(missing)}.")


# ── Samuels Seite (Plan/KI) ───────────────────────────────────────────────────
def check_samuel_html(r, html, today):
    m = re.search(r"const weekStarts = (\[.*?\]);", html)
    if not m:
        r.err("plan", "Wochenplan (weekStarts) nicht gefunden.")
    else:
        starts = json.loads(m.group(1))
        if not starts or not (starts[0] <= today.isoformat() < (date.fromisoformat(starts[-1]) + timedelta(days=7)).isoformat()):
            r.warn("plan", "Heute liegt außerhalb des Trainingsplans – Plan verlängern oder neues Ziel anlegen.")
    m = re.search(r"const MARATHON = new Date\('([\d-]+)'\)", html)
    if not m or m.group(1) != RACE_DATE["samuel"]:
        r.err("race_date", f"Renndatum im Dashboard ({m.group(1) if m else '–'}) ≠ {RACE_DATE['samuel']}.")
    m = re.search(r"window\.GARMIN_DATA\s*=\s*({.*?});\s*</script>", html, re.S)
    if not m:
        r.err("render", "GARMIN_DATA fehlt in index.html.")
        return
    g = json.loads(m.group(1))
    if g.get("_claude_error"):
        r.warn("claude", f"KI-Empfehlung fehlgeschlagen: {g['_claude_error'][:160]}")
    if not g.get("recommendation"):
        r.warn("claude", "Keine Tagesempfehlung vorhanden.")
    upd = g.get("updated")
    if upd and (today - date.fromisoformat(upd)).days > 2:
        r.err("render", f"Dashboard zuletzt am {upd} gerendert – Cloud-Rendering hängt.")


def check_frau_html(r, html, today, data):
    synced = (data.get("synced_at") or "")[:10]
    m = re.search(r'class="today"[^>]*data-day="([\d-]+)"', html)
    if not m:
        r.warn("render", "Tageskachel fehlt auf Carinas Seite.")
    elif synced and m.group(1) < synced:
        r.err("render", f"Carinas Seite wurde seit dem Sync ({synced}) nicht neu gerendert.")
    if RACE_DATE["frau"].split("-")[0] not in html or "Tegernsee" not in html:
        r.err("race_date", "Rennziel Tegernsee fehlt auf Carinas Seite.")


# ── Seite im Browser ──────────────────────────────────────────────────────────
def find_chrome():
    cands = [os.environ.get("CHROME_BIN"),
             "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
             shutil.which("google-chrome"), shutil.which("chromium"), shutil.which("chromium-browser")]
    cands += sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
    cands.append("/opt/pw-browsers/chromium")
    for c in cands:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


def check_page(r, html_path):
    chrome = find_chrome()
    if not chrome:
        r.warn("page", "Kein Browser gefunden – Seitenprüfung übersprungen.")
        return
    with tempfile.TemporaryDirectory() as tmp:
        try:
            out = subprocess.run(
                [chrome, "--headless=new", "--disable-gpu", "--no-sandbox", f"--user-data-dir={tmp}",
                 "--window-size=420,3000", "--virtual-time-budget=8000", "--dump-dom",
                 "file://" + os.path.abspath(html_path)],
                capture_output=True, text=True, timeout=120).stdout
        except Exception as e:
            r.warn("page", f"Browser-Render fehlgeschlagen: {e}")
            return
    m = re.search(r'<pre id="selfcheck"[^>]*>(.*?)</pre>', out, re.S)
    if not m or not m.group(1).strip():
        r.err("page", "Selbsttest der Seite lief nicht (Skriptfehler oder Chart.js nicht geladen).")
        return
    try:
        sc = json.loads(m.group(1).replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">"))
    except Exception:
        r.err("page", "Selbsttest-Ergebnis unlesbar.")
        return
    for e in sc.get("errors") or []:
        r.err("js_error", f"JavaScript-Fehler: {e[:200]}")
    for o in sc.get("outside") or []:
        r.err("chart", f"Chart '{o.get('chart')}': {o.get('n')} Punkt(e) außerhalb der Achsen.")
    if sc.get("charts", 0) == 0:
        r.warn("chart", "Keine Charts gefunden.")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    args = sys.argv[1:]
    profile = args[args.index("--profile") + 1] if "--profile" in args else "samuel"
    p = PROFILES[profile]
    today = date.today()
    r = Report()
    os.chdir(REPO)

    with open(p["data"], encoding="utf-8") as f:
        data = json.load(f)
    check_data(r, data, today, profile)

    html_path = p["html"]
    tmp_html = None
    if "--html-from-origin" in args:
        # Samuels Seite rendert die Cloud – geprueft wird der veroeffentlichte Stand.
        try:
            src = subprocess.check_output(["git", "show", f"origin/main:{p['html']}"]).decode()
            tmp_html = os.path.join(REPO, ".check_tmp.html")
            with open(tmp_html, "w", encoding="utf-8") as f:
                f.write(src)
            html_path = tmp_html
        except Exception as e:
            r.warn("page", f"Veröffentlichte Seite nicht lesbar ({e}) – prüfe lokale Kopie.")
    try:
        with open(html_path, encoding="utf-8") as f:
            html = f.read()
        if profile == "samuel":
            check_samuel_html(r, html, today)
        else:
            check_frau_html(r, html, today, data)
        if "--no-page" not in args:
            check_page(r, html_path)
    finally:
        if tmp_html and os.path.exists(tmp_html):
            os.remove(tmp_html)

    errors = [i for i in r.issues if i["sev"] == "error"]
    result = {"profile": profile, "checked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
              "ok": not errors, "issues": r.issues}
    os.makedirs("checks", exist_ok=True)
    with open(f"checks/{profile}.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    for i in r.issues:
        print(f"[{i['sev'].upper()}] {i['code']}: {i['msg']}")
    print(f"Prüfung {profile}: {'OK' if not errors else f'{len(errors)} Fehler'}, {len(r.issues) - len(errors)} Warnungen")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
