#!/usr/bin/env python3
"""Täglich: Garmin-Daten holen → Claude analysiert → index.html aktualisieren."""
import os
import re
import json
from datetime import date, timedelta


TOKENSTORE_PATH = os.path.expanduser("~/.garmin_session")


def garmin_login():
    from garminconnect import Garmin
    email = os.environ["GARMIN_EMAIL"]
    password = os.environ["GARMIN_PASSWORD"]
    api = Garmin(email, password)
    if os.path.exists(TOKENSTORE_PATH):
        try:
            with open(TOKENSTORE_PATH) as f:
                api.garth.loads(f.read())
            _ = api.display_name  # raises if session expired
            print("Garmin: cached session used")
            return api
        except Exception:
            print("Garmin: cached session expired, re-login")
    api.login()
    with open(TOKENSTORE_PATH, "w") as f:
        f.write(api.garth.dumps())
    print("Garmin: fresh login, session saved")
    return api


def fetch_garmin_metrics():
    api = garmin_login()
    today = date.today()
    yesterday = (today - timedelta(days=1)).isoformat()
    week_ago = (today - timedelta(days=7)).isoformat()
    today_str = today.isoformat()
    metrics = {}

    # Sleep (letzte Nacht = gestern in Garmin)
    try:
        sleep = api.get_sleep_data(yesterday)
        dto = sleep.get("dailySleepDTO", {})
        secs = dto.get("sleepTimeSeconds") or 0
        metrics["sleep_hours"] = round(secs / 3600, 1) if secs else None
        metrics["sleep_score"] = ((dto.get("sleepScores") or {}).get("overall") or {}).get("value")
    except Exception as e:
        print(f"Sleep error: {e}")
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
        print(f"HRV error: {e}")
        metrics["hrv_status"] = None
        metrics["hrv_value"] = None
        metrics["hrv_weekly_avg"] = None

    # Tagesstats (Body Battery, Stress, Ruhepuls)
    try:
        stats = api.get_stats(today_str)
        metrics["body_battery"] = stats.get("bodyBatteryMostRecentValue")
        metrics["stress"] = stats.get("averageStressLevel")
        metrics["resting_hr"] = stats.get("restingHeartRateValue")
    except Exception as e:
        print(f"Stats error: {e}")
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
        print(f"Training readiness error: {e}")
        metrics["training_readiness"] = None

    # Letzte 7 Tage Aktivitäten
    try:
        acts = api.get_activities_by_date(week_ago, today_str, "")
        metrics["recent_activities"] = [
            {
                "name": a.get("activityName", ""),
                "type": (a.get("activityType") or {}).get("typeKey", ""),
                "date": (a.get("startTimeLocal") or "")[:10],
                "distance_km": round((a.get("distance") or 0) / 1000, 1),
                "duration_min": round((a.get("duration") or 0) / 60),
            }
            for a in acts[:7]
        ]
    except Exception as e:
        print(f"Activities error: {e}")
        metrics["recent_activities"] = []

    # Gewicht (neuester Eintrag)
    try:
        comp = api.get_body_composition(week_ago, today_str)
        entries = comp.get("dateWeightList") or []
        if entries:
            metrics["weight_kg"] = round((entries[-1].get("weight") or 0) / 1000, 1)
        else:
            metrics["weight_kg"] = None
    except Exception as e:
        print(f"Weight error: {e}")
        metrics["weight_kg"] = None

    return metrics


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


def call_claude(metrics, plan_context):
    import anthropic
    client = anthropic.Anthropic()

    hrv_labels = {
        "BALANCED": "Grün (ausgeglichen)",
        "UNBALANCED": "Gelb (unausgeglichen)",
        "LOW": "Rot (niedrig)",
        "POOR": "Rot (schlecht)",
        "NONE": "Keine Daten",
    }
    hrv_display = hrv_labels.get(metrics.get("hrv_status", ""), metrics.get("hrv_status") or "unbekannt")

    prompt = f"""Du bist Laufcoach. Analysiere diese Garmin-Morgendaten und gib eine kurze Trainingsempfehlung.

Garmin-Daten:
- Schlaf: {metrics.get("sleep_hours")} h (Score {metrics.get("sleep_score")}/100)
- HRV: {hrv_display} | Wert letzte Nacht: {metrics.get("hrv_value")} ms | Wochenschnitt: {metrics.get("hrv_weekly_avg")} ms
- Body Battery: {metrics.get("body_battery")}/100
- Training Readiness: {metrics.get("training_readiness")}/100
- Ruhepuls: {metrics.get("resting_hr")} bpm
- Stresslevel gestern: {metrics.get("stress")}/100
- Gewicht: {metrics.get("weight_kg")} kg
- Letzte Aktivitäten (7 Tage): {json.dumps(metrics.get("recent_activities", []), ensure_ascii=False)}

Planposition: {plan_context}

Ziel: Frankfurt Marathon 25.10.2026, ~5h Zielzeit, Übertraining vermeiden.

Antworte NUR mit diesem JSON (kein Markdown, kein Text drumherum):
{{
  "recommendation": "<max. 2 prägnante Sätze auf Deutsch>",
  "slider_sleep": <Zahl 4–10, Schritte 0.5, von Garmin-Schlafdaten ableiten>,
  "slider_wellbeing": <1–5: 1=erschöpft, 3=ok, 5=top – aus HRV+BB+Stress ableiten>,
  "slider_hrv": <1=Rot, 2=Ok, 3=Grün – direkt aus HRV-Status>
}}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    # Claude might wrap in ```json ... ``` – strip that
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def inject_garmin_data(html_content, metrics, claude_result):
    payload = {
        **metrics,
        "recommendation": claude_result.get("recommendation", ""),
        "slider_sleep": claude_result.get("slider_sleep", 7.5),
        "slider_wellbeing": claude_result.get("slider_wellbeing", 3),
        "slider_hrv": claude_result.get("slider_hrv", 2),
        "updated": date.today().isoformat(),
    }
    block = (
        "<!-- GARMIN:START -->\n"
        "<script>\n"
        f"window.GARMIN_DATA = {json.dumps(payload, ensure_ascii=False, indent=2)};\n"
        "</script>\n"
        "<!-- GARMIN:END -->"
    )
    if "<!-- GARMIN:START -->" in html_content:
        html_content = re.sub(
            r"<!-- GARMIN:START -->.*?<!-- GARMIN:END -->",
            block,
            html_content,
            flags=re.DOTALL,
        )
    else:
        html_content = html_content.replace("</head>", f"{block}\n</head>")
    return html_content


def main():
    html_path = "index.html"
    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    print("Garmin-Daten abrufen …")
    try:
        metrics = fetch_garmin_metrics()
        print(json.dumps(metrics, ensure_ascii=False))
    except Exception as e:
        print(f"Garmin fehlgeschlagen: {e}")
        metrics = {}

    plan_context = get_plan_context(html)
    print(f"Plan-Kontext: {plan_context}")

    print("Claude API …")
    try:
        claude_result = call_claude(metrics, plan_context)
        print(json.dumps(claude_result, ensure_ascii=False))
    except Exception as e:
        print(f"Claude fehlgeschlagen: {e}")
        claude_result = {
            "recommendation": "Tagesupdate nicht verfügbar – bitte manuell eintragen.",
            "slider_sleep": metrics.get("sleep_hours") or 7.5,
            "slider_wellbeing": 3,
            "slider_hrv": 2,
        }

    updated = inject_garmin_data(html, metrics, claude_result)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(updated)
    print("index.html aktualisiert.")


if __name__ == "__main__":
    main()
