#!/bin/bash
# Taeglicher lokaler Garmin-Sync (von launchd aufgerufen).
#
# Holt die Garmin-Daten auf diesem Mac (aus GitHub-IPs blockt Garmin mit 429),
# committet garmin_data.json und pusht. Der Push loest in GitHub Actions das
# Rendern des Dashboards aus (dort liegt der Anthropic-Key).
#
# Schreibt NUR bei Erfolg. Schlaegt der Abruf fehl, bleiben die alten Daten stehen.

set -uo pipefail

REPO="$HOME/ffm-marathon"
LOG="$REPO/logs/sync.log"
PY="/usr/bin/python3"

mkdir -p "$REPO/logs"
exec >> "$LOG" 2>&1

echo "════════════════════════════════════════════════════════"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Start"

cd "$REPO" || { echo "FEHLER: Repo nicht gefunden: $REPO"; exit 1; }

# Netzwerk da? Sonst still beenden (z.B. Mac ohne WLAN aufgewacht).
if ! /sbin/ping -c1 -t5 connect.garmin.com >/dev/null 2>&1; then
  echo "Kein Netz / Garmin nicht erreichbar – Abbruch, kein Schaden."
  exit 0
fi

# 1) Garmin-Daten holen
if ! "$PY" sync_garmin.py; then
  echo "FEHLER: sync_garmin.py fehlgeschlagen – alte Daten bleiben erhalten."
  exit 1
fi

# 2) Nur committen, wenn sich wirklich etwas geaendert hat.
#    git status erfasst auch noch unversionierte Dateien (git diff nicht).
if [ -z "$(git status --porcelain -- garmin_data.json)" ]; then
  echo "Keine Aenderung an garmin_data.json – nichts zu pushen."
  echo "[$(date '+%H:%M:%S')] Fertig (unveraendert)"
  exit 0
fi

git add garmin_data.json
git -c user.name="Garmin Sync" -c user.email="garmin-sync@local" \
    commit -q -m "Garmin-Daten $(date +%Y-%m-%d)"

# 3) Push (mit Rebase, falls die Cloud parallel index.html committet hat).
#    --autostash: sonstige lokale Aenderungen blockieren den Rebase nicht.
for i in 1 2 3; do
  if git pull --rebase --autostash --quiet origin main && git push --quiet origin main; then
    echo "Push erfolgreich (Versuch $i)."
    echo "[$(date '+%H:%M:%S')] Fertig – Actions rendert jetzt das Dashboard."
    exit 0
  fi
  echo "Push-Versuch $i fehlgeschlagen, neuer Versuch in 20s …"
  sleep 20
done

echo "FEHLER: Push nach 3 Versuchen fehlgeschlagen. Commit liegt lokal bereit."
exit 1
