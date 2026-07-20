# Marathon-Dashboard Frankfurt

Live: **https://pirasam.github.io/ffm-marathon/**

## Wie es läuft (du musst nichts tun)

```
07:00  Mac          sync_garmin.py   →  garmin_data.json  →  git push
         ↓ (Push löst aus)
       GitHub       update_plan.py   →  Claude Opus 4.8   →  index.html
         ↓
       GitHub Pages → Dashboard aktuell
```

**Warum diese Aufteilung?** Garmin blockt den Token-Refresh aus GitHub-Servern
mit `429 Too Many Requests` — vom Mac aus funktioniert er zuverlässig. Der
Anthropic-Key liegt dagegen nur in GitHub. Also holt der Mac die Daten, die
Cloud macht die Analyse. Jeder Teil macht nur das, was er kann.

Der **Push der Daten** ist der Auslöser fürs Rendern — nicht der GitHub-Zeitplan,
der sich um Stunden verspätet hat. Zwei geplante Läufe (07:30, 09:00) bleiben nur
als Sicherheitsnetz.

## Dateien

| Datei | Zweck | Läuft wo |
|---|---|---|
| `garmin_client.py` | Garmin-API (Login, Kennzahlen, Laufdynamik, Challenges) | nur lokal |
| `sync_garmin.py` | Holt Daten → `garmin_data.json` | nur lokal |
| `daily_sync.sh` | launchd-Runner: Sync + Commit + Push | nur lokal |
| `update_plan.py` | Liest JSON → Claude → `index.html` | Cloud |
| `garmin_data.json` | Einzige Datenquelle fürs Dashboard | im Repo |
| `generate_session.py` | Garmin-Login erneuern (siehe unten) | nur lokal |

## Sicherheitsnetze

- **Garmin-Abruf schlägt fehl** → `garmin_data.json` bleibt unangetastet, kein Push.
  Alte gute Daten werden nie durch leere ersetzt.
- **Claude schlägt fehl** → Kennzahlen werden aktualisiert, die vorherigen Texte
  bleiben stehen (kein „nicht verfügbar").
- **Mac war aus** → launchd holt den Lauf beim Aufwachen nach. Bleiben die Daten
  älter als 1 Tag, zeigt das Dashboard eine deutliche Warnung mit Alter statt so
  zu tun, als wäre alles frisch.
- **Kein Netz** → Skript beendet sich still, ohne Schaden.

## Wenn doch mal was klemmt

**Prüfen, was zuletzt passiert ist:**
```bash
tail -30 ~/ffm-marathon/logs/sync.log
```

**Sync von Hand anstoßen:**
```bash
cd ~/ffm-marathon && ./daily_sync.sh && tail -20 logs/sync.log
```

**Automatik-Status:**
```bash
launchctl print gui/$(id -u)/com.pirasam.garmin-sync | grep -E "state|last exit"
```

**Garmin-Login abgelaufen** (ca. 1× im Jahr, Log zeigt Login-Fehler):
```bash
cd ~/ffm-marathon && python3 generate_session.py
```

## Wichtig

- Das Repo liegt in `~/ffm-marathon`. Auf dem Schreibtisch ist nur ein Verweis —
  macOS verbietet Hintergrundjobs den Zugriff auf `~/Desktop`.
- `garmin_secret.txt` und `logs/` sind in `.gitignore` und dürfen nie ins Repo.
- Der Genesungsmodus (keine Trainingsempfehlungen) wird in `update_plan.py` über
  `RECOVERY_MODE = True` gesteuert. Zum Beenden auf `False` setzen.
