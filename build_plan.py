#!/usr/bin/env python3
"""Baut W6..W18 (Wiedereinstieg nach Borreliose) und spleisst sie in index.html.
Umfaenge/Longruns/Intensitaet nach dem gegengecheckten Plan (progressiver als v1).
Weeks 0..5 (Historie) bleiben unberuehrt.
Puls-Leitplanken: locker 140-150 | zuegiger Reiz 142-148 | Marathonbelastung 145-151 | LT ~172."""
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

RAD = ("Rad-Pendeln locker", ["bike","z2"], "Locker pendeln, Puls <130 – reine Erholung, kein Reiz.")
KRAFT = ("Kraft · Hamstring", ["kraft","rest"], "Nordic Curls, RDL, Rumpf. Gegen Quad-Dominanz. Kein Lauf.")
REST = ("Ruhetag", ["rest"], "Pause. Erholung ist im Wiedereinstieg Teil des Trainings.")

weeks6_18 = [

 wk("W6","Woche 6","Wiedereinstieg · Frequenz vor Dauer",
    [("Laufen","~15 km"),("Rad","optional"),("Intensität","nur locker"),("Longrun","–")],
    [("Mo",*REST),
     ("Di","Lauf locker · 4–5 km",["run","z2"],"Sehr locker, Puls ≤150, Sprechtest. Bei schweren Beinen kürzer."),
     ("Mi",*REST),
     ("Do","Lauf locker · 5–6 km",["run","z2"],"Gemütlich nach Gefühl. Puls klettert? Tempo raus, gehen erlaubt."),
     ("Fr",*REST),
     ("Sa","Nach Gefühl · 5–6 km ODER Pause",["run","z2"],"Bei Hitze aussetzen. Sonst locker. Noch kein Longrun."),
     ("So","Ruhetag / Spaziergang",["rest"],"Bilanz erste Woche. Ab Montag Struktur mit Büro-Pendeln.")]),

 wk("W7","Woche 7","Aufbau · komplett locker (22–25 km)",
    [("Laufen","22–25 km"),("Rad","Pendeln"),("Intensität","komplett locker"),("Longrun","11 km")],
    [("Mo · Büro",*RAD),
     ("Di · Büro","Rücklauf · 6 km",["run","z2"],"Heimlaufen (ganz oder Teilstrecke). Locker, Puls 140–150."),
     ("Mi",*REST),
     ("Do · Büro","Rücklauf · 7 km",["run","z2"],"Locker, Sprechtest muss gehen. Kein Tempo diese Woche."),
     ("Fr · Büro",*RAD),
     ("Sa","Longrun · 11 km",["run","z2","longrun"],"Komplett locker, 8:00+/km. Bei Hitze früh morgens, Elektrolyte."),
     ("So",*KRAFT)]),

 wk("W8","Woche 8","Aufbau · locker + Steigerungen (28–32 km)",
    [("Laufen","28–32 km"),("Rad","Pendeln"),("Intensität","locker + Steigerungen"),("Longrun","14 km")],
    [("Mo · Büro",*RAD),
     ("Di · Büro","Rücklauf · 8 km + Steigerungen",["run","z2"],"Locker, am Ende 4× 20 s zügig (kein Sprint) für die Spritzigkeit."),
     ("Mi",*REST),
     ("Do · Büro","Rücklauf · 9 km",["run","z2"],"Ruhig, Puls 140–150. Frequenz Richtung 165 halten."),
     ("Fr · Büro",*RAD),
     ("Sa","Longrun · 14 km",["run","z2","longrun"],"Zone 2, Start 8:00/km, Gel ab km 10. Natrium mitnehmen."),
     ("So",*KRAFT)]),

 wk("W9","Woche 9","Aufbau · erste moderate Abschnitte (33–37 km)",
    [("Laufen","33–37 km"),("Rad","Pendeln"),("Intensität","1× moderat"),("Longrun","18 km")],
    [("Mo · Büro",*RAD),
     ("Di · Büro","Rücklauf · 9 km",["run","z2"],"Locker. Fühlt sich alles leicht an, ist das grünes Licht für mehr."),
     ("Mi",*REST),
     ("Do · Büro","Zügiger Reiz · 9 km",["run","z2"],"Erster flotterer Reiz (nur wenn Woche unauffällig): 20–25 Min bei 142–148 bpm, Rest locker."),
     ("Fr · Büro",*RAD),
     ("Sa","Longrun · 18 km",["run","z2","longrun"],"Zone 2, letzte 3–4 km leicht zügiger antesten. Verpflegung üben."),
     ("So",*KRAFT)]),

 wk("W10","Woche 10","Vorinfektniveau · Standortbestimmung (37–41 km)",
    [("Laufen","37–41 km"),("Rad","Pendeln"),("Intensität","1× Marathonbelastung"),("Longrun","21 km")],
    [("Mo · Büro",*RAD),
     ("Di · Büro","Rücklauf · 9 km",["run","z2"],"Locker. Wie steht der Ruhepuls im Wochenschnitt vs. Basis (53–55)?"),
     ("Mi",*REST),
     ("Do · Büro","Marathonbelastung · 10 km",["run","lt"],"30–40 Min bei ~145–151 bpm, kontrolliert. Nur wenn Puls und Gefühl stabil."),
     ("Fr · Büro",*RAD),
     ("Sa","Longrun · 21 km",["run","z2","longrun"],"Zurück auf Vorinfekt-Niveau. Fühlt sich das gut an → Marathon realistisch."),
     ("So","Bilanz + Kraft",["kraft","rest"],"STANDORTBESTIMMUNG: Antikörpertest + Körpergefühl + Werte. Marathon 25.10. weiter oder Ziel anpassen? Ehrlich entscheiden.")]),

 wk("W11","Woche 11","Entlastung · Deload (31–35 km)",
    [("Laufen","31–35 km"),("Rad","Pendeln"),("Intensität","nur locker"),("Longrun","16 km")],
    [("Mo · Büro",*RAD),
     ("Di · Büro","Rücklauf · 8 km",["run","z2"],"Locker, kurz. Diese Woche bewusst weniger."),
     ("Mi",*REST),
     ("Do · Büro","Rücklauf · 8 km",["run","z2"],"Locker. Körper adaptiert die Belastung der letzten Wochen."),
     ("Fr · Büro",*RAD),
     ("Sa","Longrun kurz · 16 km",["run","z2","longrun"],"Reduziert, ganz entspannt."),
     ("So",*REST)]),

 wk("W12","Woche 12","Marathonaufbau (40–44 km)",
    [("Laufen","40–44 km"),("Rad","Pendeln"),("Intensität","1× Marathonbelastung"),("Longrun","24 km")],
    [("Mo · Büro",*RAD),
     ("Di · Büro","Rücklauf · 10 km",["run","z2"],"Locker Grundlage."),
     ("Mi · Büro","Marathonbelastung · 8 km",["run","lt"],"2× 20 Min bei 145–151 bpm, dazwischen 5 Min locker."),
     ("Do",*REST),
     ("Fr · Büro",*RAD),
     ("Sa","Longrun · 24 km",["run","z2","longrun"],"Zone 2, Renn-Verpflegung strikt üben."),
     ("So",*KRAFT)]),

 wk("W13","Woche 13","Längster Belastungsblock (42–46 km)",
    [("Laufen","42–46 km"),("Rad","Pendeln"),("Intensität","1× Tempo/LT"),("Longrun","25 km")],
    [("Mo · Büro",*RAD),
     ("Di · Büro","Rücklauf · 11 km",["run","z2"],"Locker Grundlage."),
     ("Mi · Büro","Tempolauf · 10 km",["run","lt"],"3× 8 Min an der Schwelle (~170–172 bpm), 3 Min locker dazwischen."),
     ("Do",*REST),
     ("Fr · Büro",*RAD),
     ("Sa","Longrun · 25 km",["run","z2","longrun"],"Der längste Belastungsblock. Letzte 5 km im Marathon-Renntempo."),
     ("So",*KRAFT)]),

 wk("W14","Woche 14","Entlastung (34–38 km)",
    [("Laufen","34–38 km"),("Rad","Pendeln"),("Intensität","nur locker"),("Longrun","19 km")],
    [("Mo · Büro",*RAD),
     ("Di · Büro","Rücklauf · 9 km",["run","z2"],"Locker."),
     ("Mi · Büro","Rücklauf · 9 km",["run","z2"],"Locker. Erholung nach dem großen Block."),
     ("Do",*REST),
     ("Fr · Büro",*RAD),
     ("Sa","Longrun kurz · 19 km",["run","z2","longrun"],"Reduziert, entspannt."),
     ("So",*REST)]),

 wk("W15","Woche 15","Letzter Peak (44–48 km)",
    [("Laufen","44–48 km"),("Rad","Pendeln"),("Intensität","Renntempo"),("Longrun","28 km")],
    [("Mo · Büro",*RAD),
     ("Di · Büro","Rücklauf · 10 km",["run","z2"],"Locker Grundlage."),
     ("Mi · Büro","Marathon-Renntempo · 10 km",["run","lt"],"3× 3 km im Zieltempo (~7:00/km, ~150 bpm). Renngefühl kalibrieren."),
     ("Do",*REST),
     ("Fr · Büro",*RAD),
     ("Sa","Longrun-Peak · 28 km",["run","z2","longrun"],"Der wichtigste lange Lauf. Alles wie am Renntag, letzte 6 km Renntempo."),
     ("So",*REST)]),

 wk("W16","Woche 16","Taperbeginn (34–38 km)",
    [("Laufen","34–38 km"),("Rad","Pendeln"),("Intensität","kurzes Renntempo"),("Longrun","20 km")],
    [("Mo · Büro",*RAD),
     ("Di · Büro","Rücklauf · 9 km",["run","z2"],"Locker. Ab jetzt runterfahren, nicht mehr aufbauen."),
     ("Mi · Büro","Renntempo kurz · 8 km",["run","lt"],"2× 2 km Zieltempo, spritzig ohne zu ermüden."),
     ("Do",*REST),
     ("Fr · Büro",*RAD),
     ("Sa","Longrun reduziert · 20 km",["run","z2","longrun"],"Deutlich kürzer als Peak. Beine an Länge gewöhnt halten, erholen."),
     ("So",*REST)]),

 wk("W17","Woche 17","Deutliche Reduktion (23–28 km)",
    [("Laufen","23–28 km"),("Rad","optional"),("Intensität","kurz + Renntempo"),("Longrun","14 km")],
    [("Mo",*REST),
     ("Di · Büro","Rücklauf · 7 km",["run","z2"],"Locker, kurz."),
     ("Mi · Büro","Renntempo · 6 km",["run","lt"],"3× 1 km Zieltempo. Beine wach halten, nicht ermüden."),
     ("Do",*REST),
     ("Fr · Büro",*RAD),
     ("Sa","Longrun kurz · 14 km",["run","z2","longrun"],"Letzter etwas längerer Lauf. Entspannt."),
     ("So",*REST)]),

 wk("W18","Renn-Woche","Frisch bleiben · MARATHON",
    [("Laufen","10–14 km"),("Rad","–"),("Intensität","Wettkampf"),("Longrun","42,2 km")],
    [("Mo",*REST),
     ("Di","Locker · 6 km + Steigerungen",["run","z2"],"Kurz, 4× 20 s zügig. Beine spritzig halten."),
     ("Mi",*REST),
     ("Do","Locker · 4 km",["run","z2"],"Ganz kurz lockern. Danach nur noch Ruhe."),
     ("Fr","Ruhetag",["rest"],"Beine hoch. Carbo-Loading, viel trinken."),
     ("Sa","Ausschütteln · 3 km",["run","z2"],"15 Min locker + 2 Steigerungen. Ausrüstung bereitlegen."),
     ("So","MARATHON FRANKFURT",["run","lt"],"25.10. Renntag! Pacing: erste 10 km 140–145 bpm, dann 145–150, im letzten Drittel >150 nur wenn Atmung/Beine/Gefühl stabil. Verpflegung wie geübt. Genieß es.")]),
]

html = open("index.html", encoding="utf-8").read()
m = re.search(r"const weeks = (\[.*?\n\]\s*);", html, re.DOTALL)
weeks = json.loads(m.group(1))
weeks = weeks[:6] + weeks6_18
assert len(weeks) == 19, len(weeks)
new = "const weeks = " + json.dumps(weeks, ensure_ascii=False, indent=2) + ";"
html = html[:m.start()] + new + html[m.end():]
open("index.html", "w", encoding="utf-8").write(html)
print(f"Plan neu: {len(weeks)} Wochen. Umfaenge W7..W18:",
      [w['stats'][0]['v'] for w in weeks[7:]])
