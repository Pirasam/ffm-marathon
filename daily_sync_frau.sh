#!/bin/bash
# Taeglicher Garmin-Sync fuer Carinas Dashboard (von launchd aufgerufen).
#
# Unterschied zu daily_sync.sh (Samuel):
#  - laeuft ueber uv/Python 3.13 (Garmins neuer Login braucht neue Bibliothek)
#  - rendert das Dashboard LOKAL (render_frau.py, deterministisch, kein API-Key)
#  - committet+pusht frau/garmin_data.json UND frau/index.html
#    (kein Cloud-Render noetig)
#
# Schreibt NUR bei Erfolg. Schlaegt der Abruf fehl, bleiben die alten Daten stehen.

set -uo pipefail

REPO="$HOME/ffm-marathon"
LOG="$REPO/logs/sync_frau.log"
UV="$HOME/.local/bin/uv"
PY="/usr/bin/python3"
DATA="frau/garmin_data.json"
HTML="frau/index.html"

mkdir -p "$REPO/logs"
exec >> "$LOG" 2>&1

echo "════════════════════════════════════════════════════════"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Start (frau)"

cd "$REPO" || { echo "FEHLER: Repo nicht gefunden: $REPO"; exit 1; }

# Selbstheilung: haengender Rebase blockiert sonst jeden weiteren Lauf.
if [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; then
  echo "WARNUNG: haengender Rebase gefunden – wird aufgeraeumt."
  git rebase --abort 2>/dev/null || true
  rm -rf .git/rebase-merge .git/rebase-apply
fi

# Nur ihre Datendatei auf Serverstand bringen (nicht das ganze Repo).
git fetch --quiet origin main 2>/dev/null || true
git checkout --quiet origin/main -- "$DATA" 2>/dev/null || true

# Drosselung: nicht oefter als alle 8 Minuten (ausser --force).
if [ "${1:-}" != "--force" ] && [ -f "$DATA" ]; then
  AGE=$("$PY" - "$DATA" <<'PY' 2>/dev/null || echo 9999
import json, datetime, sys
try:
    t = json.load(open(sys.argv[1])).get("synced_at","")
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

# Netzwerk da?
if ! /sbin/ping -c1 -t5 connect.garmin.com >/dev/null 2>&1; then
  echo "Kein Netz / Garmin nicht erreichbar – Abbruch, kein Schaden."
  exit 0
fi

# 1) Garmin-Daten holen (neue Bibliothek via uv)
if ! "$UV" run --python 3.13 --with garminconnect --with requests --quiet \
      python sync_garmin.py --profile frau; then
  echo "FEHLER: sync_garmin.py (frau) fehlgeschlagen – alte Daten bleiben erhalten."
  exit 1
fi

# 2) Nur weiter, wenn sich die WERTE geaendert haben (synced_at/Token zaehlen nicht).
CHANGED=$("$PY" - "$DATA" <<'PY' 2>/dev/null || echo yes
import json, subprocess, sys
def core(src):
    try:
        d = json.loads(src)
        m = dict(d.get("metrics", {})); m.pop("_errors", None)
        return json.dumps({"m": m, "h": d.get("history")}, sort_keys=True)
    except Exception:
        return None
now = core(open(sys.argv[1]).read())
try:
    prev = core(subprocess.check_output(["git","show","origin/main:"+sys.argv[1]]).decode())
except Exception:
    prev = None
print("no" if (now is not None and now == prev) else "yes")
PY
)
if [ "$CHANGED" = "no" ]; then
  echo "Werte unveraendert – nichts zu pushen."
  git checkout --quiet -- "$DATA" 2>/dev/null || true
  echo "[$(date '+%H:%M:%S')] Fertig (unveraendert)"
  exit 0
fi

# 3) Dashboard lokal rendern (deterministisch, kein API-Key)
if ! "$PY" render_frau.py; then
  echo "FEHLER: render_frau.py fehlgeschlagen."
  exit 1
fi

git add "$DATA" "$HTML"
git -c user.name="Garmin Sync" -c user.email="garmin-sync@local" \
    commit -q -m "Carina: Garmin-Daten + Dashboard $(date +%Y-%m-%d)"

# 4) Push mit Konflikt-Auffang (frisch gesyncte Daten gewinnen).
for i in 1 2 3; do
  if ! git pull --rebase --autostash --quiet origin main 2>/dev/null; then
    if [ -n "$(git diff --name-only --diff-filter=U 2>/dev/null)" ]; then
      echo "Konflikt – behalte die frisch gesyncten Daten."
      git checkout --theirs -- "$DATA" "$HTML" 2>/dev/null || true
      git add "$DATA" "$HTML" 2>/dev/null || true
      GIT_EDITOR=true git rebase --continue >/dev/null 2>&1 || {
        git rebase --abort 2>/dev/null || true
        rm -rf .git/rebase-merge .git/rebase-apply
      }
    fi
  fi
  if git push --quiet origin main 2>/dev/null; then
    echo "Push erfolgreich (Versuch $i)."
    echo "[$(date '+%H:%M:%S')] Fertig – Carinas Dashboard aktualisiert."
    exit 0
  fi
  echo "Push-Versuch $i fehlgeschlagen, neuer Versuch in 20s …"
  sleep 20
done

echo "FEHLER: Push nach 3 Versuchen fehlgeschlagen. Commit liegt lokal bereit."
exit 1
