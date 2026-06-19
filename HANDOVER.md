# Marathon-Trainingsplan – Übergabe

**Ziel:** Frankfurt Marathon 25.10.2026, ~5h Zielzeit, verletzungsfrei. Primär: Übertraining vermeiden.

## Sportlerprofil
- LT2: 174 bpm / 5:33 pace / 391 W. HFmax >200. Natürlicher Laufpuls ~150 bpm bei 7:00–7:30/km
- Garmin-Zonen LT2-basiert kalibriert. Zone-2-Obergrenze ~143 bpm
- Radfahren = Erholung (Pendeln ~130 W / <130 bpm). Laufpendeln = echtes Training
- Aktivität: 2–3× Rad, 2–3× Laufen, 1× Kraft/Woche. 4 Bürotage, Pendeln per Rad (15 km) oder Lauf (10–15 km)
- Gewicht 92 kg → Ziel 87 kg. Yazio-Tracking. Protein-Ziel 155 g/Tag, Defizit nicht zu aggressiv

## Trainingsprinzipien
- 80/20: Großteil locker, wenig hart
- Longruns strikt Zone 2, 8:00+/km starten, Puls möglichst <=150
- Nie zwei Lauftage in Folge
- Mittwoch Pflichtpause
- Tempolauf ist optional und wird bei Belastung zuerst gestrichen
- Plananpassung nach Schlaf, HFV, Wohlbefinden (Check-in im Plan)

## Planstruktur
- Periodisiert mit 3:1-Rhythmus (3 Wochen Aufbau, 1 Woche Entlastung)
- Longrun-Peak 2x 32 km (W11 und W14)
- Taper ueber die letzten ~3 Wochen
- Aktuelle Woche (Mitte Juni 2026) = Infekt-Wiedereinstieg, kein hartes Training

## Status (16.6.2026)
Beginnender Infekt - mehrere Tage Halskratzen, jetzt Brustenge nach 7-km-Lauf. Training pausiert bis Brust frei und Schlaf erholt. Brustenge nach Belastung ist ein Stopp-Signal. Bei anhaltender Brustenge oder Fieber aerztlich abklaeren (Myokarditis-Risiko bei Belastung mit Infekt).

## Setup / Deployment
- index.html ist die komplette App (dunkles Theme, Wochen-Tabs, Tages-Check-in mit Anpassungs-Banner, Status-Tracking via localStorage).
- Bei Planaenderungen: index.html bearbeiten, committen, pushen -> Netlify deployt automatisch.
- Netlify-Alternative ohne GitHub: Ordner per Drag&Drop auf netlify.com/drop ziehen.
