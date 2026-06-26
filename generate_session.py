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
api = Garmin(email, password, prompt_mfa=get_mfa)

try:
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
