#!/usr/bin/env python3
"""
Garmin-Session-Tokens generieren und als GitHub Secret speichern.

Lokal ausführen:
    python3 generate_session.py

Oder im Browser via GitHub Codespaces:
    github.com/Pirasam/ffm-marathon → Code → Codespaces → Create codespace on main
    Dann im Terminal: python3 generate_session.py
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

def get_mfa():
    print("\nGarmin hat einen Verifizierungscode per E-Mail gesendet.")
    return input("Code eingeben: ").strip()

print("\nAnmelden bei Garmin Connect …")
api = Garmin(email, password)

try:
    api.login(prompt_mfa=get_mfa)
except TypeError:
    # Ältere Version ohne prompt_mfa-Parameter
    api.login()
except Exception as e:
    print(f"\nFEHLER beim Login: {e}")
    print("\nMögliche Ursachen:")
    print("- E-Mail oder Passwort falsch")
    print("- Garmin Connect nicht erreichbar")
    print("- Verifizierungscode falsch eingegeben")
    sys.exit(1)

try:
    print(f"\nErfolgreich angemeldet als: {api.display_name}")
except Exception:
    print("\nAngemeldet (Display-Name nicht abrufbar)")

session_data = api.garth.dumps()

# Lokal speichern für Tests
import os
session_path = os.path.expanduser("~/.garmin_session")
with open(session_path, "w") as f:
    f.write(session_data)
print(f"Session lokal gespeichert: {session_path}")

# Schneller API-Test
print("\nTeste Garmin API-Calls …")
from datetime import date, timedelta
yesterday = (date.today() - timedelta(days=1)).isoformat()
today_str = date.today().isoformat()

try:
    hrv = api.get_hrv_data(yesterday)
    s = hrv.get("hrvSummary", {})
    print(f"  HRV: {s.get('lastNight')} ms, Status: {s.get('status')}")
except Exception as e:
    print(f"  HRV FEHLER: {e}")

try:
    stats = api.get_stats(today_str)
    print(f"  Body Battery: {stats.get('bodyBatteryMostRecentValue')}, RHR: {stats.get('restingHeartRateValue')}")
except Exception as e:
    print(f"  Stats FEHLER: {e}")

try:
    sleep = api.get_sleep_data(yesterday)
    dto = sleep.get("dailySleepDTO", {})
    h = (dto.get("sleepTimeSeconds") or 0) // 3600
    print(f"  Schlaf: {h}h")
except Exception as e:
    print(f"  Schlaf FEHLER: {e}")

print("\n" + "=" * 60)
print("GARMIN_SESSION_DATA — als GitHub Secret speichern:")
print("=" * 60)
print(session_data)
print("=" * 60)

print("""
Nächste Schritte:
1. Den Text oben komplett kopieren
2. github.com/Pirasam/ffm-marathon
   → Settings → Secrets and variables → Actions
   → "New repository secret"
3. Name:  GARMIN_SESSION_DATA
   Value: (kopierten Text einfügen)
4. "Add secret" speichern
5. Actions → "Run workflow" triggern

Die Session ist ~60 Tage gültig.
""")
