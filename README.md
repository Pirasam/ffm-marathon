# Marathon-Dashboard Frankfurt

Live: **https://pirasam.github.io/ffm-marathon/**

## Wie es läuft (du musst nichts tun)

Alles passiert in der Cloud — **unabhängig davon, ob dein Mac an ist.**

```
07:00 (UTC 05:00)   GitHub Actions
   1. sync_garmin.py   Garmin-Daten holen   → garmin_data.json
   2. update_plan.py   Claude Opus 4.8      → index.html
   3. push             → GitHub Pages aktualisiert das Dashboard
```

Zwei weitere Zeitfenster (07:40, 08:30) fangen ab, wenn GitHubs Zeitplan sich
verspätet. Liegen die Daten des Tages schon vor, brechen sie sofort ab.

**Der Mac ist nur Redundanz, keine Voraussetzung.** Läuft er (per launchd,
5 Zeitfenster), synct er ebenfalls und pusht — das löst dann direkt ein Rendern
aus. Ist er aus, macht die Cloud alles allein.

## Was wann schiefgehen kann

| Problem | Was passiert | Was du tun musst |
|---|---|---|
| Garmin antwortet mit 429 | 4 Versuche mit wachsender Pause; klappt es nicht, wird aus den letzten guten Daten gerendert | nichts |
| Garmin-Token abgelaufen (401) | Dashboard zeigt Datenalter **in Rot** mit Hinweis | Token erneuern (unten) |
| Claude nicht erreichbar | Kennzahlen werden aktualisiert, vorherige Texte bleiben stehen | nichts |
| Mac aus | Cloud macht alles | nichts |

**Grundregel:** Es wird nie etwas Gutes durch etwas Leeres ersetzt. Schlägt ein
Schritt fehl, bleibt der vorherige Stand erhalten und das Alter wird sichtbar
ausgewiesen — statt so zu tun, als wäre alles frisch.

## Der einzige Wartungsfall: Garmin-Token

Der Token hält etwa ein Jahr. Läuft er ab, zeigt das Dashboard eine rote
Warnung mit dem Datenalter. Dann:

```bash
cd ~/ffm-marathon
python3 generate_session.py          # fragt Garmin-Login + ggf. 2FA
cat garmin_secret.txt | pbcopy       # Token in die Zwischenablage
```

Dann einfügen unter:
https://github.com/Pirasam/ffm-marathon/settings/secrets/actions/GARMIN_SESSION_DATA

## Dateien

| Datei | Zweck |
|---|---|
| `garmin_client.py` | Garmin-API: Login (mit Retry), Kennzahlen, Laufdynamik, Challenges |
| `sync_garmin.py` | Holt Daten → `garmin_data.json`; schreibt nie leere Daten |
| `update_plan.py` | Liest JSON → Claude → `index.html`; bricht ohne Daten ab |
| `garmin_data.json` | Einzige Datenquelle fürs Dashboard (inkl. Historie) |
| `daily_sync.sh` + `com.pirasam.garmin-sync.plist` | Optionale Mac-Redundanz |
| `generate_session.py` | Garmin-Login erneuern |

## Nachschauen, was passiert ist

- **Cloud:** https://github.com/Pirasam/ffm-marathon/actions
- **Mac:** `tail -30 ~/ffm-marathon/logs/sync.log`

## Hinweise

- Das Repo liegt in `~/ffm-marathon`, auf dem Schreibtisch ist nur ein Verweis —
  macOS verbietet Hintergrundjobs den Zugriff auf `~/Desktop`.
- `garmin_secret.txt` und `logs/` sind in `.gitignore` und gehören nie ins Repo.
- Genesungsmodus (keine Trainingsempfehlungen) steuert `RECOVERY_MODE` in
  `update_plan.py`. Zum Beenden auf `False` setzen.
