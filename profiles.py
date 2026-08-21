#!/usr/bin/env python3
"""Profile fuer mehrere Personen auf einem Mac / in einem Repo.

Jedes Profil hat eigene Garmin-Sitzung, eigene Datendatei und eigenes Dashboard.
Samuels Profil behaelt exakt die alten Pfade -> nichts an seinem Setup aendert sich.
"""
import os

PROFILES = {
    "samuel": {
        "token": os.path.expanduser("~/.garmin_session"),
        "data": "garmin_data.json",
        "html": "index.html",
    },
    "frau": {
        "token": os.path.expanduser("~/.garmin_session_frau"),
        "data": "frau/garmin_data.json",
        "html": "frau/index.html",
    },
}


def get_profile(name):
    if name not in PROFILES:
        raise SystemExit(f"Unbekanntes Profil '{name}'. Bekannt: {', '.join(PROFILES)}")
    return PROFILES[name]
