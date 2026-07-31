#!/usr/bin/env python3
"""Baut die Trainingswochen W6..W18 (Wiedereinstieg nach Borreliose) neu und
spleisst sie in index.html. Weeks 0..5 (Reha/W1..W5, Historie) bleiben unberuehrt."""
import re, json

DAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

def wk(label, name, focus, stats, days):
    out = {"label": label, "name": name, "focus": focus,
           "stats": [{"l": l, "v": v} for l, v in stats], "days": []}
    pfx = label.lower()
    for i, (dname, title, badges, desc) in enumerate(days):
        d = {"id": f"{pfx}{DAYS[i].lower()}", "name": dname,
             "title": title, "badges": badges, "desc": desc}
        if "longrun" in badges:
            d["badges"] = [b for b in badges if b != "longrun"]
            d["longrun"] = True
        out["days"].append(d)
    return out

# Puls-Erinnerung: locker 140–155, Sprechtest. LT 175. Wiedereinstieg: alles sehr locker.
weeks6_18 = [

 wk("W6","Woche 6","Wiedereinstieg · Frequenz vor Dauer",
    [("Laufen","~15 km"),("Rad","optional"),("Intensität","nur Zone 2"),("Longrun","–")],
    [("Mo","Ruhetag",["rest"],"Nach der ersten Lauf-Woche zählt Erholung als Training. Schlaf priorisieren."),
     ("Di","Lauf locker · 4–5 km",["run","z2"],"Sehr locker, Puls ≤150, Sprechtest. Bei schweren Beinen kürzer."),
     ("Mi","Ruhetag",["rest"],"Pause. Nach Krankheit lieber ein Tag zu viel Ruhe als einer zu wenig."),
     ("Do","Lauf locker · 5–6 km",["run","z2"],"Gemütlich, nach Gefühl. Wenn der Puls klettert: Tempo raus, gehen ist erlaubt."),
     ("Fr","Ruhetag",["rest"],"Erholung. Wie fühlen sich die Beine an?"),
     ("Sa","Nach Gefühl · 5–6 km ODER Pause",["run","z2"],"Bei Hitze aussetzen (Arztvorgabe). Sonst locker. Kein Longrun diese Woche."),
     ("So","Ruhetag / Spaziergang",["rest"],"Bilanz der ersten Woche zurück. Nächste Woche kommt Struktur mit dem Pendeln.")]),

 wk("W7","Woche 7","Aufbau behutsam · Pendeln startet",
    [("Laufen","~20 km"),("Rad","Pendeln"),("Intensität","nur Zone 2"),("Longrun","8 km")],
    [("Mo · Büro","Rad-Pendeln locker",["bike","z2"],"Erster Bürotag zurück. Rad ganz gemütlich, Puls <130 – reine Erholung, kein Training."),
     ("Di · Büro","Rücklauf · 5–6 km",["run","z2"],"Abends heimlaufen (ganz oder Teilstrecke, Rest Bahn). Locker, Puls ≤150."),
     ("Mi","Ruhetag",["rest"],"Pflichtruhetag. Schlaf und Hamstring-Mobilität."),
     ("Do · Büro","Rücklauf · 6–7 km",["run","z2"],"Locker heimlaufen. Sprechtest muss gehen, sonst zu schnell."),
     ("Fr · Büro","Rad-Pendeln locker",["bike","z2"],"Lockeres Pendeln, Beine für den Longrun schonen."),
     ("Sa","Longrun-Aufbau · 8 km",["run","z2","longrun"],"Erster wieder etwas längerer Lauf. Ganz ruhig, 8:00+/km, viel trinken. Bei Hitze früh morgens."),
     ("So","Kraft · Hamstring",["kraft","rest"],"Nordic Curls, RDL leicht, Rumpf. Gegen die alte Quad-Dominanz. Kein Lauf.")]),

 wk("W8","Woche 8","Aufbau · Distanz vorsichtig steigern",
    [("Laufen","~28 km"),("Rad","Pendeln"),("Intensität","nur Zone 2"),("Longrun","11 km")],
    [("Mo · Büro","Rad-Pendeln locker",["bike","z2"],"Erholung nach Longrun/Kraft. Puls <130."),
     ("Di · Büro","Rücklauf · 7 km",["run","z2"],"Locker heimlaufen. Immer noch reine Grundlage, kein Tempo."),
     ("Mi","Ruhetag",["rest"],"Pause. Erholungswerte checken – Ruhepuls sollte ≤55 bleiben."),
     ("Do · Büro","Rücklauf · 8 km",["run","z2"],"Ruhig, Puls ≤150. Frequenz bewusst Richtung 165 halten."),
     ("Fr · Büro","Rad-Pendeln locker",["bike","z2"],"Locker, Beine schonen."),
     ("Sa","Longrun · 11 km",["run","z2","longrun"],"Behutsam länger. Zone 2, Start 8:00/km. Elektrolyte mitnehmen (Natrium!)."),
     ("So","Kraft · Hamstring",["kraft","rest"],"Zweite feste Krafteinheit. Hamstring-Fokus, Rumpf. Kein Lauf.")]),

 wk("W9","Woche 9","Aufbau · zurück Richtung Basis",
    [("Laufen","~34 km"),("Rad","Pendeln"),("Intensität","Z2, Ende Woche 1× zügig"),("Longrun","14 km")],
    [("Mo · Büro","Rad-Pendeln locker",["bike","z2"],"Erholung. Puls <130."),
     ("Di · Büro","Rücklauf · 8 km",["run","z2"],"Locker. Wenn sich alles leicht anfühlt, ist das das grüne Licht für mehr."),
     ("Mi","Ruhetag",["rest"],"Pause. Antikörper-Bluttest steht diese Wochen an – Termin nicht vergessen."),
     ("Do · Büro","Zügiger Dauerlauf · 8 km",["run","z2"],"Erste leicht flottere Einheit: letzte 3 km etwas zügiger (Puls bis ~158), aber weit unter Schwelle. Nur wenn die Woche sich gut anfühlte."),
     ("Fr · Büro","Rad-Pendeln locker",["bike","z2"],"Locker, Beine für den Longrun schonen."),
     ("Sa","Longrun · 14 km",["run","z2","longrun"],"Wieder Richtung ordentliche Länge. Strikt Zone 2, Gel ab km 10."),
     ("So","Kraft + Mobility",["kraft","rest"],"Hamstring, Rumpf, lockeres Dehnen. Kein Lauf.")]),

 wk("W10","Woche 10","Standortbestimmung · Entscheidung Marathon",
    [("Laufen","~34 km"),("Rad","Pendeln"),("Intensität","Zone 2"),("Longrun","16 km")],
    [("Mo · Büro","Rad-Pendeln locker",["bike","z2"],"Erholung. Diese Woche ehrlich Bilanz ziehen (siehe So)."),
     ("Di · Büro","Rücklauf · 8 km",["run","z2"],"Locker. Wie steht der Ruhepuls im Wochenschnitt vs. Basis (53–55)?"),
     ("Mi","Ruhetag",["rest"],"Pause."),
     ("Do · Büro","Rücklauf · 8–10 km",["run","z2"],"Ruhig. Frequenz und Bodenkontakt beobachten – sind sie wieder wie vor der Krankheit?"),
     ("Fr · Büro","Rad-Pendeln locker",["bike","z2"],"Locker."),
     ("Sa","Longrun · 16 km",["run","z2","longrun"],"Zurück auf dem Vor-Krankheits-Niveau. Wenn sich das gut anfühlt, ist der Marathon realistisch."),
     ("So","Bilanz + Kraft",["kraft","rest"],"ENTSCHEIDUNGSPUNKT: Antikörpertest + Körpergefühl + Werte. Marathon 25.10. weiter verfolgen oder Ziel verschieben? Ehrlich entscheiden.")]),

 wk("W11","Woche 11","Marathon-Build · Aufbau (falls Freigabe)",
    [("Laufen","~40 km"),("Rad","Pendeln"),("Intensität","Z2 + 1× LT kurz"),("Longrun","20 km")],
    [("Mo · Büro","Rad-Pendeln locker",["bike","z2"],"Erholung."),
     ("Di · Büro","Rücklauf · 10 km",["run","z2"],"Locker Grundlage."),
     ("Mi · Büro","Tempo kurz · 8 km",["run","lt"],"Erste echte Tempo-Einheit: 2× 8 Min an der Schwelle (Puls ~170), dazwischen locker. Nur wenn gesund."),
     ("Do","Ruhetag",["rest"],"Pause nach Tempo."),
     ("Fr · Büro","Rad-Pendeln locker",["bike","z2"],"Beine für den langen Lauf schonen."),
     ("Sa","Longrun · 20 km",["run","z2","longrun"],"Erster 20er seit der Krankheit. Zone 2, Verpflegung wie im Wettkampf üben."),
     ("So","Kraft · Hamstring",["kraft","rest"],"Erhaltung. Kein Lauf.")]),

 wk("W12","Woche 12","Peak-Block · Aufbau",
    [("Laufen","~46 km"),("Rad","Pendeln"),("Intensität","Z2 + 1× LT"),("Longrun","24 km")],
    [("Mo · Büro","Rad-Pendeln locker",["bike","z2"],"Erholung."),
     ("Di · Büro","Rücklauf · 10–12 km",["run","z2"],"Locker Grundlage."),
     ("Mi · Büro","Tempolauf · 10 km",["run","lt"],"3× 8 Min Schwelle, Puls ~170–174. Dazwischen 3 Min locker."),
     ("Do","Ruhetag",["rest"],"Pause."),
     ("Fr · Büro","Rad-Pendeln locker",["bike","z2"],"Schonen."),
     ("Sa","Longrun · 24 km",["run","z2","longrun"],"Solide Länge. Marathon-Verpflegung strikt üben, Elektrolyte."),
     ("So","Kraft + Mobility",["kraft","rest"],"Hamstring, Rumpf. Kein Lauf.")]),

 wk("W13","Woche 13","Entlastung · Deload",
    [("Laufen","~30 km"),("Rad","Pendeln"),("Intensität","nur Zone 2"),("Longrun","16 km")],
    [("Mo · Büro","Rad-Pendeln locker",["bike","z2"],"Erholung. Diese Woche bewusst weniger."),
     ("Di · Büro","Rücklauf · 8 km",["run","z2"],"Locker, kurz."),
     ("Mi","Ruhetag",["rest"],"Pause."),
     ("Do · Büro","Rücklauf · 8 km",["run","z2"],"Locker. Körper adaptiert die Belastung der letzten Wochen."),
     ("Fr · Büro","Rad-Pendeln locker",["bike","z2"],"Locker."),
     ("Sa","Longrun kurz · 16 km",["run","z2","longrun"],"Reduzierter Longrun, ganz entspannt."),
     ("So","Ruhetag",["rest"],"Volle Erholung vor dem nächsten Block.")]),

 wk("W14","Woche 14","Longrun-Peak · 28 km",
    [("Laufen","~48 km"),("Rad","Pendeln"),("Intensität","Z2 + 1× LT"),("Longrun","28 km")],
    [("Mo · Büro","Rad-Pendeln locker",["bike","z2"],"Erholung."),
     ("Di · Büro","Rücklauf · 12 km",["run","z2"],"Locker Grundlage."),
     ("Mi · Büro","Tempolauf · 10 km",["run","lt"],"3–4× 8 Min Schwelle. Puls ~172."),
     ("Do","Ruhetag",["rest"],"Pause vor dem langen Lauf."),
     ("Fr · Büro","Rad-Pendeln locker",["bike","z2"],"Schonen."),
     ("Sa","Longrun-Peak · 28 km",["run","z2","longrun"],"Der wichtigste lange Lauf. Renn-Verpflegung komplett durchspielen. Zone 2, letzte 5 km ggf. Marathon-Renntempo antesten."),
     ("So","Kraft leicht",["kraft","rest"],"Locker, Regeneration. Kein Lauf.")]),

 wk("W15","Woche 15","Letzter langer Block · 30 km",
    [("Laufen","~46 km"),("Rad","Pendeln"),("Intensität","Z2 + Renntempo"),("Longrun","30 km")],
    [("Mo · Büro","Rad-Pendeln locker",["bike","z2"],"Erholung."),
     ("Di · Büro","Rücklauf · 12 km",["run","z2"],"Locker."),
     ("Mi · Büro","Marathon-Renntempo · 12 km",["run","lt"],"3× 3 km im Zieltempo (~7:00/km, Puls ~155–160). Renngefühl bekommen."),
     ("Do","Ruhetag",["rest"],"Pause."),
     ("Fr · Büro","Rad-Pendeln locker",["bike","z2"],"Schonen."),
     ("Sa","Longrun · 30 km",["run","z2","longrun"],"Letzter sehr langer Lauf. Danach beginnt das Tapering. Alles wie am Renntag."),
     ("So","Ruhetag",["rest"],"Volle Erholung.")]),

 wk("W16","Woche 16","Taper Beginn · Volumen −30%",
    [("Laufen","~32 km"),("Rad","Pendeln"),("Intensität","Z2 + kurzes Tempo"),("Longrun","20 km")],
    [("Mo · Büro","Rad-Pendeln locker",["bike","z2"],"Erholung. Ab jetzt runterfahren, nicht mehr aufbauen."),
     ("Di · Büro","Rücklauf · 10 km",["run","z2"],"Locker."),
     ("Mi · Büro","Renntempo kurz · 8 km",["run","lt"],"2× 2 km Zieltempo, spritzig halten ohne zu ermüden."),
     ("Do","Ruhetag",["rest"],"Pause."),
     ("Fr · Büro","Rad-Pendeln locker",["bike","z2"],"Locker."),
     ("Sa","Longrun reduziert · 20 km",["run","z2","longrun"],"Deutlich kürzer als Peak. Beine bleiben an Länge gewöhnt, erholen sich aber."),
     ("So","Ruhetag",["rest"],"Erholung.")]),

 wk("W17","Woche 17","Taper · Spritzigkeit",
    [("Laufen","~22 km"),("Rad","optional"),("Intensität","kurz + Renntempo"),("Longrun","13 km")],
    [("Mo","Ruhetag",["rest"],"Erholung, Beine frisch machen."),
     ("Di · Büro","Rücklauf · 8 km",["run","z2"],"Locker, kurz."),
     ("Mi · Büro","Renntempo · 6 km",["run","lt"],"3× 1 km Zieltempo. Beine wach halten, nicht ermüden."),
     ("Do","Ruhetag",["rest"],"Pause."),
     ("Fr","Locker · 5 km",["run","z2"],"Ganz locker, Lockerungslauf."),
     ("Sa","Longrun kurz · 13 km",["run","z2","longrun"],"Letzter etwas längerer Lauf. Entspannt."),
     ("So","Ruhetag",["rest"],"Erholung. Nächste Woche ist Renn-Woche.")]),

 wk("W18","Renn-Woche","Taper-Ende · MARATHON",
    [("Laufen","~15 km"),("Rad","–"),("Intensität","Wettkampf"),("Longrun","42,2 km")],
    [("Mo","Ruhetag",["rest"],"Erholung. Kohlenhydrate hochfahren beginnen."),
     ("Di","Locker · 6 km + Steigerungen",["run","z2"],"Kurz, mit 4× 20 s zügig. Beine spritzig halten."),
     ("Mi","Ruhetag",["rest"],"Pause."),
     ("Do","Locker · 4 km",["run","z2"],"Ganz kurz, lockern. Danach nur noch Ruhe."),
     ("Fr","Ruhetag",["rest"],"Beine hoch. Carbo-Loading, viel trinken."),
     ("Sa","Ausschütteln · 3 km",["run","z2"],"Optional 15 Min ganz locker + 2 Steigerungen. Ausrüstung bereitlegen."),
     ("So","MARATHON FRANKFURT",["run","lt"],"25.10. Renntag! Zieltempo ~7:00/km, Puls kontrolliert unter der Schwelle. Verpflegung wie geübt. Genieß es – nach allem, was hinter dir liegt.")]),
]

html = open("index.html", encoding="utf-8").read()
m = re.search(r"const weeks = (\[.*?\n\]\s*);", html, re.DOTALL)
weeks = json.loads(m.group(1))
weeks = weeks[:6] + weeks6_18            # 0..5 behalten, 6..18 ersetzen
assert len(weeks) == 19, len(weeks)
new = "const weeks = " + json.dumps(weeks, ensure_ascii=False, indent=2) + ";"
html = html[:m.start()] + new + html[m.end():]
open("index.html", "w", encoding="utf-8").write(html)
print(f"Plan neu gebaut: {len(weeks)} Wochen, W6..W18 ersetzt.")
