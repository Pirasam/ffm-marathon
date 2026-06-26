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
    session_secret = os.environ.get("GARMIN_SESSION_DATA", "")

    api = Garmin(email, password)

    # 1. GitHub Secret (most reliable in CI — no fresh login needed)
    if session_secret:
        try:
            api.garth.loads(session_secret)
            print("Garmin: session from GARMIN_SESSION_DATA secret")
            with open(TOKENSTORE_PATH, "w") as f:
                f.write(api.garth.dumps())
            return api
        except Exception as e:
            print(f"Garmin: secret session failed: {e}")

    # 2. Cached file from previous run
    if os.path.exists(TOKENSTORE_PATH):
        try:
            with open(TOKENSTORE_PATH) as f:
                api.garth.loads(f.read())
            print("Garmin: cached session used")
            return api
        except Exception as e:
            print(f"Garmin: cached session failed: {e}, trying fresh login")

    # 3. Fresh login (requires interactive MFA on new IPs — usually fails in CI)
    if not email or not password:
        raise RuntimeError("Keine Session verfügbar und GARMIN_EMAIL/PASSWORD fehlen")
    print("Garmin: fresh login …")
    api.login()
    with open(TOKENSTORE_PATH, "w") as f:
        f.write(api.garth.dumps())
    print("Garmin: fresh login OK, session saved")
    return api


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

    # HRV
    try:
        hrv = api.get_hrv_data(yesterday)
        s = hrv.get("hrvSummary", {})
        metrics["hrv_status"] = s.get("status")
        metrics["hrv_value"] = s.get("lastNight")
        metrics["hrv_weekly_avg"] = s.get("weeklyAvg")
    except Exception as e:
        print(f"HRV error: {e}"); _errors.append(f"hrv: {e}")
        metrics["hrv_status"] = None
        metrics["hrv_value"] = None
        metrics["hrv_weekly_avg"] = None

    # Daily stats (Body Battery, Stress, RHR)
    try:
        stats = api.get_stats(today_str)
        metrics["body_battery"] = stats.get("bodyBatteryMostRecentValue")
        metrics["stress"] = stats.get("averageStressLevel")
        metrics["resting_hr"] = stats.get("restingHeartRateValue")
    except Exception as e:
        print(f"Stats error: {e}"); _errors.append(f"stats: {e}")
        metrics["body_battery"] = None
        metrics["stress"] = None
        metrics["resting_hr"] = None

    # Training Readiness
    try:
        tr = api.get_training_readiness(today_str)
        if isinstance(tr, list) and tr:
            metrics["training_readiness"] = tr[0].get("trainingReadinessScore")
        else:
            metrics["training_readiness"] = None
    except Exception as e:
        print(f"Training readiness error: {e}"); _errors.append(f"readiness: {e}")
        metrics["training_readiness"] = None

    # Activities last 14 days (for weekly volume)
    try:
        acts = api.get_activities_by_date(two_weeks_ago, today_str, "")
        metrics["recent_activities"] = [
            {
                "name": a.get("activityName", ""),
                "type": (a.get("activityType") or {}).get("typeKey", ""),
                "date": (a.get("startTimeLocal") or "")[:10],
                "distance_km": round((a.get("distance") or 0) / 1000, 1),
                "duration_min": round((a.get("duration") or 0) / 60),
            }
            for a in acts[:14]
        ]
        # Weekly running km grouped by ISO week
        weekly = defaultdict(float)
        for a in acts:
            atype = (a.get("activityType") or {}).get("typeKey", "")
            if "running" in atype or "trail" in atype:
                d = date.fromisoformat((a.get("startTimeLocal") or today_str)[:10])
                wk = f"{d.year}-W{d.isocalendar()[1]:02d}"
                weekly[wk] += (a.get("distance") or 0) / 1000
        metrics["weekly_running"] = {k: round(v, 1) for k, v in weekly.items()}
    except Exception as e:
        print(f"Activities error: {e}"); _errors.append(f"activities: {e}")
        metrics["recent_activities"] = []
        metrics["weekly_running"] = {}

    # Weight
    try:
        comp = api.get_body_composition(two_weeks_ago, today_str)
        entries = comp.get("dateWeightList") or []
        if entries:
            latest = max(entries, key=lambda x: x.get("calendarDate", ""))
            metrics["weight_kg"] = round((latest.get("weight") or 0) / 1000, 1) or None
        else:
            metrics["weight_kg"] = None
    except Exception as e:
        print(f"Weight error: {e}"); _errors.append(f"weight: {e}")
        metrics["weight_kg"] = None

    # VO2max
    try:
        perf = api.get_max_metrics(today_str)
        if isinstance(perf, list) and perf:
            metrics["vo2max"] = perf[0].get("generic", {}).get("vo2MaxPreciseValue")
        else:
            metrics["vo2max"] = None
    except Exception as e:
        print(f"VO2max error: {e}"); _errors.append(f"vo2max: {e}")
        metrics["vo2max"] = None

    # Challenges
    metrics["challenges"] = fetch_challenges(api, today)

    metrics["_errors"] = _errors
    return metrics


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
        return {"hrv": [], "rhr": [], "weight": [], "weekly_km": []}
    try:
        return json.loads(m.group(1))
    except Exception:
        return {"hrv": [], "rhr": [], "weight": [], "weekly_km": []}


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
    if metrics.get("weight_kg"):
        history["weight"] = prepend_dedup(
            history.get("weight", []), {"d": today_str, "v": metrics["weight_kg"]}, 60
        )

    # Weekly running – update all weeks present in the fresh activity data
    existing_wk = {x["w"]: x for x in history.get("weekly_km", [])}
    for wk, km in weekly_running.items():
        existing_wk[wk] = {"w": wk, "v": km}
    sorted_weeks = sorted(existing_wk.values(), key=lambda x: x["w"], reverse=True)
    history["weekly_km"] = sorted_weeks[:12]

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
    return f"Woche {cur + 1} von {len(week_starts)}, heute {day_de[today.weekday()]} ({today.isoformat()})"


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

    prompt = f"""Du bist Laufcoach. Analysiere diese Garmin-Morgendaten für einen Läufer (Ziel: Frankfurt Marathon 25.10.2026, ~5h, aktuell 91 kg → Ziel 87 kg).

Garmin-Daten:
- Schlaf: {metrics.get("sleep_hours")} h (Score {metrics.get("sleep_score")}/100)
- HRV: {hrv_display} | Wert letzte Nacht: {metrics.get("hrv_value")} ms | Wochenschnitt: {metrics.get("hrv_weekly_avg")} ms
- Body Battery: {metrics.get("body_battery")}/100
- Training Readiness: {metrics.get("training_readiness")}/100
- Ruhepuls: {metrics.get("resting_hr")} bpm
- Stresslevel gestern: {metrics.get("stress")}/100
- Gewicht: {metrics.get("weight_kg")} kg
- VO₂max: {metrics.get("vo2max")}
- Letzte Aktivitäten (14 Tage): {json.dumps(metrics.get("recent_activities", [])[:7], ensure_ascii=False)}
- Planposition: {plan_context}
- Bald ablaufende Challenges: {json.dumps(soon_challenges, ensure_ascii=False)}

WICHTIG: Garmin bewertet lange, niedrigpulsige Zone-2-Einheiten oft als "unproduktiv" – ignoriere Garmin's Training-Status, beurteile selbst.

Antworte NUR mit diesem JSON (kein Markdown, kein Text):
{{
  "recommendation": "<max. 2 prägnante Sätze auf Deutsch>",
  "training_intensity": "<Leicht|Mittel|Hart>",
  "slider_sleep": <4–10 Schritte 0.5>,
  "slider_wellbeing": <1–5: 1=erschöpft 5=top>,
  "slider_hrv": <1–3: 1=Rot 2=Ok 3=Grün>,
  "predicted_finish_h": <Zahl z.B. 4.97, realistisch aus VO2max+Volumen+Gewicht>,
  "on_track_score": <0–100>,
  "factor_volume": <0–100>,
  "factor_hrv": <0–100>,
  "factor_vo2max": <0–100>,
  "factor_weight": <0–100>,
  "challenge_alert": "<leer ODER 1 Satz zu bald endender Challenge auf Deutsch>"
}}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
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
        "factor_volume": claude_result.get("factor_volume", 50),
        "factor_hrv": claude_result.get("factor_hrv", 50),
        "factor_vo2max": claude_result.get("factor_vo2max", 50),
        "factor_weight": claude_result.get("factor_weight", 50),
        "challenge_alert": claude_result.get("challenge_alert", ""),
        "updated": date.today().isoformat(),
    }
    payload.pop("weekly_running", None)
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
