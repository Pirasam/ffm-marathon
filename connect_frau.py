#!/usr/bin/env python3
"""Einmaliger Garmin-Login fuer das Dashboard der Frau (ueber garth direkt).

Nutzt garths eigenen, aktuellen Login (die alte garminconnect-Huelle scheitert
an Garmins neuem SSO mit 401). Speichert die Sitzung in ~/.garmin_session_frau –
getrennt von Samuels ~/.garmin_session – im selben Format, das der Sync liest.

Ausfuehren (deine Frau gibt IHREN Garmin-Login ein):
    python3 connect_frau.py
"""
import os, sys, getpass, base64, json

try:
    import garth
except ImportError:
    print("FEHLER: garth nicht installiert – 'pip3 install -U garth garminconnect'")
    sys.exit(1)

TOKEN_PATH = os.path.expanduser("~/.garmin_session_frau")

email = input("Garmin E-Mail (deiner Frau): ").strip()
password = getpass.getpass("Garmin Passwort (wird nicht angezeigt): ")

def get_mfa():
    print("\nGarmin hat einen Verifizierungscode per E-Mail/App gesendet.")
    return input("Code eingeben: ").strip()

print("\nAnmelden bei Garmin Connect (ueber garth) …")
try:
    garth.login(email, password, prompt_mfa=get_mfa)
except TypeError:
    # aeltere garth-Signatur ohne prompt_mfa
    garth.login(email, password)
except Exception as e:
    print(f"\nFEHLER beim Login: {e}")
    print("Falls weiterhin 401: bitte kurz Bescheid geben – dann brauchen wir ein neueres Python.")
    sys.exit(1)

# Session im base64-Format sichern (kompatibel mit garth.loads im Sync)
session_data = garth.client.dumps()
decoded = json.loads(base64.b64decode(session_data).decode())
if len(decoded) < 2 or decoded[1] is None:
    print("\nFEHLER: Login lieferte keine gueltigen Tokens. Bitte nochmal versuchen.")
    sys.exit(1)

tmp = TOKEN_PATH + ".tmp"
with open(tmp, "w") as f:
    f.write(session_data)
os.replace(tmp, TOKEN_PATH)
print(f"\nLogin erfolgreich! Sitzung gespeichert: {TOKEN_PATH}")

# Kurzer Funktionstest ueber unsere Pipeline
try:
    from garmin_client import garmin_login, fetch_garmin_metrics
    api = garmin_login(token_path=TOKEN_PATH)
    from datetime import date
    rhr = api.get_stats(date.today().isoformat()).get("restingHeartRate")
    print(f"Test OK – Ruhepuls heute: {rhr}")
except Exception as e:
    print(f"Test-Hinweis (Login trotzdem gespeichert): {e}")

print("\nFertig. Sag Claude 'weiter mit dem Frau-Dashboard', dann baut er es.")
