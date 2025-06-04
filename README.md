# 🚆 Kapazitätsbasierte Bahnsimulation mit Visualisierung

Dieses Projekt simuliert eine realitätsnahe Bahnstrecke mit Zügen, Brems- und Fahrprofilen, 
Belegzeiten und einer umfassenden Visualisierung. Ziel ist es, die maximal nutzbare Kapazität 
eines Streckenabschnitts unter realen Bedingungen abzuschätzen.

## 🔧 Hauptfunktionen

- YAML-basierte Definition von Infrastruktur, Geschwindigkeitsprofilen und Fahrplänen
- Streckenprofil-Berechnung mit automatischer Segmentzuweisung
- Simulation realistischer Zugbewegungen inkl.:
  - Bremsen, Beschleunigen, Haltezeiten
  - Dynamische Reservierung von Blockabschnitten
  - Konfliktvermeidung bei Engstellen
- Automatische Erstellung von Fahrzeitprofilen mit `pandas` und `numpy`
- Visualisierung mit `pygame`:
  - Streckenabschnitts- und Bahnhofsnamen
  - Dynamisch fahrende Züge
  - Kapazitätsauslastung jedes Abschnitts
  - Verzögerungsprotokoll (inkl. Grund & Dauer)

## 🗂️ Projektstruktur

```bash
.
├── 1_Infrastruktur.yaml      # Strecke mit Stations-/Abschnittsdefinition
├── 2_Vprofil.yaml            # Geschwindigkeit entlang der Strecke
├── 3_Fahrplan.yaml           # Zugfahrpläne inkl. Rückfahrten
├── 4_Streckenabschnitte.py   # Mapping von Geschwindigkeit zu Strecke
├── 5_Fahrprofile.py          # Simulationscode für einzelne Streckenprofile
├── 5.1_Fahrprofile.py        # Visualisierung von Fahrprofilen (z. B. Geschwindigkeit über Zeit)
├── 6_Bremspunkte.py          # Breakpoint-Erkennung (z. B. Bremszeitpunkt)
├── 7_Simulation.py           # Hauptsimulation mit SimPy
├── 8_Visualisierung.py       # Echtzeit-Visualisierung mit pygame
├── requirements.txt          # Python-Abhängigkeiten
└── /csv/, /json/             # Outputs und Zwischenstände
