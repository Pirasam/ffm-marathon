#!/bin/bash
# Dauerhafter Remote-Control-Dienst (von launchd gestartet, KeepAlive).
#
# Haelt auf dem immer laufenden Mac Mini rund um die Uhr eine Claude-Code-Session
# bereit, die Samuel vom Handy/Browser (claude.ai/code) aus steuern kann.
#
#  - ensure_trust.py markiert den Projektordner als vertraut (headless-Start ok)
#  - caffeinate -s verhindert System-Schlaf, damit die Session online bleibt
#  - claude remote-control laeuft im Server-Modus und pollt nach Verbindungen
#
# Beendet sich der Prozess (z.B. laengerer Netzausfall), startet launchd ihn neu.

set -uo pipefail

REPO="$HOME/ffm-marathon"
CLAUDE="$HOME/.local/bin/claude"
LOG="$REPO/logs/remote_control.log"

mkdir -p "$REPO/logs"
cd "$REPO" || { echo "Repo nicht gefunden: $REPO" >> "$LOG"; exit 1; }

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Remote-Control-Dienst startet …" >> "$LOG"

# Projektordner als vertraut sicherstellen (idempotent, selbstheilend).
/usr/bin/python3 "$REPO/ensure_trust.py" >> "$LOG" 2>&1 || true

# Server-Modus starten; caffeinate haelt den Mac wach, solange der Dienst laeuft.
exec /usr/bin/caffeinate -s "$CLAUDE" remote-control --name "Mac-Mini · ffm-marathon"
