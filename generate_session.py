#!/usr/bin/env python3
"""
Einmalig lokal ausführen → Garmin-Tokens generieren → als GitHub Secret speichern.

Ausführen:
    GARMIN_EMAIL=deine@email.de GARMIN_PASSWORD=deinPasswort python generate_session.py
oder einfach:
    python generate_session.py
(fragt dann interaktiv nach E-Mail und Passwort)
"""
import os, sys

try:
    from garminconnect import Garmin
except ImportError:
    print("FEHLER: garminconnect nicht installiert. Bitte: pip install garminconnect")
    sys.exit(1)

email = os.environ.get("GARMIN_EMAIL") or input("Garmin E-Mail: ")
password = os.environ.get("GARMIN_PASSWORD") or input("Garmin Passwort: ")

print("\nAnmelden bei Garmin Connect …")
api = Garmin(email, password)

try:
    api.login()
except Exception as e:
    print(f"\nFEHLER beim Login: {e}")
    print("Prüfe E-Mail/Passwort und ob Garmin Connect erreichbar ist.")
    sys.exit(1)

try:
    print(f"Erfolgreich angemeldet als: {api.display_name}")
except Exception:
    print("Angemeldet (Display-Name nicht abrufbar)")

session_data = api.garth.dumps()

print("\n" + "=" * 60)
print("GARMIN_SESSION_DATA — diesen Wert als GitHub Secret speichern:")
print("=" * 60)
print(session_data)
print("=" * 60)

print("""
Nächste Schritte:
1. Obigen Text komplett kopieren (eine Zeile JSON)
2. GitHub → Repository → Settings → Secrets and variables → Actions
3. "New repository secret" klicken
4. Name:  GARMIN_SESSION_DATA
5. Value: (kopierten Text einfügen)
6. "Add secret" speichern

Die Session ist ~60 Tage gültig. Danach dieses Script neu ausführen.
""")
