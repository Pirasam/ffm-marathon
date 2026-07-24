# Marathon-Dashboard Frankfurt

Live: **https://pirasam.github.io/ffm-marathon/**

## Wie es läuft

```
06:58  Mac wacht auf  ->  sync_garmin.py  ->  garmin_data.json  ->  push
          |                                                          |
          |                                        loest Rendern aus v
       (schlaeft weiter)                    GitHub: Claude -> index.html
```

Zusaetzlich versucht GitHub selbst 3x vormittags zu synchronisieren (07:00,
09:00, 11:00) – das klappt aber nur, solange der Garmin-Token frisch ist
(siehe unten). Verlass dich auf den Mac; die Cloud ist Beiwerk.

**Warum der Mac?** Garmins Zugriffs-Token gilt nur ~24 h. Das Erneuern wird
aus GitHub-Netzen blockiert (429). Vom Mac aus funktioniert es. Deshalb muss
der Mini nachts schlafen (nicht ausschalten) und um 06:58 aufwachen:

```bash
sudo pmset repeat wake MTWRFSU 06:58:00     # einmalig, braucht dein Passwort
pmset -g sched                              # pruefen
```

## Der Wartungsfall: Garmin-Login erneuern

Der Login traegt ~30 Tage. Vorher warnen Log **und Dashboard** sichtbar.
Dann:

```bash
cd ~/ffm-marathon
python3 generate_session.py          # Garmin-Login + ggf. 2FA
cat garmin_secret.txt | pbcopy       # Token kopieren
```

Einfuegen unter:
https://github.com/Pirasam/ffm-marathon/settings/secrets/actions/GARMIN_SESSION_DATA

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
