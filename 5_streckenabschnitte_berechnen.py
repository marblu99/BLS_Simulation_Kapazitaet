import os
import json
import numpy as np
import pandas as pd

# Einstellungen
beschleunigen = 0.9
bremsen = 0.9

def simuliere(streckenabschnitte, name_strecke, startgeschwindigkeit, bremsung_am_ende, beschleunigen, bremsen, dt=0.1, x_offset=0.0):
    ziel_strecke = sum(abschnitt["length"] for abschnitt in streckenabschnitte)
    abschnittsgrenzen = []
    cum_length = 0
    for abschnitt in streckenabschnitte:
        cum_length += abschnitt['length']
        abschnittsgrenzen.append((cum_length, abschnitt['v_ziel'] / 3.6))

    def get_v_ziel_at_position(x):
        for end, v in abschnittsgrenzen:
            if x <= end:
                return v
        return abschnittsgrenzen[-1][1]

    bremszonen = []
    position = ziel_strecke

    # Letzte Bremsung auf 0 m/s falls erforderlich
    if bremsung_am_ende:
        v_vorher = 0.0
        pos = ziel_strecke
        for i in reversed(range(len(streckenabschnitte))):
            v_vorher = streckenabschnitte[i]['v_ziel'] / 3.6
            s_brems = (v_vorher ** 2) / (2 * bremsen)
            pos -= streckenabschnitte[i]['length']
            if ziel_strecke - s_brems >= pos:
                bremszonen.append({
                    "start": ziel_strecke - s_brems,
                    "end": ziel_strecke,
                    "v_start": v_vorher,
                    "v_ziel": 0.0
                })
                break

    # Bremszonen bei Zielgeschwindigkeitssprüngen
    position = ziel_strecke
    for i in reversed(range(len(streckenabschnitte) - 1)):
        v_curr = streckenabschnitte[i]['v_ziel'] / 3.6
        v_next = streckenabschnitte[i + 1]['v_ziel'] / 3.6

        # "position" ist jetzt der Anfang des Abschnitts i+1
        position -= streckenabschnitte[i + 1]['length']

        if v_curr > v_next:
            s_brems = (v_curr**2 - v_next**2) / (2 * bremsen)
            start_brems = position - s_brems
            if start_brems >= 0:
                bremszonen.append({
                    "start": start_brems,
                    "end": position,
                    "v_start": v_curr,
                    "v_ziel": v_next
                })

    def get_bremszone_at_position(x, v):
        for z in bremszonen:
            if z["start"] <= x <= z["end"] and v > z["v_ziel"]:
                return z
        return None

    x, t = 0.0, 0.0
    v = startgeschwindigkeit
    v_alt = v

    positions = [x + x_offset]
    geschwindigkeit_ms = [v]
    geschwindigkeit_kmh = [v * 3.6]
    zeiten = [t]
    beschleunigungen = [0]

    while x <= ziel_strecke:
        v_ziel_raw = get_v_ziel_at_position(x)
        s_verfuegbar = ziel_strecke - x
        v_next = v_ziel_raw
        for grenze, v_abschnitt in abschnittsgrenzen:
            if grenze > x:
                s_verfuegbar = grenze - x
                v_next = v_abschnitt
                break

        v_erreichbar = np.sqrt(v**2 + 2 * beschleunigen * s_verfuegbar)
        v_ziel = min(v_erreichbar, v_next)

        zone = get_bremszone_at_position(x, v)
        if zone:
            s_rest = zone["end"] - x
            if s_rest > 0:
                v_target = np.sqrt(max(zone["v_ziel"]**2 + 2 * bremsen * s_rest, 0))
                if v <= v_target:
                    zone = None
                else:
                    v = max(v - bremsen * dt, v_target)
            else:
                v = max(v - bremsen * dt, zone["v_ziel"])

        if not zone:
            if v < v_ziel:
                v = min(v + beschleunigen * dt, v_ziel)
            elif v > v_ziel:
                v = max(v - bremsen * dt, v_ziel)

        a_ = (v - v_alt) / dt if t > 0 else 0
        positions.append(x + x_offset)
        geschwindigkeit_ms.append(v)
        geschwindigkeit_kmh.append(v * 3.6)
        zeiten.append(t)
        beschleunigungen.append(a_)
        v_alt = v
        x += v * dt
        t += dt

    if positions[-1] < ziel_strecke + x_offset:
        v_final = 0.0 if bremsung_am_ende else geschwindigkeit_ms[-1]
        positions.append(ziel_strecke + x_offset)
        geschwindigkeit_ms.append(v_final)
        geschwindigkeit_kmh.append(v_final * 3.6)
        t = round(t / dt) * dt
        zeiten.append(t)
        beschleunigungen.append((geschwindigkeit_ms[-1] - geschwindigkeit_ms[-2]) / dt)

    os.makedirs("csv", exist_ok=True)
    df = pd.DataFrame({
        "Zeit [s]": zeiten,
        "Position [m]": positions,
        "Geschwindigkeit [m/s]": geschwindigkeit_ms,
        "Beschleunigung [m/s²]": beschleunigungen
    })
    pfad = f"csv/{name_strecke}.csv"
    df.to_csv(pfad, index=False, float_format="%.1f")
    print(f"✅ Gespeichert: {pfad}")

def vorheriger_abschnitt_name(aktueller, daten):
    abschnitte = list(daten.keys())
    try:
        index = abschnitte.index(aktueller)
        if index > 0:
            return abschnitte[index - 1]
    except ValueError:
        pass
    return None

if __name__ == "__main__":
    with open("json/streckenabschnitte.json") as f:
        daten = json.load(f)

    cum_offset = 0.0
    for abschnitt, strecke in daten.items():
        v0_options = ["start0", "startV"]
        stop_options = [True, False]

        for start_typ in v0_options:
            for stop in stop_options:
                # Übersetze Starttyp
                start_code = "0" if start_typ == "start0" else "v"
                # Übersetze Stoptyp
                stop_code = "0" if stop else "v"
                # Neuer Name im Format: S1_0_to_v.csv
                name = f"{abschnitt}_{start_code}_to_{stop_code}"

                v0 = 0.0 if start_typ == "start0" else strecke[0]["v_ziel"] / 3.6

                if start_typ == "startV":
                    vorgaenger = vorheriger_abschnitt_name(abschnitt, daten)
                    if vorgaenger:
                        vorgaenger_path = f"csv/{vorgaenger}_0_to_v.csv"
                        if os.path.exists(vorgaenger_path):
                            df = pd.read_csv(vorgaenger_path)
                            letzte_v = df["Geschwindigkeit [m/s]"].iloc[-1]
                            ziel_v = strecke[0]["v_ziel"] / 3.6
                            if abs(letzte_v - ziel_v) > 0.1:
                                v0 = letzte_v

                simuliere(strecke, name, v0, stop, beschleunigen, bremsen, x_offset=cum_offset)

        # Korrigierte Berechnung der Offset-Distanz
        cum_offset += sum(abschnitt["length"] for abschnitt in strecke)
