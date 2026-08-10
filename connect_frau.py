#!/usr/bin/env python3
"""Einmaliger Garmin-Login fuer das Dashboard der Frau.

Speichert die Sitzung in ~/.garmin_session_frau – getrennt von Samuels
~/.garmin_session, damit beide Profile nebeneinander laufen.

Ausfuehren (deine Frau gibt IHREN Garmin-Login ein):
    python3 connect_frau.py
"""
import os, sys, base64, json
from datetime import date, timedelta

try:
    from garminconnect import Garmin
except ImportError:
    print("FEHLER: garminconnect nicht installiert – 'pip3 install garminconnect'")
    sys.exit(1)

TOKEN_PATH = os.path.expanduser("~/.garmin_session_frau")

email = input("Garmin E-Mail (deiner Frau): ").strip()
import getpass
password = getpass.getpass("Garmin Passwort (wird nicht angezeigt): ")

print("\nAnmelden bei Garmin Connect …")
api = Garmin(email, password)

def get_mfa():
    print("\nGarmin hat einen Verifizierungscode per E-Mail/App gesendet.")
    return input("Code eingeben: ").strip()

try:
    api.login(prompt_mfa=get_mfa)
except TypeError:
    api.login()
except Exception as e:
    print(f"\nFEHLER beim Login: {e}")
    sys.exit(1)

session_data = api.garth.dumps()
decoded = json.loads(base64.b64decode(session_data).decode())
if len(decoded) < 2 or decoded[1] is None:
    print("\nFEHLER: Login lieferte keine Tokens. Bitte nochmal versuchen.")
    sys.exit(1)

tmp = TOKEN_PATH + ".tmp"
with open(tmp, "w") as f:
    f.write(session_data)
os.replace(tmp, TOKEN_PATH)
print(f"\nLogin erfolgreich! Sitzung gespeichert: {TOKEN_PATH}")

# Kurzer Funktionstest
y = (date.today() - timedelta(days=1)).isoformat()
try:
    rhr = api.get_stats(date.today().isoformat()).get("restingHeartRate")
    s = api.get_hrv_data(y).get("hrvSummary", {}) or {}
    print(f"Test OK – Ruhepuls {rhr}, HRV {s.get('lastNightAvg')}")
except Exception as e:
    print(f"Test-Hinweis: {e}")

print("\nFertig. Sag Claude Bescheid, dann baut er das Dashboard.")
