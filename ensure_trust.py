#!/usr/bin/env python3
"""Markiert ~/ffm-marathon als von Claude Code 'vertrauten' Ordner.

Noetig, damit `claude remote-control` headless (unter launchd, ohne TTY) starten
kann, ohne am interaktiven Vertrauens-Dialog haengenzubleiben. Idempotent: setzt
den Eintrag nur, wenn er fehlt. Wird bei jedem Dienststart erneut geprueft und
heilt sich damit selbst, falls die Datei zwischendurch ueberschrieben wurde.

Nur dieser eine, dem Nutzer gehoerende Projektordner wird als vertraut markiert.
"""
import json
import os

P = os.path.expanduser("~/.claude.json")
REPO = os.path.expanduser("~/ffm-marathon")

try:
    with open(P) as f:
        d = json.load(f)
except Exception as e:
    raise SystemExit(f"~/.claude.json nicht lesbar: {e}")

projs = d.setdefault("projects", {})
entry = projs.get(REPO) or {}

# Zusaetzlich das einmalige Remote-Control-Zustimmungs-Flag absichern, damit der
# headless-Dienst nie am "Enable Remote Control? (y/n)"-Dialog haengt.
changed = False

if not entry.get("hasTrustDialogAccepted"):
    defaults = {
        "allowedTools": [],
        "disabledMcpjsonServers": [],
        "enabledMcpjsonServers": [],
        "hasClaudeMdExternalIncludesApproved": False,
        "hasClaudeMdExternalIncludesWarningShown": False,
        "hasTrustDialogAccepted": True,
        "projectOnboardingSeenCount": 1,
        "mcpContextUris": [],
    }
    projs[REPO] = {**defaults, **entry, "hasTrustDialogAccepted": True}
    changed = True
    print(f"Trust gesetzt für {REPO}")
else:
    print(f"Trust bereits vorhanden für {REPO}")

if d.get("remoteDialogSeen") is not True:
    d["remoteDialogSeen"] = True
    changed = True
    print("remoteDialogSeen gesetzt (kein y/n-Dialog mehr)")

if changed:
    tmp = P + ".tmp"
    with open(tmp, "w") as f:
        json.dump(d, f, indent=2)
    os.replace(tmp, P)
else:
    print("Nichts zu tun – bereits eingerichtet.")
