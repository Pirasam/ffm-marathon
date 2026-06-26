#!/usr/bin/env python3
"""
Garmin-Session generieren und als GitHub Secret speichern.

Ausführen:
    python3 generate_session.py

Dann den Inhalt von garmin_secret.txt als GitHub Secret 'GARMIN_SESSION_DATA' speichern.
"""
import os, sys

try:
    from garminconnect import Garmin
except ImportError:
    print("FEHLER: garminconnect nicht installiert.")
    print("Bitte ausführen: pip3 install garminconnect")
    sys.exit(1)

email = os.environ.get("GARMIN_EMAIL") or input("Garmin E-Mail: ")
password = os.environ.get("GARMIN_PASSWORD") or input("Garmin Passwort: ")

print("\nAnmelden bei Garmin Connect …")
api = Garmin(email, password)

def get_mfa():
    print("\nGarmin hat einen Verifizierungscode per E-Mail gesendet.")
    return input("Code eingeben: ").strip()

try:
    api.login(prompt_mfa=get_mfa)
except TypeError:
    api.login()
except Exception as e:
    print(f"\nFEHLER beim Login: {e}")
    sys.exit(1)

print("Login erfolgreich!")

session_data = api.garth.dumps()

# Prüfen ob gültige Tokens vorhanden
import base64, json
decoded = json.loads(base64.b64decode(session_data).decode())
if decoded[1] is None:
    print("\nFEHLER: Login hat keine Tokens geliefert (oauth2_token ist leer).")
    print("Bitte nochmal versuchen.")
    sys.exit(1)

print(f"Session-Tokens OK (oauth2_token vorhanden, {len(session_data)} Zeichen)")

# Lokal speichern
session_path = os.path.expanduser("~/.garmin_session")
with open(session_path, "w") as f:
    f.write(session_data)
print(f"Session lokal gespeichert: {session_path}")

# In separate Datei schreiben (für GitHub Secret)
secret_file = os.path.join(os.path.dirname(__file__), "garmin_secret.txt")
with open(secret_file, "w") as f:
    f.write(session_data)
print(f"Secret-Datei: {secret_file}")

# API-Test
print("\nTeste Garmin API-Calls …")
from datetime import date, timedelta
yesterday = (date.today() - timedelta(days=1)).isoformat()
today_str = date.today().isoformat()

ok_count = 0
for label, call in [
    ("HRV", lambda: api.get_hrv_data(yesterday).get("hrvSummary", {}).get("lastNight")),
    ("Body Battery", lambda: api.get_stats(today_str).get("bodyBatteryMostRecentValue")),
    ("Ruhepuls", lambda: api.get_stats(today_str).get("restingHeartRateValue")),
    ("Schlaf", lambda: round((api.get_sleep_data(yesterday).get("dailySleepDTO", {}).get("sleepTimeSeconds") or 0) / 3600, 1)),
]:
    try:
        val = call()
        print(f"  {label}: {val}")
        if val is not None:
            ok_count += 1
    except Exception as e:
        print(f"  {label}: FEHLER – {e}")

print(f"\n{ok_count}/4 API-Calls erfolgreich.")

print(f"""
{'='*60}
NÄCHSTE SCHRITTE:
{'='*60}
1. Öffne: {secret_file}
   (enthält NUR den Token-String, nichts anderes)

2. Inhalt komplett kopieren (eine lange Zeile)

3. GitHub → github.com/Pirasam/ffm-marathon
   → Settings → Secrets and variables → Actions
   → Secret 'GARMIN_SESSION_DATA' updaten/erstellen
   → Inhalt aus Datei einfügen → Speichern

4. Actions → 'Run workflow' → Daten sollten erscheinen!

Die Session ist ~60 Tage gültig.
{'='*60}
""")
