#!/usr/bin/env python3
"""Rendert das Dashboard: liest garmin_data.json → Claude analysiert → index.html.

Ruft KEIN Garmin auf. Der Garmin-Abruf laeuft lokal via sync_garmin.py, weil
Garmin den Token-Refresh aus GitHub-Actions-IPs mit 429 blockt. Dieses Skript
braucht nur den ANTHROPIC_API_KEY und laeuft deshalb problemlos in der Cloud.
"""
import os
import re
import json
from datetime import date, timedelta

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(REPO_DIR, "garmin_data.json")
GARMIN_MARKER = ("<!-- GARMIN:START -->", "<!-- GARMIN:END -->")
HISTORY_MARKER = ("<!-- HISTORY:START -->", "<!-- HISTORY:END -->")

CLAUDE_MODEL = "claude-opus-4-8"

# ── Genesungs- / Wiedereinstiegs-Modus ────────────────────────────────────────
# RECOVERY_MODE True: kein normaler Trainingsplan, sondern Erholungs-/Wiederein-
#   stiegs-Ansicht. Zum Beenden (voller Trainingsbetrieb) RECOVERY_MODE = False.
# DOCTOR_CLEARED steuert, ob begrenzte Aktivität erlaubt ist (ärztliche Freigabe).
RECOVERY_MODE = True
RECOVERY_REASON = "Wiedereinstieg nach Atemwegsinfekt (Lunge frei, nur noch Restschnupfen) – zuvor Borreliose. Vorsichtiger Marathon-Aufbau."
RECOVERY_SINCE = "2026-08-18"

# Wieder-Aufbau ab 18.08.: Lunge frei, Symptome nur noch oberhalb des Halses,
# Werte zurück auf Basisniveau. Begrenzte Aktivität wieder erlaubt.
# Zum vollen Trainingsbetrieb später RECOVERY_MODE = False.
DOCTOR_CLEARED = True
DOCTOR_DATE = "2026-07-27"
DOCTOR_GUIDANCE = (
    "Grundfreigabe vom 27.07. gilt weiter. Nach dem zweiten Infekt (jetzt abgeklungen, "
    "Lunge frei) vorsichtig wieder aufbauen: erst lockere Läufe, dann Longrun langsam "
    "steigern. Immer auf das Körpergefühl hören; bei erneutem Husten/Brustsymptomen oder "
    "Herzstolpern sofort pausieren. Antikörper-Bluttest Ende August nicht vergessen."
)

# Individuelle Normalwerte VOR der Infektion (aus den Daten 27.06.–09.07.)
BASELINE_RHR = (53, 55)
BASELINE_HRV = (42, 48)


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

def _claude_json(prompt, max_tokens=1100):
    import anthropic
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def call_claude_recovery(metrics, history):
    """Wiedereinstieg nach Krankheit: begleitet, begrenzt, mit ärztlicher Freigabe."""
    rhr_hist = [x["v"] for x in (history.get("rhr") or [])[:10]]
    hrv_hist = [x["v"] for x in (history.get("hrv") or [])[:10]]
    today = date.today()
    days_to_marathon = (date(2026, 10, 25) - today).days

    if DOCTOR_CLEARED:
        frame = f"""Der Sportler erholt sich von: {RECOVERY_REASON}.
Am {DOCTOR_DATE} war er beim Arzt. ÄRZTLICHE FREIGABE (maßgeblich): "{DOCTOR_GUIDANCE}"

Das heißt konkret (Stand 18.08., nach zweitem Infekt jetzt abgeklungen, Lunge frei):
- Wieder-Aufbau läuft: er ist schon zurück bei lockeren Läufen (zuletzt 10 km locker).
  Jetzt Umfang und Longrun BEHUTSAM steigern, um den Marathon (25.10., ~10 Wochen) vorzubereiten.
- Einheiten primär locker (Zone 2, ~140–150 bpm). Tempo nur einbauen, wenn mehrere Tage unauffällig.
- IMMER auf das Körpergefühl hören; bei erneutem Husten, Brustsymptomen, Herzstolpern oder
  ungewöhnlicher Erschöpfung sofort pausieren.
- Kein Leistungsdruck, aber der Marathon ist wieder das Ziel – geduldiger, gesunder Aufbau."""
        status_line = ('"recovery_status": "<Erholung | Wiedereinstieg | Rückschlag>",')
        advice_line = ('"recovery_advice": "<2–3 Sätze für HEUTE: Falls die Werte gut sind und '
                       'es nicht zu heiß ist, eine konkrete, sehr moderate Aktivität vorschlagen '
                       '(z.B. 20–30 Min lockeres Gehen/Radeln/kurzer Lauf nach Gefühl, max ~50%). '
                       'Bei Hitze oder schlechten Werten stattdessen Ruhe/leichte Bewegung. '
                       'Immer den Körpergefühl-Vorbehalt nennen.>")')
    else:
        frame = f"""Der Sportler ist KRANK: {RECOVERY_REASON}. Er darf NICHT trainieren.

Wichtiger medizinischer Kontext:
- Symptome "unterhalb des Halses" (Husten, belegte Lunge, Fieber, Gliederschmerzen) bedeuten
  in der Sportmedizin: KEIN Training. Sport während eines Atemwegsinfekts erhöht das Risiko
  einer Herzmuskelentzündung (Myokarditis) – umso mehr, da er gerade erst eine Borreliose
  (ebenfalls mit Herzrisiko) hinter sich hat.
- Bei belegter Lunge/schmerzhaftem Husten, Fieber, Atemnot oder Verschlechterung ärztlich
  abklären lassen (mögliche Bronchitis/Lungenbeteiligung).
Empfiehl UNTER KEINEN UMSTÄNDEN Training, auch kein "lockeres" Laufen/Radfahren."""
        status_line = '"recovery_status": "<Erholung | Stabil | Rückschlag>",'
        advice_line = ('"recovery_advice": "<2 Sätze Erholungsunterstützung für heute: Ruhe, '
                       'Schlaf, viel trinken, warmhalten. Bei anhaltendem Husten/belegter Lunge '
                       'ärztlich abklären. NIEMALS Training empfehlen.>")')

    prompt = f"""Du bist ein vorsichtiger Sportmediziner-Assistent. {frame}

Seine Normalwerte VOR der Infektion: Ruhepuls {BASELINE_RHR[0]}–{BASELINE_RHR[1]} bpm,
HRV {BASELINE_HRV[0]}–{BASELINE_HRV[1]} ms. Heute ist {today.strftime('%A, %d.%m.%Y')}.

Heutige Werte:
- Ruhepuls: {metrics.get("resting_hr")} bpm
- HRV: {metrics.get("hrv_value")} ms (Status {metrics.get("hrv_status")})
- Schlaf: {metrics.get("sleep_hours")} h (Score {metrics.get("sleep_score")}/100)
- Body Battery: {metrics.get("body_battery")}/100
- Training Readiness: {metrics.get("training_readiness")}/100
- Stress gestern: {metrics.get("stress")}/100

Verlauf (neueste zuerst):
- Ruhepuls letzte 10 Tage: {rhr_hist}
- HRV letzte 10 Tage: {hrv_hist}

Beurteile NÜCHTERN. Beachte: schlechter Schlaf allein drückt HRV und hebt den Ruhepuls –
unterscheide das von einem echten Rückschlag.

ZUSÄTZLICH – Marathon-On-Track (Ziel: Frankfurt 25.10.2026 unter 5:00 h, in {days_to_marathon} Tagen):
Er hatte vor der Krankheit eine solide Basis (21-km-Longrun, VO₂max ~45, ~40 km/Woche) und ist
jetzt im Wiedereinstieg. Schätze REALISTISCH und ehrlich, ob das Ziel noch machbar ist – die
Krankheit hat Wochen gekostet, aber die Basis ist da. Wenn Finish > 5:00 h, dann on_track_score < 70.

Antworte NUR mit diesem JSON (kein Markdown):
{{
  {status_line}
  "recovery_note": "<2 Sätze: wie stehen Ruhepuls, HRV und Schlaf im Vergleich zur Basis? Nüchtern.>",
  {advice_line},
  "predicted_finish_h": <realistische Marathon-Zielzeit in Stunden, z.B. 5.15, unter Berücksichtigung der Krankheitspause>,
  "on_track_score": <0–100, ehrlich; konsistent mit predicted_finish_h>,
  "on_track_note": "<1 Satz: wo steht er auf dem Weg zum Marathon, größter Hebel im Wiedereinstieg>",
  "factor_volume": <0–100: Laufumfang aktuell>,
  "factor_hrv": <0–100: Erholung/HRV>,
  "factor_vo2max": <0–100: Ausdauerbasis>,
  "factor_weight": <0–100: Gewicht Richtung 87 kg>
}}"""
    return _claude_json(prompt, max_tokens=850)


def call_claude(metrics, plan_context):
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
- VO₂max: {metrics.get("vo2max")}{" (letzter bekannter Wert, heute keine Messung – NICHT als Verschlechterung werten, factor_vo2max normal bewerten)" if metrics.get("vo2max_carried") else ""}{last_run_str}
- Letzte Aktivitäten (14 Tage): {json.dumps(metrics.get("recent_activities", [])[:7], ensure_ascii=False)}
- {plan_context}
- Bald ablaufende Challenges: {json.dumps(soon_challenges, ensure_ascii=False)}

REGEL 1 — Plan ist bindend: Die Empfehlung MUSS zum heute geplanten Training (Zeile "HEUTE GEPLANT") passen.
- Steht dort RUHETAG: empfiehl KEIN Laufen/Radfahren. Empfiehl Erholung, Mobilität, ggf. Spaziergang. Erkläre kurz warum Ruhe heute wichtig ist.
- Steht dort ein Lauf/Rad: bestätige oder passe an Tagesform an (z.B. bei schlechter Erholung kürzer/langsamer).
- Erfinde NIEMALS ein Training, das nicht im Plan steht.

REGEL 2 — REALISTISCHE Herzfrequenz (echte Werte, KEINE Lehrbuch-Formeln):
- Maximalpuls 201, Laktatschwelle 175, Ruhepuls 57. Lockere Läufe aktuell Ø 137–144 bpm.
- Zonen: lockerer Dauerlauf/GA1 ~140–156 bpm | Marathon-Renntempo ~150–162 | Tempo ~157–166 | Schwelle ~167–175.
- Easy-/Grundlagen-Empfehlung daher ~140–155 bpm. NIEMALS einen Puls-Deckel <140 nennen (da müsste er gehen).
- Bestes Maß ist der SPRECHTEST (ganze Sätze möglich = richtig), nicht eine starre Zahl.
- Pace-Logik: niedrigere min/km = SCHNELLER. "Zu intensiv" → nächster Lauf entspannter, NIE eine schnellere Pace als "locker" verkaufen.

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

    return _claude_json(prompt, max_tokens=1100)


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
    # Genesungs-Modus-Felder durchreichen (nur gesetzt, wenn aktiv)
    for k in ("recovery_mode", "recovery_reason", "recovery_since", "recovery_status",
              "recovery_note", "readiness_check", "baseline_rhr", "baseline_hrv",
              "doctor_cleared", "doctor_date", "doctor_guidance"):
        if k in claude_result:
            payload[k] = claude_result[k]
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

def load_existing_payload(html_content):
    """Bisherige GARMIN_DATA aus index.html lesen – dient als Rückfall für die
    Textfelder, falls Claude ausfällt. Besser alter guter Text als 'nicht verfügbar'."""
    m = re.search(r"window\.GARMIN_DATA\s*=\s*({.*?});", html_content, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except Exception:
        return {}


def load_garmin_data():
    """Liest die von sync_garmin.py (lokal) erzeugte garmin_data.json.

    Wirft, wenn die Datei fehlt oder keine Kerndaten enthält – dann darf
    index.html NICHT geschrieben werden, damit gute Daten nicht durch leere
    ersetzt werden.
    """
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    metrics = data.get("metrics") or {}
    core = [metrics.get("resting_hr"), metrics.get("hrv_value"), metrics.get("sleep_hours")]
    if all(v is None for v in core):
        raise RuntimeError("garmin_data.json enthält keine Kerndaten (Ruhepuls/HRV/Schlaf leer)")
    return data


def main():
    html_path = "index.html"
    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    # Daten kommen ausschließlich aus garmin_data.json (lokal befüllt).
    try:
        data = load_garmin_data()
    except FileNotFoundError:
        print(f"ABBRUCH: {DATA_PATH} fehlt. Zuerst lokal 'python3 sync_garmin.py' ausführen.")
        return 1
    except Exception as e:
        print(f"ABBRUCH: {e}")
        print("index.html bleibt unverändert – keine leeren Daten schreiben.")
        return 1

    metrics = data["metrics"]
    history = data.get("history") or {"hrv": [], "rhr": [], "weight": [],
                                      "weekly_km": [], "run_dyn": [], "vo2max": []}
    sync_date = data.get("sync_date", "")
    synced_at = data.get("synced_at", "")
    age_days = (date.today() - date.fromisoformat(sync_date)).days if sync_date else None
    print(f"Daten vom {sync_date} ({synced_at}), Alter: {age_days} Tage")
    metrics["data_sync_date"] = sync_date
    metrics["data_age_days"] = age_days   # nur informativ; das Dashboard rechnet selbst
    metrics["token_days_left"] = data.get("token_days_left")

    html = save_history(html, history)

    plan_context = get_plan_context(html)
    print(f"Plan-Kontext: {plan_context}")

    # ── Genesungs-Modus: keine Trainingsempfehlung, nur Erholungseinschätzung ──
    if RECOVERY_MODE:
        print(f"Genesungs-Modus aktiv ({RECOVERY_REASON}) – Modell {CLAUDE_MODEL}")
        try:
            rec = call_claude_recovery(metrics, history)
            print(json.dumps(rec, ensure_ascii=False))
        except Exception as e:
            # Vorherige Texte behalten statt sie durch Platzhalter zu ersetzen.
            prev = load_existing_payload(html)
            print(f"Claude (Genesung) fehlgeschlagen: {e} – behalte vorherige Texte.")
            rec = {
                "recovery_status": prev.get("recovery_status") or "Stabil",
                "recovery_note": prev.get("recovery_note") or "",
                "recovery_advice": prev.get("recommendation")
                                   or "Ruhe, ausreichend trinken, Schlaf priorisieren. Kein Training.",
                "readiness_check": prev.get("readiness_check") or "",
            }
        claude_result = {
            "recommendation": rec.get("recovery_advice", ""),
            "training_intensity": "Wiedereinstieg" if DOCTOR_CLEARED else "Genesung",
            "recovery_mode": True,
            "recovery_reason": RECOVERY_REASON,
            "recovery_since": RECOVERY_SINCE,
            "recovery_status": rec.get("recovery_status", ""),
            "recovery_note": rec.get("recovery_note", ""),
            "readiness_check": rec.get("readiness_check", ""),
            "doctor_cleared": DOCTOR_CLEARED,
            "doctor_date": DOCTOR_DATE,
            "doctor_guidance": DOCTOR_GUIDANCE,
            "baseline_rhr": list(BASELINE_RHR),
            "baseline_hrv": list(BASELINE_HRV),
            # On-Track-Prognose (Predictor bleibt sichtbar im Wiedereinstieg)
            "predicted_finish_h": rec.get("predicted_finish_h"),
            "on_track_score": rec.get("on_track_score", 55),
            "on_track_note": rec.get("on_track_note", ""),
            "factor_volume": rec.get("factor_volume", 40),
            "factor_hrv": rec.get("factor_hrv", 60),
            "factor_vo2max": rec.get("factor_vo2max", 75),
            "factor_weight": rec.get("factor_weight", 60),
            # Trainingsspezifische Felder bewusst neutral/leer
            "slider_sleep": metrics.get("sleep_hours") or 7.5,
            "slider_wellbeing": 2,
            "slider_hrv": 2,
            "challenge_alert": "",
            "run_feedback": "",
            "long_run_tips": None,
        }
        html = inject_garmin_data(html, metrics, claude_result)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        print("index.html aktualisiert (Genesungs-Modus).")
        return 0

    print("Claude API …")
    try:
        claude_result = call_claude(metrics, plan_context)
        print(json.dumps(claude_result, ensure_ascii=False))
    except Exception as e:
        # Kennzahlen trotzdem aktualisieren, aber die vorherigen Texte behalten.
        prev = load_existing_payload(html)
        print(f"Claude fehlgeschlagen: {e} – behalte vorherige Texte, Werte werden aktualisiert.")
        claude_result = {
            "recommendation": prev.get("recommendation", ""),
            "training_intensity": prev.get("training_intensity", "Mittel"),
            "slider_sleep": metrics.get("sleep_hours") or 7.5,
            "slider_wellbeing": prev.get("slider_wellbeing", 3),
            "slider_hrv": prev.get("slider_hrv", 2),
            "predicted_finish_h": prev.get("predicted_finish_h"),
            "on_track_score": prev.get("on_track_score", 65),
            "on_track_note": prev.get("on_track_note", ""),
            "factor_volume": prev.get("factor_volume", 50),
            "factor_hrv": prev.get("factor_hrv", 50),
            "factor_vo2max": prev.get("factor_vo2max", 50),
            "factor_weight": prev.get("factor_weight", 50),
            "challenge_alert": prev.get("challenge_alert", ""),
            "run_feedback": prev.get("run_feedback", ""),
        }

    html = inject_garmin_data(html, metrics, claude_result)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print("index.html aktualisiert.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
