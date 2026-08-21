#!/usr/bin/env python3
"""Einmaliger Garmin-Login fuer das Dashboard der Frau (moderne garminconnect-API).

MUSS mit aktuellem Python laufen (das System-Python 3.9 ist zu alt fuer Garmins
neuen Login). Deshalb per uv starten:

    ~/.local/bin/uv run --python 3.13 --with garminconnect connect_frau.py

Speichert die Sitzung in ~/.garmin_session_frau (getrennt von Samuels Sitzung),
im base64-Format, das der Sync via garth.loads liest.
"""
import os, sys, getpass, base64, json
from datetime import date

from garminconnect import Garmin

TOKEN_PATH = os.path.expanduser("~/.garmin_session_frau")

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

# Sitzung sichern (base64, kompatibel mit garth.loads im Sync)
session_data = garmin.garth.dumps()
decoded = json.loads(base64.b64decode(session_data).decode())
if len(decoded) < 2 or decoded[1] is None:
    print("\nFEHLER: Login lieferte keine gueltigen Tokens. Bitte nochmal versuchen.")
    sys.exit(1)

tmp = TOKEN_PATH + ".tmp"
with open(tmp, "w") as f:
    f.write(session_data)
os.replace(tmp, TOKEN_PATH)
print(f"\nLogin erfolgreich! Sitzung gespeichert: {TOKEN_PATH}")

# Kurzer Funktionstest inkl. Zyklusdaten (Natural Cycles -> Garmin)
try:
    garmin.display_name = garmin.garth.profile.get("displayName")
    rhr = garmin.get_stats(date.today().isoformat()).get("restingHeartRate")
    print(f"Test OK – Ruhepuls heute: {rhr}")
    for m in ("get_menstrual_data_for_date", "get_menstrual_calendar_data"):
        if hasattr(garmin, m):
            print(f"Zyklus-Methode vorhanden: {m}")
except Exception as e:
    print(f"Test-Hinweis (Login trotzdem gespeichert): {e}")

print("\nFertig. Sag Claude 'weiter mit dem Frau-Dashboard', dann baut er es.")
