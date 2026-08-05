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

# Selbstheilung: ein haengender Rebase blockierte sonst JEDEN weiteren Lauf –
# genau das ist am 22.07. passiert, danach lief der Sync tagelang ins Leere.
if [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; then
  echo "WARNUNG: haengender Rebase gefunden – wird aufgeraeumt."
  git rebase --abort 2>/dev/null || true
  rm -rf .git/rebase-merge .git/rebase-apply
fi

# Nur die Datendatei auf Serverstand bringen (NICHT das ganze Repo – sonst
# waeren lokale Code-Aenderungen weg). Sie wird gleich neu geschrieben.
git fetch --quiet origin main 2>/dev/null || true
git checkout --quiet origin/main -- garmin_data.json 2>/dev/null || true

# Drosselung: nicht oefter als alle 8 Minuten (ausser --force). So kann der Job
# haeufig laufen und trotzdem neue Trainings zeitnah einsammeln, ohne zu hammern.
if [ "${1:-}" != "--force" ] && [ -f garmin_data.json ]; then
  AGE=$("$PY" - <<'PY' 2>/dev/null || echo 9999
import json, datetime
try:
    t = json.load(open("garmin_data.json")).get("synced_at","")
    dt = datetime.datetime.fromisoformat(t)
    print(int((datetime.datetime.now(dt.tzinfo) - dt).total_seconds() // 60))
except Exception:
    print(9999)
PY
)
  if [ "$AGE" -lt 8 ] 2>/dev/null; then
    echo "Vor $AGE Min gesynct – Drosselung, nichts zu tun."
    exit 0
  fi
fi

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

# 2) Nur committen, wenn sich die WERTE geaendert haben (synced_at/Token-Restlauf
#    aendern sich jeden Lauf – die zaehlen nicht, sonst Push-Spam alle paar Minuten).
CHANGED=$("$PY" - <<'PY' 2>/dev/null || echo yes
import json, subprocess
def core(src):
    try:
        d = json.loads(src)
        m = dict(d.get("metrics", {})); m.pop("_errors", None)
        return json.dumps({"m": m, "h": d.get("history")}, sort_keys=True)
    except Exception:
        return None
now = core(open("garmin_data.json").read())
try:
    prev = core(subprocess.check_output(["git","show","origin/main:garmin_data.json"]).decode())
except Exception:
    prev = None
print("no" if (now is not None and now == prev) else "yes")
PY
)
if [ "$CHANGED" = "no" ]; then
  echo "Werte unveraendert – nichts zu pushen."
  git checkout --quiet -- garmin_data.json 2>/dev/null || true
  echo "[$(date '+%H:%M:%S')] Fertig (unveraendert)"
  exit 0
fi

git add garmin_data.json
git -c user.name="Garmin Sync" -c user.email="garmin-sync@local" \
    commit -q -m "Garmin-Daten $(date +%Y-%m-%d)"

# 3) Push. Bei Konflikt gewinnt IMMER die frisch gesyncte Datei – sie wird
#    jeden Lauf komplett neu geschrieben, ein Zusammenfuehren waere sinnlos.
for i in 1 2 3; do
  if ! git pull --rebase --autostash --quiet origin main 2>/dev/null; then
    if [ -n "$(git diff --name-only --diff-filter=U 2>/dev/null)" ]; then
      echo "Konflikt – behalte die frisch gesyncten Daten."
      git checkout --theirs -- garmin_data.json 2>/dev/null || true
      git add garmin_data.json 2>/dev/null || true
      GIT_EDITOR=true git rebase --continue >/dev/null 2>&1 || {
        git rebase --abort 2>/dev/null || true
        rm -rf .git/rebase-merge .git/rebase-apply
      }
    fi
  fi
  if git push --quiet origin main 2>/dev/null; then
    echo "Push erfolgreich (Versuch $i)."
    echo "[$(date '+%H:%M:%S')] Fertig – Actions rendert jetzt das Dashboard."
    exit 0
  fi
  echo "Push-Versuch $i fehlgeschlagen, neuer Versuch in 20s …"
  sleep 20
done

echo "FEHLER: Push nach 3 Versuchen fehlgeschlagen. Commit liegt lokal bereit."
exit 1
