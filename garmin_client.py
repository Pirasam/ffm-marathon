#!/usr/bin/env python3
"""Garmin-Zugriff — wird NUR lokal ausgefuehrt.

Hintergrund: Garmin blockt den OAuth-Token-Refresh aus GitHub-Actions-IPs mit
429 (Too Many Requests). Lokal funktioniert er zuverlaessig. Deshalb laeuft der
Garmin-Abruf auf dem Mac (sync_garmin.py) und schreibt garmin_data.json ins Repo;
die Cloud rendert daraus nur noch das Dashboard.
"""
import os
import json
from datetime import date, timedelta
from collections import defaultdict

TOKENSTORE_PATH = os.path.expanduser("~/.garmin_session")


def garmin_login():
    from garminconnect import Garmin
    email = os.environ.get("GARMIN_EMAIL", "")
    password = os.environ.get("GARMIN_PASSWORD", "")
    session_secret = os.environ.get("GARMIN_SESSION_DATA", "").strip()

    print(f"Garmin: GARMIN_SESSION_DATA gesetzt={bool(session_secret)}, Laenge={len(session_secret)}")

    api = Garmin(email, password)

    # 1. GitHub Secret — kein Fresh-Login in CI (Garmin 429 auf CI-IPs)
    if session_secret:
        preview = session_secret[:40].replace('\n', '\\n')
        print(f"Garmin: Secret-Preview: {preview!r}")
        try:
            api.garth.loads(session_secret)
            api.display_name = api.garth.profile.get("displayName")
            print(f"Garmin: Session OK, Nutzer: {api.display_name}")
            return api
        except Exception as e:
            raise RuntimeError(f"GARMIN_SESSION_DATA ungueltig (erste 40 Zeichen: {preview!r}): {e}")

    # 2. Gecachte Session
    if os.path.exists(TOKENSTORE_PATH):
        try:
            with open(TOKENSTORE_PATH) as f:
                api.garth.loads(f.read())
            api.display_name = api.garth.profile.get("displayName")
            print(f"Garmin: gecachte Session OK, Nutzer: {api.display_name}")
            return api
        except Exception as e:
            print(f"Garmin: gecachte Session ungueltig: {e}")

    # 3. Kein Fresh-Login — wuerde in CI mit 429 scheitern
    raise RuntimeError(
        "Keine gueltige Garmin-Session. Bitte generate_session.py lokal ausfuehren "
        "und GARMIN_SESSION_DATA als GitHub Secret setzen."
    )


# ── Garmin data ───────────────────────────────────────────────────────────────

def fetch_garmin_metrics(api):
    today = date.today()
    yesterday = (today - timedelta(days=1)).isoformat()
    two_weeks_ago = (today - timedelta(days=14)).isoformat()
    today_str = today.isoformat()
    metrics = {}
    _errors = []

    # Sleep — Garmin indexiert die zuletzt geschlafene Nacht unter dem HEUTIGEN
    # Datum. Fallback auf gestern, falls morgens noch nicht synchronisiert.
    try:
        dto = {}
        for d in (today_str, yesterday):
            dto = (api.get_sleep_data(d) or {}).get("dailySleepDTO", {}) or {}
            if dto.get("sleepTimeSeconds"):
                break
        secs = dto.get("sleepTimeSeconds") or 0
        metrics["sleep_hours"] = round(secs / 3600, 1) if secs else None
        metrics["sleep_score"] = ((dto.get("sleepScores") or {}).get("overall") or {}).get("value")
    except Exception as e:
        print(f"Sleep error: {e}"); _errors.append(f"sleep: {e}")
        metrics["sleep_hours"] = None
        metrics["sleep_score"] = None

    # HRV — lastNightAvg ist der von Garmin angezeigte Nachtwert (40–50er-Bereich).
    # lastNight5MinHigh ist nur der Spitzenwert und liegt deutlich höher.
    # Ebenfalls unter dem heutigen Datum indexiert (Fallback: gestern).
    try:
        s = {}
        for d in (today_str, yesterday):
            s = (api.get_hrv_data(d) or {}).get("hrvSummary", {}) or {}
            if s.get("lastNightAvg") or s.get("lastNight5MinHigh"):
                break
        metrics["hrv_status"] = s.get("status")
        metrics["hrv_value"] = s.get("lastNightAvg") or s.get("lastNight5MinHigh")
        metrics["hrv_weekly_avg"] = s.get("weeklyAvg")
        bl = s.get("baseline") or {}
        metrics["hrv_balanced_low"] = bl.get("balancedLow")
        metrics["hrv_balanced_high"] = bl.get("balancedUpper")
    except Exception as e:
        print(f"HRV error: {e}"); _errors.append(f"hrv: {e}")
        metrics["hrv_status"] = None
        metrics["hrv_value"] = None
        metrics["hrv_weekly_avg"] = None
        metrics["hrv_balanced_low"] = None
        metrics["hrv_balanced_high"] = None

    # Daily stats (Stress, RHR)
    try:
        stats = api.get_stats(today_str)
        metrics["stress"] = stats.get("averageStressLevel")
        metrics["resting_hr"] = stats.get("restingHeartRate") or stats.get("restingHeartRateValue")
    except Exception as e:
        print(f"Stats error: {e}"); _errors.append(f"stats: {e}")
        metrics["stress"] = None
        metrics["resting_hr"] = None

    # Body Battery — Tages-Höchstwert (morgens nach dem Schlaf am höchsten).
    # get_body_battery liefert Tagesobjekte mit verschachteltem bodyBatteryValuesArray [[ts, level], …].
    try:
        bb_data = api.get_body_battery(yesterday, today_str)
        today_levels, all_levels = [], []
        for day in (bb_data or []):
            d_date = day.get("date") if isinstance(day, dict) else None
            for pair in (day.get("bodyBatteryValuesArray") or []):
                if isinstance(pair, list) and len(pair) >= 2 and pair[1] is not None:
                    all_levels.append(pair[1])
                    if d_date == today_str:
                        today_levels.append(pair[1])
        # Bevorzuge den heutigen Peak; sonst den jüngsten verfügbaren Tag
        peak = max(today_levels) if today_levels else (max(all_levels) if all_levels else None)
        metrics["body_battery"] = peak
        print(f"Body Battery Peak: {peak} (heute {len(today_levels)} Werte, gesamt {len(all_levels)})")
    except Exception as e:
        print(f"Body Battery error: {e}"); _errors.append(f"body_battery: {e}")
        try:
            metrics["body_battery"] = api.get_stats(today_str).get("bodyBatteryMostRecentValue")
        except Exception:
            metrics["body_battery"] = None

    # Training Readiness
    try:
        tr = api.get_training_readiness(today_str)
        if isinstance(tr, list) and tr:
            metrics["training_readiness"] = tr[0].get("score") or tr[0].get("trainingReadinessScore")
        else:
            metrics["training_readiness"] = None
    except Exception as e:
        print(f"Training readiness error: {e}"); _errors.append(f"readiness: {e}")
        metrics["training_readiness"] = None

    # Activities last 14 days (for weekly volume)
    try:
        acts = api.get_activities_by_date(two_weeks_ago, today_str, "")
        def _pace(dist_m, dur_s):
            if not dist_m or not dur_s:
                return None
            p = (dur_s / 60) / (dist_m / 1000)
            return round(p, 2)
        metrics["recent_activities"] = [
            {
                "name": a.get("activityName", ""),
                "type": (a.get("activityType") or {}).get("typeKey", ""),
                "date": (a.get("startTimeLocal") or "")[:10],
                "distance_km": round((a.get("distance") or 0) / 1000, 1),
                "duration_min": round((a.get("duration") or 0) / 60),
                "pace_min_km": _pace(a.get("distance"), a.get("duration")),
                "avg_hr": a.get("averageHR"),
            }
            for a in acts[:14]
        ]
        # Last run (for feedback section)
        metrics["last_run"] = next(
            (a for a in metrics["recent_activities"]
             if "running" in a.get("type", "") or "trail" in a.get("type", "")),
            None
        )
        # Weekly running km grouped by ISO week
        weekly = defaultdict(float)
        running_acts = []
        for a in acts:
            atype = (a.get("activityType") or {}).get("typeKey", "")
            if "running" in atype or "trail" in atype:
                d = date.fromisoformat((a.get("startTimeLocal") or today_str)[:10])
                wk = f"{d.year}-W{d.isocalendar()[1]:02d}"
                weekly[wk] += (a.get("distance") or 0) / 1000
                running_acts.append(a)
        metrics["weekly_running"] = {k: round(v, 1) for k, v in weekly.items()}

        # Laufdynamik des jüngsten Laufs (+ Historie der Kernwerte)
        metrics["run_dynamics"] = fetch_run_dynamics(api, running_acts)
    except Exception as e:
        print(f"Activities error: {e}"); _errors.append(f"activities: {e}")
        metrics["recent_activities"] = []
        metrics["last_run"] = None
        metrics["weekly_running"] = {}
        metrics["run_dynamics"] = None

    # Weight — get_body_composition liefert die volle Historie (dateWeightList,
    # Top-Level weight in Gramm). get_weigh_ins gibt für Ranges nur 1 Tag zurück.
    ninety_days_ago = (today - timedelta(days=90)).isoformat()
    try:
        comp = api.get_body_composition(ninety_days_ago, today_str)
        entries = (comp or {}).get("dateWeightList") or []
        weight_by_date = {}
        for e in entries:
            d_str = e.get("calendarDate") or e.get("date") or ""
            raw = e.get("weight")  # Gramm
            if d_str and raw:
                weight_by_date[d_str] = round(raw / 1000, 1)
        if weight_by_date:
            latest_date = max(weight_by_date)
            metrics["weight_kg"] = weight_by_date[latest_date]
            metrics["weight_history"] = {k: v for k, v in sorted(weight_by_date.items(), reverse=True)[:60]}
            print(f"Gewicht: {metrics['weight_kg']} kg ({len(weight_by_date)} Einträge)")
        else:
            metrics["weight_kg"] = None
            metrics["weight_history"] = {}
    except Exception as e:
        print(f"Weight error: {e}"); _errors.append(f"weight: {e}")
        metrics["weight_kg"] = None
        metrics["weight_history"] = {}

    # VO2max — bis zu 7 Tage zurückblicken (an Ruhetagen liefert der Endpoint oft nichts).
    # Nur abbrechen, wenn wirklich ein Wert vorliegt.
    metrics["vo2max"] = None
    try:
        for i in range(0, 7):
            d = (today - timedelta(days=i)).isoformat()
            perf = api.get_max_metrics(d)
            if isinstance(perf, list) and perf:
                val = (perf[0].get("generic") or {}).get("vo2MaxPreciseValue") \
                      or (perf[0].get("generic") or {}).get("vo2MaxValue")
                if val:
                    metrics["vo2max"] = round(val, 1)
                    break
    except Exception as e:
        print(f"VO2max error: {e}"); _errors.append(f"vo2max: {e}")

    # Challenges
    metrics["challenges"] = fetch_challenges(api, today)

    metrics["_errors"] = _errors
    return metrics


def _dynamics_from_activity(a):
    """Extrahiere Laufdynamik-Kennzahlen aus einem Garmin-Aktivitäts-Summary."""
    def r(v, n=0):
        return round(v, n) if isinstance(v, (int, float)) else None
    return {
        "date": (a.get("startTimeLocal") or "")[:10],
        "distance_km": r((a.get("distance") or 0) / 1000, 1),
        "cadence": r(a.get("averageRunningCadenceInStepsPerMinute")),
        "stride_length": r(a.get("avgStrideLength")),  # cm
        "vertical_oscillation": r(a.get("avgVerticalOscillation"), 1),  # cm
        "vertical_ratio": r(a.get("avgVerticalRatio"), 1),  # %
        "ground_contact_time": r(a.get("avgGroundContactTime")),  # ms
        "ground_contact_balance": r(a.get("avgGroundContactBalance"), 1),  # % links
        "avg_power": r(a.get("avgPower")),  # W
    }


def fetch_run_dynamics(api, running_acts):
    """Laufdynamik des jüngsten Laufs + Historie der Kernwerte (Frequenz,
    vertikales Verhältnis, Bodenkontaktzeit) für die Trend-Charts."""
    if not running_acts:
        return None
    # jüngster Lauf zuerst
    runs = sorted(running_acts, key=lambda a: a.get("startTimeLocal") or "", reverse=True)
    latest = runs[0]
    dyn = _dynamics_from_activity(latest)

    # Anreichern mit Geschwindigkeitsverlust + Leistungszustand (aus Detail)
    try:
        aid = latest.get("activityId")
        det = api.get_activity_details(aid)
        descs = det.get("metricDescriptors", [])
        idx = {d.get("key"): d.get("metricsIndex") for d in descs}
        rows = det.get("activityDetailMetrics", [])
        def series(key):
            i = idx.get(key)
            if i is None:
                return []
            return [row["metrics"][i] for row in rows
                    if row.get("metrics") and len(row["metrics"]) > i and row["metrics"][i] is not None]
        pc = series("directPerformanceCondition")
        sl = series("directStepSpeedLossPercent")
        ev = api.get_activity_evaluation(aid).get("summaryDTO", {})
        dyn["performance_condition"] = round(pc[-1]) if pc else None
        dyn["step_speed_loss_pct"] = round(ev.get("stepSpeedLossPercent"), 1) if ev.get("stepSpeedLossPercent") is not None else (round(sum(sl)/len(sl), 1) if sl else None)
    except Exception as e:
        print(f"Run-Dynamics-Detail-Fehler: {e}")
        dyn["performance_condition"] = None
        dyn["step_speed_loss_pct"] = None

    # Historie der Kernwerte aus allen vorliegenden Läufen
    history = {}
    for a in runs:
        d = _dynamics_from_activity(a)
        if d["date"] and d["cadence"]:
            history[d["date"]] = {
                "cadence": d["cadence"],
                "vertical_ratio": d["vertical_ratio"],
                "gct": d["ground_contact_time"],
            }
    dyn["history"] = history
    print(f"Laufdynamik: Frequenz {dyn.get('cadence')} spm, vert. Verhältnis "
          f"{dyn.get('vertical_ratio')}%, Bodenkontakt {dyn.get('ground_contact_time')} ms")
    return dyn


def _format_challenge_units(badge_key, progress, target):
    """Rohwerte (Schritte/Meter/Sekunden/Anzahl) in lesbare Einheiten umrechnen."""
    k = (badge_key or "").lower()
    if "step" in k:
        return round(progress), round(target), "Schritte"
    if "strength" in k or "hour" in k or "ride" in k or "_hr" in k:
        return round(progress / 3600, 1), round(target / 3600, 1), "h"
    if "cycle" in k or "run" in k or "walk" in k or "km" in k or "mile" in k or "distance" in k:
        return round(progress / 1000, 1), round(target / 1000, 1), "km"
    if "photo" in k:
        return round(progress), round(target), "Fotos"
    if "activit" in k:
        return round(progress), round(target), "Aktivitäten"
    return round(progress, 1), round(target, 1), ""


def fetch_challenges(api, today):
    """Aktive, noch nicht abgeschlossene Garmin-Badge-Challenges mit Fortschritt."""
    try:
        items = api.get_non_completed_badge_challenges(1, 100)
    except Exception as e:
        print(f"Challenge-Fehler: {e}")
        return []
    if not isinstance(items, list):
        return []

    challenges = []
    for item in items:
        try:
            start_str = (item.get("startDate") or "")[:10]
            end_str = (item.get("endDate") or "")[:10]
            if not end_str:
                continue
            end_date = date.fromisoformat(end_str)
            days_remaining = (end_date - today).days
            if days_remaining < 0:
                continue  # abgelaufen
            if start_str and date.fromisoformat(start_str) > today:
                continue  # noch nicht gestartet
            if item.get("badgeEarnedDate"):
                continue  # schon geschafft

            progress = float(item.get("badgeProgressValue") or 0)
            target = float(item.get("badgeTargetValue") or 0)
            if target <= 0:
                continue  # ohne Ziel kein sinnvoller Fortschritt
            pct = min(100, round(progress / target * 100))
            if pct >= 100:
                continue  # faktisch fertig

            cur, goal, unit = _format_challenge_units(item.get("badgeKey"), progress, target)
            challenges.append({
                "name": item.get("badgeChallengeName", ""),
                "current": cur,
                "goal": goal,
                "unit": unit,
                "days_remaining": days_remaining,
                "pct": pct,
            })
        except Exception as e:
            print(f"Challenge parse error: {e}")

    # Nach Dringlichkeit sortieren: bald endend zuerst, dann höchster Fortschritt
    challenges.sort(key=lambda c: (c["days_remaining"], -c["pct"]))
    print(f"Challenges: {len(challenges)} aktiv – {[c['name'] for c in challenges]}")
    return challenges[:8]


# ── History management ────────────────────────────────────────────────────────


def backfill_history(api, history, today, days=30):
    """Fülle fehlende HRV- und Ruhepuls-Tage aus Garmin (einmalig beim ersten Lauf,
    danach nur der jeweils neue Tag). So sind die 30-Tage-Charts sofort gefüllt."""
    have_hrv = {x["d"] for x in history.get("hrv", [])}
    have_rhr = {x["d"] for x in history.get("rhr", [])}
    new_hrv, new_rhr = 0, 0

    for i in range(1, days + 1):
        d = (today - timedelta(days=i)).isoformat()

        if d not in have_hrv:
            try:
                hrv = api.get_hrv_data(d)
                s = (hrv or {}).get("hrvSummary", {})
                v = s.get("lastNightAvg") or s.get("lastNight5MinHigh")
                if v:
                    history.setdefault("hrv", []).append({"d": d, "v": v})
                    new_hrv += 1
            except Exception:
                pass

        if d not in have_rhr:
            try:
                stats = api.get_stats(d)
                v = stats.get("restingHeartRate") or stats.get("restingHeartRateValue")
                if v:
                    history.setdefault("rhr", []).append({"d": d, "v": v})
                    new_rhr += 1
            except Exception:
                pass

    # Sortieren (neueste zuerst) und kappen
    history["hrv"] = sorted(history.get("hrv", []), key=lambda x: x["d"], reverse=True)[:30]
    history["rhr"] = sorted(history.get("rhr", []), key=lambda x: x["d"], reverse=True)[:30]
    print(f"Backfill: {new_hrv} neue HRV-Tage, {new_rhr} neue Ruhepuls-Tage")
    return history


def update_history(history, metrics, today_str, weekly_running):
    def prepend_dedup(lst, entry, maxlen):
        lst = [x for x in lst if x.get("d") != today_str]
        return ([entry] + lst)[:maxlen]

    if metrics.get("hrv_value"):
        history["hrv"] = prepend_dedup(
            history.get("hrv", []), {"d": today_str, "v": metrics["hrv_value"]}, 30
        )
    if metrics.get("resting_hr"):
        history["rhr"] = prepend_dedup(
            history.get("rhr", []), {"d": today_str, "v": metrics["resting_hr"]}, 30
        )
    if metrics.get("vo2max"):
        history["vo2max"] = prepend_dedup(
            history.get("vo2max", []), {"d": today_str, "v": metrics["vo2max"]}, 60
        )
    # Weight: use full history from Garmin if available (90 days)
    if metrics.get("weight_history"):
        existing = {x["d"]: x for x in history.get("weight", [])}
        for d_str, kg in metrics["weight_history"].items():
            existing[d_str] = {"d": d_str, "v": kg}
        history["weight"] = sorted(existing.values(), key=lambda x: x["d"], reverse=True)[:60]
    elif metrics.get("weight_kg"):
        history["weight"] = prepend_dedup(
            history.get("weight", []), {"d": today_str, "v": metrics["weight_kg"]}, 60
        )

    # Weekly running – update all weeks present in the fresh activity data
    existing_wk = {x["w"]: x for x in history.get("weekly_km", [])}
    for wk, km in weekly_running.items():
        existing_wk[wk] = {"w": wk, "v": km}
    sorted_weeks = sorted(existing_wk.values(), key=lambda x: x["w"], reverse=True)
    history["weekly_km"] = sorted_weeks[:12]

    # Laufdynamik-Historie (Frequenz, vert. Verhältnis, Bodenkontakt je Lauf)
    rd = metrics.get("run_dynamics") or {}
    if rd.get("history"):
        existing_rd = {x["d"]: x for x in history.get("run_dyn", [])}
        for d_str, vals in rd["history"].items():
            existing_rd[d_str] = {"d": d_str, **vals}
        history["run_dyn"] = sorted(existing_rd.values(), key=lambda x: x["d"], reverse=True)[:40]

    return history


