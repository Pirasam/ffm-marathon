#!/usr/bin/env python3
"""Lokaler Garmin-Sync: holt alle Kennzahlen und schreibt sie nach garmin_data.json.

Laeuft auf dem Mac (launchd, taeglich). Ruft NIE Claude auf und braucht keinen
API-Key. Die Cloud (GitHub Actions) liest nur noch die JSON.

Wichtig: Bei einem Garmin-Fehler wird die bestehende garmin_data.json NICHT
ueberschrieben und der Exit-Code ist != 0. Lieber alte gute Daten behalten als
gute durch leere ersetzen.

Aufruf:
    python3 sync_garmin.py            # normaler Sync
    python3 sync_garmin.py --dry-run  # nur anzeigen, nichts schreiben
"""
import json
import os
import sys
from datetime import date, datetime

from garmin_client import (garmin_login, fetch_garmin_metrics,
                           backfill_history, update_history,
                           backfill_efficiency, merge_efficiency, compute_efficiency,
                           backfill_vo2max_monthly,
                           compute_durability, compute_aerobic_base,
                           compute_economy, backfill_economy)
from profiles import get_profile

REPO_DIR = os.path.dirname(os.path.abspath(__file__))

# Profil aus --profile NAME (Default: samuel = altes Verhalten, gleiche Pfade).
def _arg_profile():
    for i, a in enumerate(sys.argv):
        if a == "--profile" and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return "samuel"

PROFILE = _arg_profile()
_P = get_profile(PROFILE)
TOKEN_PATH = _P["token"]
DATA_PATH = os.path.join(REPO_DIR, _P["data"])

EMPTY_HISTORY = {"hrv": [], "rhr": [], "weight": [], "weekly_km": [],
                 "run_dyn": [], "vo2max": [], "efficiency": [],
                 "durability": [], "vo2max_monthly": []}


def load_existing():
    """Bestehende Daten laden (fuer Historie und als Fallback)."""
    try:
        with open(DATA_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"WARNUNG: garmin_data.json unlesbar ({e}) – starte mit leerer Historie.")
        return {}


def main():
    dry_run = "--dry-run" in sys.argv
    today = date.today()
    existing = load_existing()
    history = existing.get("history") or dict(EMPTY_HISTORY)

    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Garmin-Sync ({PROFILE}) startet …")

    try:
        api = garmin_login(token_path=TOKEN_PATH)
        metrics = fetch_garmin_metrics(api)
    except Exception as e:
        print(f"FEHLER: Garmin-Abruf fehlgeschlagen: {e}")
        print("Bestehende garmin_data.json bleibt unveraendert.")
        return 1

    # Selbst-Erneuerung: Garmin gibt bei jedem Login/Refresh einen NEUEN
    # 30-Tage-Token aus. Speichern wir ihn zurueck, lebt die Sitzung ewig weiter
    # – solange der Mac mindestens einmal im Monat laeuft. Kein generate_session,
    # kein GitHub-Secret mehr noetig.
    try:
        tokenstore = TOKEN_PATH
        # Alte Lib: api.garth.dumps(); neue Lib (Frau): api.client.dumps()
        fresh = api.garth.dumps() if hasattr(api, "garth") else api.client.dumps()
        tmp = tokenstore + ".tmp"
        with open(tmp, "w") as f:
            f.write(fresh)
        os.replace(tmp, tokenstore)
        print("Garmin-Sitzung erneuert und zurueckgespeichert (~30 Tage).")
    except Exception as e:
        print(f"WARNUNG: Konnte Sitzung nicht zurueckspeichern ({e}).")

    # Harte Plausibilitaetspruefung: ohne Kerndaten nichts ueberschreiben
    core = [metrics.get("resting_hr"), metrics.get("hrv_value"), metrics.get("sleep_hours")]
    if all(v is None for v in core):
        print(f"FEHLER: Keine Kerndaten erhalten (Ruhepuls/HRV/Schlaf alle leer). "
              f"API-Fehler: {metrics.get('_errors')}")
        print("Bestehende garmin_data.json bleibt unveraendert.")
        return 1

    # Historie auffuellen und fortschreiben
    try:
        history = backfill_history(api, history, today)
    except Exception as e:
        print(f"WARNUNG: Backfill fehlgeschlagen ({e}) – nutze bestehende Historie.")

    # VO2max-Luecke aus Historie fuellen (Ruhetage liefern oft nichts)
    if not metrics.get("vo2max") and history.get("vo2max"):
        metrics["vo2max"] = history["vo2max"][0]["v"]
        metrics["vo2max_carried"] = True
        print(f"VO2max aus Historie uebernommen: {metrics['vo2max']}")

    history = update_history(history, metrics, today.isoformat(),
                             metrics.get("weekly_running", {}))

    # Laufeffizienz (12 Monate): einmal backfillen, dann inkrementell fortschreiben.
    try:
        history = backfill_efficiency(api, history, today)
        history = merge_efficiency(history, metrics.get("recent_activities"))
        metrics["efficiency"] = compute_efficiency(history.get("efficiency") or [], today)
        history = backfill_vo2max_monthly(api, history, today)
        if metrics.get("efficiency") is not None:
            metrics["efficiency"]["vo2max"] = history.get("vo2max_monthly") or []
    except Exception as e:
        print(f"WARNUNG: Effizienz-Berechnung fehlgeschlagen ({e}).")
        metrics["efficiency"] = (existing.get("metrics") or {}).get("efficiency")

    # Marathon-Indikatoren: Durability, aerobe Basis, Laufoekonomie
    try:
        history = compute_durability(api, history, today)
        history = backfill_economy(api, history, today)
        eff_runs = (metrics.get("efficiency") or {}).get("runs") or []
        metrics["marathon"] = {
            "durability": history.get("durability") or [],
            "aerobic_base": compute_aerobic_base(eff_runs, today),
            "economy": compute_economy(history.get("run_dyn") or [], today),
            "generated": today.isoformat(),
        }
    except Exception as e:
        print(f"WARNUNG: Marathon-Indikatoren fehlgeschlagen ({e}).")
        metrics["marathon"] = (existing.get("metrics") or {}).get("marathon")

    # Wie lange traegt der Garmin-Login noch? Der Refresh-Token laeuft nach
    # ~30 Tagen ab; danach hilft nur generate_session.py. Rechtzeitig warnen.
    token_days = None
    try:
        import base64
        raw = os.environ.get("GARMIN_SESSION_DATA", "").strip()
        if not raw:
            with open(TOKEN_PATH) as f:
                raw = f.read().strip()
        parts = json.loads(base64.b64decode(raw))
        o2 = parts[1] if len(parts) > 1 and isinstance(parts[1], dict) else {}
        rexp = o2.get("refresh_token_expires_at")
        if rexp:
            import time
            token_days = round((rexp - time.time()) / 86400, 1)
            if token_days < 7:
                print(f"WARNUNG: Garmin-Login laeuft in {token_days} Tagen ab – "
                      f"'python3 generate_session.py' ausfuehren.")
            else:
                print(f"Garmin-Login noch {token_days} Tage gueltig.")
    except Exception:
        pass

    payload = {
        "synced_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "sync_date": today.isoformat(),
        "token_days_left": token_days,
        "metrics": metrics,
        "history": history,
    }

    if dry_run:
        summary = {k: metrics.get(k) for k in
                   ("hrv_value", "resting_hr", "sleep_hours", "body_battery",
                    "training_readiness", "weight_kg", "vo2max")}
        print("DRY-RUN – wuerde schreiben:")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"Historie: " + ", ".join(f"{k}={len(v)}" for k, v in history.items()))
        return 0

    os.makedirs(os.path.dirname(DATA_PATH) or ".", exist_ok=True)
    tmp = DATA_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_PATH)  # atomar

    print(f"OK: garmin_data.json geschrieben. "
          f"HRV {metrics.get('hrv_value')}, Ruhepuls {metrics.get('resting_hr')}, "
          f"Schlaf {metrics.get('sleep_hours')}h, "
          f"Historie hrv={len(history.get('hrv', []))} rhr={len(history.get('rhr', []))}")
    if metrics.get("_errors"):
        print(f"Hinweis – einzelne API-Fehler: {metrics['_errors']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
