#!/usr/bin/env python3
"""Einmaliger Garmin-Login fuer das Dashboard der Frau (moderne garminconnect-API).

MUSS mit aktuellem Python laufen (das System-Python 3.9 ist zu alt fuer Garmins
neuen Login). Deshalb per uv starten:

    ~/.local/bin/uv run --python 3.13 --with garminconnect connect_frau.py

Speichert die Sitzung in ~/.garmin_session_frau (getrennt von Samuels Sitzung).
Der Anzeigename wird als Sidecar ~/.garmin_session_frau.name abgelegt, damit der
Sync (der die Sitzung ueber client.loads laedt) die API-URLs bauen kann.
"""
import os, sys, getpass
from datetime import date

from garminconnect import Garmin

TOKEN_PATH = os.path.expanduser("~/.garmin_session_frau")
NAME_PATH = TOKEN_PATH + ".name"

email = input("Garmin E-Mail (deiner Frau): ").strip()
password = getpass.getpass("Garmin Passwort (wird nicht angezeigt): ")

print("\nAnmelden bei Garmin Connect …")
try:
    garmin = Garmin(email=email, password=password, return_on_mfa=True)
    res1, res2 = garmin.login()
    if res1 == "needs_mfa":
        code = input("\nGarmin-Verifizierungscode (E-Mail/App) eingeben: ").strip()
        garmin.resume_login(res2, code)
except Exception as e:
    print(f"\nFEHLER beim Login: {e}")
    sys.exit(1)

# Sitzung sichern (base64-String aus der neuen garminconnect-Bibliothek)
session_data = garmin.client.dumps()
if not session_data or len(session_data) < 20:
    print("\nFEHLER: Login lieferte keine gueltige Sitzung. Bitte nochmal versuchen.")
    sys.exit(1)

display_name = getattr(garmin, "display_name", None) or ""
full_name = getattr(garmin, "full_name", None) or ""

tmp = TOKEN_PATH + ".tmp"
with open(tmp, "w") as f:
    f.write(session_data)
os.replace(tmp, TOKEN_PATH)
if display_name:
    with open(NAME_PATH, "w") as f:
        f.write(display_name)

print(f"\nLogin erfolgreich! Sitzung gespeichert: {TOKEN_PATH}")
if full_name:
    print(f"Angemeldet als: {full_name}")

# ── Genau die Lade-Route testen, die der Sync spaeter nutzt ──────────────────
# (frische Garmin-Instanz, Sitzung aus dem gespeicherten String laden)
print("\nTeste die Sync-Lade-Route …")
try:
    g2 = Garmin()
    g2.client.loads(session_data)
    try:
        g2._load_profile_and_settings()
    except Exception:
        pass
    if not getattr(g2, "display_name", None) and display_name:
        g2.display_name = display_name
    rhr = g2.get_stats(date.today().isoformat()).get("restingHeartRate")
    print(f"  OK – Sync kann sich anmelden. Ruhepuls heute: {rhr}")
except Exception as e:
    print(f"  WARNUNG: Sync-Lade-Route scheiterte: {e}")
    print("  (Sitzung ist trotzdem gespeichert – bitte Claude Bescheid geben.)")

# ── Zyklusdaten pruefen (Natural Cycles -> Garmin) ──────────────────────────
print("\nPruefe Zyklusdaten (Natural Cycles -> Garmin Connect) …")
try:
    today = date.today().isoformat()
    day = garmin.get_menstrual_data_for_date(today)
    if day:
        phase = day.get("currentPhase") or day.get("phaseType") or day.get("phase")
        cday = day.get("cycleDayNumber") or day.get("dayInCycle")
        print(f"  Zyklusdaten vorhanden! Phase: {phase}, Zyklustag: {cday}")
    else:
        print("  Keine Zyklusdaten fuer heute – evtl. traegt Natural Cycles noch nicht"
              " nach Garmin ein. (Pruefen wir beim Aufbau des Dashboards.)")
except Exception as e:
    print(f"  Zyklus-Hinweis: {e}")

print("\nFertig. Sag Claude 'weiter mit dem Frau-Dashboard', dann baut er es.")
