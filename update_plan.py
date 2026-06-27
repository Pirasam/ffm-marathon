#!/usr/bin/env python3
"""Täglich: Garmin-Daten holen → Claude analysiert → index.html aktualisieren."""
import os
import re
import json
from datetime import date, timedelta
from collections import defaultdict

TOKENSTORE_PATH = os.path.expanduser("~/.garmin_session")
GARMIN_MARKER = ("<!-- GARMIN:START -->", "<!-- GARMIN:END -->")
HISTORY_MARKER = ("<!-- HISTORY:START -->", "<!-- HISTORY:END -->")


# ── Auth ──────────────────────────────────────────────────────────────────────

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

    # Sleep
    try:
        sleep = api.get_sleep_data(yesterday)
        dto = sleep.get("dailySleepDTO", {})
        secs = dto.get("sleepTimeSeconds") or 0
        metrics["sleep_hours"] = round(secs / 3600, 1) if secs else None
        metrics["sleep_score"] = ((dto.get("sleepScores") or {}).get("overall") or {}).get("value")
    except Exception as e:
        print(f"Sleep error: {e}"); _errors.append(f"sleep: {e}")
        metrics["sleep_hours"] = None
        metrics["sleep_score"] = None

    # HRV — lastNightAvg ist der von Garmin angezeigte Nachtwert (40–50er-Bereich).
    # lastNight5MinHigh ist nur der Spitzenwert und liegt deutlich höher.
    try:
        hrv = api.get_hrv_data(yesterday)
        s = hrv.get("hrvSummary", {})
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

    # VO2max
    try:
        for d in [today_str, yesterday]:
            perf = api.get_max_metrics(d)
            if isinstance(perf, list) and perf:
                metrics["vo2max"] = perf[0].get("generic", {}).get("vo2MaxPreciseValue")
                break
        else:
            metrics["vo2max"] = None
    except Exception as e:
        print(f"VO2max error: {e}"); _errors.append(f"vo2max: {e}")
        metrics["vo2max"] = None

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


def fetch_challenges(api, today):
    """Fetch active Garmin badge challenges. Returns list or [] on failure."""
    endpoints = [
        "/badge-challenge/v1/badgeChallenges?start=0&limit=50",
        "/badge-challenge/v1/badgeChallenges",
    ]
    raw = None
    for ep in endpoints:
        try:
            resp = api.garth.get("connect", ep)
            raw = resp.json()
            print(f"Challenges OK from {ep}: {str(raw)[:200]}")
            break
        except Exception as e:
            print(f"Challenge endpoint {ep} failed: {e}")

    if not raw:
        return []

    # Normalise – different Garmin API versions use different field names
    items = raw if isinstance(raw, list) else (
        raw.get("badgeChallengeList") or raw.get("challenges") or raw.get("data") or []
    )

    challenges = []
    for item in items[:10]:
        try:
            name = (item.get("badgeChallengeName") or item.get("challengeName")
                    or item.get("name") or "")
            end_str = (item.get("endDate") or item.get("challengeEndDate")
                       or item.get("end_date") or "")
            current = float(item.get("currentConsumption") or item.get("progress")
                            or item.get("current") or 0)
            goal = float(item.get("badgeChallengeGoal") or item.get("goal") or 1)
            unit = (item.get("badgeChallengeGoalUnit") or item.get("unit") or "")

            days_remaining = None
            if end_str:
                end_date = date.fromisoformat(end_str[:10])
                days_remaining = (end_date - today).days
                if days_remaining < 0:
                    continue  # skip expired

            pct = min(100, round(current / goal * 100)) if goal > 0 else 0
            challenges.append({
                "name": name,
                "current": round(current, 1),
                "goal": round(goal, 1),
                "unit": unit,
                "days_remaining": days_remaining,
                "pct": pct,
            })
        except Exception as e:
            print(f"Challenge parse error: {e}")

    return challenges


# ── History management ────────────────────────────────────────────────────────

def load_history(html_content):
    start, end = HISTORY_MARKER
    m = re.search(
        re.escape(start) + r"\s*<script>window\.GARMIN_HISTORY\s*=\s*(.*?);\s*</script>\s*" + re.escape(end),
        html_content, re.DOTALL
    )
    if not m:
        return {"hrv": [], "rhr": [], "weight": [], "weekly_km": [], "run_dyn": []}
    try:
        return json.loads(m.group(1))
    except Exception:
        return {"hrv": [], "rhr": [], "weight": [], "weekly_km": [], "run_dyn": []}


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


def save_history(html_content, history):
    start, end = HISTORY_MARKER
    block = (
        f"{start}\n"
        f"<script>window.GARMIN_HISTORY = {json.dumps(history, ensure_ascii=False)};</script>\n"
        f"{end}"
    )
    if start in html_content:
        html_content = re.sub(
            re.escape(start) + r".*?" + re.escape(end),
            block, html_content, flags=re.DOTALL
        )
    else:
        html_content = html_content.replace("</head>", f"{block}\n</head>")
    return html_content


# ── Plan context ──────────────────────────────────────────────────────────────

def get_plan_context(html_content):
    m = re.search(r"const weekStarts = (\[.*?\]);", html_content)
    if not m:
        return "Trainingsplan (Woche unbekannt)"
    week_starts = json.loads(m.group(1))
    today = date.today()
    cur = 0
    for i, ws in enumerate(week_starts):
        if today >= date.fromisoformat(ws):
            cur = i
    day_de = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    base = f"Woche {cur + 1} von {len(week_starts)}, heute {day_de[today.weekday()]} ({today.isoformat()})"

    # Extract today's planned training from the weeks array
    try:
        wm = re.search(r"const weeks = (\[.*?\n\]\s*;)", html_content, re.DOTALL)
        if wm:
            weeks_data = json.loads(wm.group(1).rstrip(";"))
            if cur < len(weeks_data):
                week = weeks_data[cur]
                days = week.get("days", [])
                dow = today.weekday()  # 0=Mo … 6=So
                if dow < len(days):
                    day = days[dow]
                    title = day.get("title", "")
                    badges = day.get("badges", [])
                    desc = day.get("desc", "")
                    is_rest = "rest" in badges
                    is_longrun = bool(day.get("longrun")) or "longrun" in title.lower()
                    base += f"\nHEUTE GEPLANT: {title}"
                    if is_rest:
                        base += " (RUHETAG — KEIN LAUFEN, KEIN TRAINING empfehlen)"
                    elif is_longrun:
                        base += " (LONGRUN — langer Dauerlauf, Verpflegung und Regeneration wichtig)"
                    elif "run" in badges:
                        base += f" (Lauftag — Zone 2, {desc[:80]})"
                    elif "bike" in badges:
                        base += f" (Radtag — {desc[:80]})"
                    base += f"\nBeschreibung: {desc[:160]}"
    except Exception as e:
        print(f"Plan-Kontext-Fehler: {e}")

    return base


# ── Claude ────────────────────────────────────────────────────────────────────

def call_claude(metrics, plan_context):
    import anthropic
    client = anthropic.Anthropic()

    hrv_labels = {
        "BALANCED": "Grün (ausgeglichen)", "UNBALANCED": "Gelb (unausgeglichen)",
        "LOW": "Rot (niedrig)", "POOR": "Rot (schlecht)", "NONE": "Keine Daten",
    }
    hrv_display = hrv_labels.get(metrics.get("hrv_status", ""), metrics.get("hrv_status") or "unbekannt")

    # Check for soon-expiring challenges
    soon_challenges = [
        c for c in metrics.get("challenges", [])
        if c.get("days_remaining") is not None and 0 <= c["days_remaining"] <= 3
           and c["pct"] < 100
    ]

    last_run = metrics.get("last_run")
    last_run_str = ""
    if last_run:
        lr = last_run
        d, t = lr.get("distance_km", 0), lr.get("duration_min", 0)
        pace = lr.get("pace_min_km")
        pace_str = f"{int(pace)}:{int((pace % 1) * 60):02d} min/km" if pace else "?"
        last_run_str = (f"\n- Letzter Lauf: {lr['date']}, {d} km, {t} min, Pace {pace_str}"
                        + (f", ∅HR {lr['avg_hr']} bpm" if lr.get("avg_hr") else ""))

    is_longrun = "LONGRUN" in plan_context
    longrun_field = ""
    if is_longrun:
        longrun_field = (
            ',\n  "long_run_tips": {\n'
            '    "hydration": "<1-2 Sätze: Trinkstrategie für heute. Bei >60 Min: alle 15-20 Min trinken, Natrium/Elektrolyte (er hatte Hamstring-Krampf durch Natriummangel!). Mengen je nach Hitze nennen.>",\n'
            '    "nutrition": "<1-2 Sätze: Verpflegung. Vor dem Lauf Kohlenhydrate, während Lauf >75 Min ein Gel ab km 12-14. Bei Gewichtsabnahme-Ziel: nicht überessen, aber Longrun braucht Energie.>",\n'
            '    "stretching": "<1-2 Sätze: Vorher dynamisch (Beinpendel, Ausfallschritte), nachher statisch mit Fokus Hamstrings/Waden. Konkret benennen.>",\n'
            '    "recovery": "<1-2 Sätze: Nach dem Lauf — Protein+Carbs binnen 30-60 Min, Elektrolyte auffüllen, lockeres Auslaufen/Gehen, Schlaf priorisieren.>"\n'
            '  }'
        )

    hrv_lo = metrics.get("hrv_balanced_low")
    hrv_hi = metrics.get("hrv_balanced_high")
    hrv_range = f" (sein ausgeglichener Bereich: {hrv_lo}–{hrv_hi} ms)" if hrv_lo and hrv_hi else ""

    prompt = f"""Du bist sein persönlicher Laufcoach. Ziel: Frankfurt Marathon 25.10.2026 unter 5:00 h, aktuell {metrics.get("weight_kg")} kg → Ziel 87 kg.

Garmin-Daten heute:
- Schlaf: {metrics.get("sleep_hours")} h (Score {metrics.get("sleep_score")}/100)
- HRV: {hrv_display} | letzte Nacht: {metrics.get("hrv_value")} ms | Wochenschnitt: {metrics.get("hrv_weekly_avg")} ms{hrv_range}
- Body Battery: {metrics.get("body_battery")}/100
- Training Readiness: {metrics.get("training_readiness")}/100
- Ruhepuls: {metrics.get("resting_hr")} bpm
- Stresslevel gestern: {metrics.get("stress")}/100
- VO₂max: {metrics.get("vo2max")}{last_run_str}
- Letzte Aktivitäten (14 Tage): {json.dumps(metrics.get("recent_activities", [])[:7], ensure_ascii=False)}
- {plan_context}
- Bald ablaufende Challenges: {json.dumps(soon_challenges, ensure_ascii=False)}

REGEL 1 — Plan ist bindend: Die Empfehlung MUSS zum heute geplanten Training (Zeile "HEUTE GEPLANT") passen.
- Steht dort RUHETAG: empfiehl KEIN Laufen/Radfahren. Empfiehl Erholung, Mobilität, ggf. Spaziergang. Erkläre kurz warum Ruhe heute wichtig ist.
- Steht dort ein Lauf/Rad: bestätige oder passe an Tagesform an (z.B. bei schlechter Erholung kürzer/langsamer).
- Erfinde NIEMALS ein Training, das nicht im Plan steht.

REGEL 2 — Pace-Logik (niedrigere min/km = SCHNELLER):
- Zone 2 für diesen Läufer (5h-Marathon, Rennpace ~7:06/km) = ca. 8:00–9:30 min/km bei 130–135 bpm — also LANGSAM.
- "Puls zu hoch" → nächster Lauf LANGSAMER (höhere min/km-Zahl). NIE eine schnellere Pace als Zone-2-Tipp nennen.

REGEL 3 — On-Track ehrlich: on_track_score (0–100) und predicted_finish_h müssen zusammenpassen.
- Wenn Finish > 5:00 h, darf on_track_score nicht "grün/gut" wirken (also < 70). Wenn Finish < 5:00 h, dann ≥ 70.
- on_track_note erklärt den Status in 1 Satz und nennt den größten Hebel.

REGEL 4 — Laufanalyse konkret & motivierend: Beziehe dich auf echte Zahlen (Pace, Puls, Distanz), sag was gut war UND den einen wichtigsten nächsten Schritt. Kein Fachjargon-Geschwurbel, kein unrealistischer Ratschlag.

Antworte NUR mit diesem JSON (kein Markdown):
{{
  "recommendation": "<2 Sätze auf Deutsch, passend zum HEUTE GEPLANTEN Training>",
  "training_intensity": "<Leicht|Mittel|Hart|Ruhe>",
  "slider_sleep": <4–10 Schritte 0.5>,
  "slider_wellbeing": <1–5: 1=erschöpft 5=top>,
  "slider_hrv": <1–3: 1=Rot 2=Ok 3=Grün>,
  "predicted_finish_h": <Zahl z.B. 4.97, realistisch aus VO2max+Volumen+Gewicht>,
  "on_track_score": <0–100, konsistent mit predicted_finish_h>,
  "on_track_note": "<1 Satz: erklärt on_track_score + Finishzeit zusammen, nennt größten Hebel (z.B. Laufumfang)>",
  "factor_volume": <0–100>,
  "factor_hrv": <0–100>,
  "factor_vo2max": <0–100>,
  "factor_weight": <0–100>,
  "challenge_alert": "<leer ODER 1 Satz zu bald endender Challenge>",
  "run_feedback": "<falls letzter Lauf vorhanden: 2 konkrete, motivierende Sätze mit echten Zahlen. Sonst leer.>"{longrun_field}
}}"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1100,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


# ── HTML injection ────────────────────────────────────────────────────────────

def inject_garmin_data(html_content, metrics, claude_result):
    payload = {
        **metrics,
        "recommendation": claude_result.get("recommendation", ""),
        "training_intensity": claude_result.get("training_intensity", "Mittel"),
        "slider_sleep": claude_result.get("slider_sleep", 7.5),
        "slider_wellbeing": claude_result.get("slider_wellbeing", 3),
        "slider_hrv": claude_result.get("slider_hrv", 2),
        "predicted_finish_h": claude_result.get("predicted_finish_h"),
        "on_track_score": claude_result.get("on_track_score", 65),
        "on_track_note": claude_result.get("on_track_note", ""),
        "factor_volume": claude_result.get("factor_volume", 50),
        "factor_hrv": claude_result.get("factor_hrv", 50),
        "factor_vo2max": claude_result.get("factor_vo2max", 50),
        "factor_weight": claude_result.get("factor_weight", 50),
        "challenge_alert": claude_result.get("challenge_alert", ""),
        "run_feedback": claude_result.get("run_feedback", ""),
        "long_run_tips": claude_result.get("long_run_tips") or None,
        "updated": date.today().isoformat(),
    }
    payload.pop("weekly_running", None)
    payload.pop("weight_history", None)
    # run_dynamics behalten, aber die Historie liegt in GARMIN_HISTORY
    if isinstance(payload.get("run_dynamics"), dict):
        payload["run_dynamics"] = {k: v for k, v in payload["run_dynamics"].items() if k != "history"}
    # keep _errors in payload for live debugging

    start, end = GARMIN_MARKER
    block = (
        f"{start}\n"
        f"<script>\nwindow.GARMIN_DATA = {json.dumps(payload, ensure_ascii=False, indent=2)};\n</script>\n"
        f"{end}"
    )
    if start in html_content:
        html_content = re.sub(
            re.escape(start) + r".*?" + re.escape(end),
            block, html_content, flags=re.DOTALL
        )
    else:
        html_content = html_content.replace("</head>", f"{block}\n</head>")
    return html_content


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    html_path = "index.html"
    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    print("Garmin-Daten abrufen …")
    api = None
    try:
        api = garmin_login()
        metrics = fetch_garmin_metrics(api)
        print(json.dumps({k: v for k, v in metrics.items() if k not in ("recent_activities", "_errors")}, ensure_ascii=False))
        if metrics.get("_errors"):
            print(f"API-Fehler: {metrics['_errors']}")
    except Exception as e:
        print(f"Garmin fehlgeschlagen: {e}")
        metrics = {"challenges": [], "weekly_running": {}, "recent_activities": [], "_errors": [f"login: {e}"]}

    # Update history
    history = load_history(html)
    if api is not None:
        try:
            history = backfill_history(api, history, date.today())
        except Exception as e:
            print(f"Backfill fehlgeschlagen: {e}")
    history = update_history(history, metrics, date.today().isoformat(), metrics.get("weekly_running", {}))
    html = save_history(html, history)

    plan_context = get_plan_context(html)
    print(f"Plan-Kontext: {plan_context}")

    print("Claude API …")
    try:
        claude_result = call_claude(metrics, plan_context)
        print(json.dumps(claude_result, ensure_ascii=False))
    except Exception as e:
        print(f"Claude fehlgeschlagen: {e}")
        claude_result = {
            "recommendation": "Tagesupdate nicht verfügbar.",
            "training_intensity": "Mittel",
            "slider_sleep": metrics.get("sleep_hours") or 7.5,
            "slider_wellbeing": 3,
            "slider_hrv": 2,
            "predicted_finish_h": None,
            "on_track_score": 65,
            "on_track_note": "",
            "factor_volume": 50,
            "factor_hrv": 50,
            "factor_vo2max": 50,
            "factor_weight": 50,
            "challenge_alert": "",
        }

    html = inject_garmin_data(html, metrics, claude_result)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("index.html aktualisiert.")


if __name__ == "__main__":
    main()
