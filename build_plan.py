#!/usr/bin/env python3
"""Recalibriert W9..W18 (Wieder-Aufbau nach 2. Infekt, Stand 18.08.) und spleisst
sie in index.html. Weeks 0..8 (Reha..W8, Historie) bleiben unberuehrt.
Marathon 25.10. Longrun 13->30 km, Peak 3 Wochen vorher, dann Taper.
Puls: locker 140-150 | Marathonbelastung 145-151 | LT ~172."""
import re, json

DAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

def wk(label, name, focus, stats, days):
    out = {"label": label, "name": name, "focus": focus,
           "stats": [{"l": l, "v": v} for l, v in stats], "days": []}
    for i, (dn, title, badges, desc) in enumerate(days):
        d = {"id": f"{label.lower()}{DAYS[i].lower()}", "name": dn,
             "title": title, "badges": badges, "desc": desc}
        if "longrun" in badges:
            d["badges"] = [b for b in badges if b != "longrun"]; d["longrun"] = True
        out["days"].append(d)
    return out

RAD=("Rad-Pendeln locker",["bike","z2"],"Locker pendeln, Puls <130 – Erholung, kein Reiz.")
KRAFT=("Kraft · Hamstring",["kraft","rest"],"Nordic Curls, RDL, Rumpf. Kein Lauf.")
REST=("Ruhetag",["rest"],"Pause. Erholung ist Teil des Aufbaus.")

weeks9_18=[
 wk("W9","Woche 9","Wieder-Aufbau · locker (26 km)",
    [("Laufen","~26 km"),("Rad","Pendeln"),("Intensität","nur locker"),("Longrun","13 km")],
    [("Mo · Büro",*RAD),
     ("Di · Büro","Rücklauf · 8 km",["run","z2"],"Locker, Puls ≤150. Nach dem Infekt bewusst ruhig."),
     ("Mi",*REST),
     ("Do · Büro","Rücklauf · 8 km",["run","z2"],"Locker nach Gefühl. Bei Resthusten kürzer."),
     ("Fr · Büro",*RAD),
     ("Sa","Longrun · 13 km",["run","z2","longrun"],"Wieder in den Longrun-Rhythmus. Zone 2, 8:00+/km, Elektrolyte."),
     ("So",*KRAFT)]),
 wk("W10","Woche 10","Aufbau (30 km)",
    [("Laufen","~30 km"),("Rad","Pendeln"),("Intensität","locker"),("Longrun","16 km")],
    [("Mo · Büro",*RAD),
     ("Di · Büro","Rücklauf · 9 km",["run","z2"],"Locker. Antikörper-Bluttest Ende August nicht vergessen."),
     ("Mi",*REST),
     ("Do · Büro","Rücklauf · 9 km",["run","z2"],"Ruhig, Frequenz Richtung 165."),
     ("Fr · Büro",*RAD),
     ("Sa","Longrun · 16 km",["run","z2","longrun"],"Zone 2, Gel ab km 10."),
     ("So",*KRAFT)]),
 wk("W11","Woche 11","Aufbau · 1× moderat (34 km)",
    [("Laufen","~34 km"),("Rad","Pendeln"),("Intensität","1× moderat"),("Longrun","18 km")],
    [("Mo · Büro",*RAD),
     ("Di · Büro","Rücklauf · 9 km",["run","z2"],"Locker Grundlage."),
     ("Mi",*REST),
     ("Do · Büro","Zügiger Reiz · 9 km",["run","z2"],"Nur wenn unauffällig: 20 Min bei 145–150 bpm, Rest locker."),
     ("Fr · Büro",*RAD),
     ("Sa","Longrun · 18 km",["run","z2","longrun"],"Zone 2, letzte 3 km leicht zügiger."),
     ("So",*KRAFT)]),
 wk("W12","Woche 12","Marathonaufbau (38 km)",
    [("Laufen","~38 km"),("Rad","Pendeln"),("Intensität","Marathonbelastung"),("Longrun","21 km")],
    [("Mo · Büro",*RAD),
     ("Di · Büro","Rücklauf · 10 km",["run","z2"],"Locker."),
     ("Mi · Büro","Marathonbelastung · 8 km",["run","lt"],"2× 20 Min bei 145–151 bpm, 5 Min locker dazwischen."),
     ("Do",*REST),
     ("Fr · Büro",*RAD),
     ("Sa","Longrun · 21 km",["run","z2","longrun"],"Renn-Verpflegung üben. Zone 2."),
     ("So",*KRAFT)]),
 wk("W13","Woche 13","Aufbau · Tempo (42 km)",
    [("Laufen","~42 km"),("Rad","Pendeln"),("Intensität","Tempo/LT"),("Longrun","24 km")],
    [("Mo · Büro",*RAD),
     ("Di · Büro","Rücklauf · 11 km",["run","z2"],"Locker Grundlage."),
     ("Mi · Büro","Tempolauf · 10 km",["run","lt"],"3× 8 Min Schwelle (~170 bpm), 3 Min locker."),
     ("Do",*REST),
     ("Fr · Büro",*RAD),
     ("Sa","Longrun · 24 km",["run","z2","longrun"],"Letzte 5 km Marathon-Renntempo."),
     ("So",*KRAFT)]),
 wk("W14","Woche 14","Longrun-Aufbau (44 km)",
    [("Laufen","~44 km"),("Rad","Pendeln"),("Intensität","Tempo/LT"),("Longrun","27 km")],
    [("Mo · Büro",*RAD),
     ("Di · Büro","Rücklauf · 11 km",["run","z2"],"Locker."),
     ("Mi · Büro","Tempolauf · 10 km",["run","lt"],"3–4× 8 Min Schwelle (~172 bpm)."),
     ("Do",*REST),
     ("Fr · Büro",*RAD),
     ("Sa","Longrun · 27 km",["run","z2","longrun"],"Renn-Verpflegung komplett durchspielen."),
     ("So",*REST)]),
 wk("W15","Woche 15","Letzter Peak (46 km)",
    [("Laufen","~46 km"),("Rad","Pendeln"),("Intensität","Renntempo"),("Longrun","30 km")],
    [("Mo · Büro",*RAD),
     ("Di · Büro","Rücklauf · 10 km",["run","z2"],"Locker."),
     ("Mi · Büro","Marathon-Renntempo · 10 km",["run","lt"],"3× 3 km Zieltempo (~7:00/km, ~150 bpm)."),
     ("Do",*REST),
     ("Fr · Büro",*RAD),
     ("Sa","Longrun-Peak · 30 km",["run","z2","longrun"],"Der wichtigste lange Lauf. Alles wie am Renntag, letzte 6 km Renntempo."),
     ("So",*REST)]),
 wk("W16","Woche 16","Taperbeginn (34 km)",
    [("Laufen","~34 km"),("Rad","Pendeln"),("Intensität","kurzes Renntempo"),("Longrun","20 km")],
    [("Mo · Büro",*RAD),
     ("Di · Büro","Rücklauf · 9 km",["run","z2"],"Locker. Ab jetzt runterfahren."),
     ("Mi · Büro","Renntempo kurz · 8 km",["run","lt"],"2× 2 km Zieltempo, spritzig."),
     ("Do",*REST),
     ("Fr · Büro",*RAD),
     ("Sa","Longrun reduziert · 20 km",["run","z2","longrun"],"Deutlich kürzer als Peak, entspannt."),
     ("So",*REST)]),
 wk("W17","Woche 17","Taper (24 km)",
    [("Laufen","~24 km"),("Rad","optional"),("Intensität","kurz + Renntempo"),("Longrun","14 km")],
    [("Mo",*REST),
     ("Di · Büro","Rücklauf · 7 km",["run","z2"],"Locker, kurz."),
     ("Mi · Büro","Renntempo · 6 km",["run","lt"],"3× 1 km Zieltempo. Beine wach halten."),
     ("Do",*REST),
     ("Fr · Büro",*RAD),
     ("Sa","Longrun kurz · 14 km",["run","z2","longrun"],"Letzter etwas längerer Lauf, entspannt."),
     ("So",*REST)]),
 wk("W18","Renn-Woche","Frisch bleiben · MARATHON",
    [("Laufen","10–14 km"),("Rad","–"),("Intensität","Wettkampf"),("Longrun","42,2 km")],
    [("Mo",*REST),
     ("Di","Locker · 6 km + Steigerungen",["run","z2"],"Kurz, 4× 20 s zügig."),
     ("Mi",*REST),
     ("Do","Locker · 4 km",["run","z2"],"Ganz kurz lockern."),
     ("Fr","Ruhetag",["rest"],"Beine hoch, Carbo-Loading, viel trinken."),
     ("Sa","Ausschütteln · 3 km",["run","z2"],"15 Min locker + 2 Steigerungen. Ausrüstung bereitlegen."),
     ("So","MARATHON FRANKFURT",["run","lt"],"25.10.! Pacing: erste 10 km 140–145 bpm, dann 145–150, letztes Drittel >150 nur wenn stabil. Verpflegung wie geübt. Nach allem, was hinter dir liegt – genieß es.")]),
]

html=open("index.html",encoding="utf-8").read()
m=re.search(r"const weeks = (\[.*?\n\]\s*);",html,re.DOTALL)
weeks=json.loads(m.group(1))
weeks=weeks[:9]+weeks9_18
assert len(weeks)==19,len(weeks)
html=html[:m.start()]+"const weeks = "+json.dumps(weeks,ensure_ascii=False,indent=2)+";"+html[m.end():]
open("index.html","w",encoding="utf-8").write(html)
print("Plan recalibriert. Longruns W9..W18:",[w["stats"][3]["v"] for w in weeks[9:]])
