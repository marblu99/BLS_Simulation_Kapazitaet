import os
import json
import pandas as pd

# Einstellungen
csv_ordner = "csv"
output_ordner = "json"
os.makedirs(output_ordner, exist_ok=True)
sections = [f"S{i}" for i in range(1, 10)]
a_toleranz = 0.01
toleranz = 0.1  # für die Konsistenzprüfung

# Hilfsfunktionen
def finde_letzte_neg_beginn(df, a_tol):
    a = df["Beschleunigung [m/s²]"].values
    for i in range(len(a) - 2, 0, -1):
        if a[i] < -a_tol and a[i - 1] >= -a_tol:
            return df.loc[i, "Zeit [s]"]
    return None

def finde_erste_pos_ende(df, a_tol):
    a = df["Beschleunigung [m/s²]"].values
    for i in range(1, len(a)):
        if a[i-1] > a_tol and a[i] <= a_tol:
            return df.loc[i, "Zeit [s]"]
    return None

def vergleiche_zeiten(name, v1, v2, tol=0.1):
    abweichung = abs(v1 - v2)
    if abweichung > tol:
        print(f"{name}: {v1:.2f} vs. {v2:.2f} → Δ={abweichung:.2f} ❌ NICHT GLEICH")

# Ergebnisstruktur
daten = {}

# Verarbeitung pro Abschnitt
for section in sections:
    try:
        df_0_0 = pd.read_csv(os.path.join(csv_ordner, f"{section}_0_to_0.csv"))
        df_0_v = pd.read_csv(os.path.join(csv_ordner, f"{section}_0_to_v.csv"))
        df_v_0 = pd.read_csv(os.path.join(csv_ordner, f"{section}_v_to_0.csv"))
        df_v_v = pd.read_csv(os.path.join(csv_ordner, f"{section}_v_to_v.csv"))

        T_0_0 = df_0_0["Zeit [s]"].iloc[-1]
        T_0_v = df_0_v["Zeit [s]"].iloc[-1]
        T_v_0 = df_v_0["Zeit [s]"].iloc[-1]
        T_v_v = df_v_v["Zeit [s]"].iloc[-1]

        # FORWARD
        t_break_0_fwd = finde_letzte_neg_beginn(df_0_0, a_toleranz)
        t_break_V_fwd = finde_letzte_neg_beginn(df_v_0, a_toleranz)
        remaining_0_fwd = T_0_0 - t_break_0_fwd if t_break_0_fwd is not None else None
        delta_0v = T_0_0 - T_0_v
        remaining_V_fwd = max(0.0, remaining_0_fwd - delta_0v) if remaining_0_fwd is not None else None

        # BACKWARD
        t_acc_end = finde_erste_pos_ende(df_0_0, a_toleranz)
        t_break_0_bwd = T_0_0 - t_acc_end if t_acc_end is not None else None
        remaining_0_bwd = t_acc_end
        delta_v0 = T_0_0 - T_v_0
        remaining_V_bwd = max(0.0, remaining_0_bwd - delta_v0) if remaining_0_bwd is not None else None
        t_break_V_bwd = T_0_v - remaining_0_bwd if remaining_0_bwd is not None else None

        # JSON speichern
        daten[section] = {
            "forward": {
                "time_at_breakpoint_start0": round(t_break_0_fwd, 2),
                "time_at_breakpoint_startV": round(t_break_V_fwd, 2),
                "remaining_time_stop0": round(remaining_0_fwd, 2),
                "remaining_time_stopV": round(remaining_V_fwd, 2)
            },
            "backward": {
                "time_at_breakpoint_start0": round(t_break_0_bwd, 2),
                "time_at_breakpoint_startV": round(t_break_V_bwd, 2),
                "remaining_time_stop0": round(remaining_0_bwd, 2),
                "remaining_time_stopV": round(remaining_V_bwd, 2)
            }
        }

        # Konsistenzprüfung
        f = daten[section]["forward"]
        b = daten[section]["backward"]

        f_start0 = f["time_at_breakpoint_start0"] + f["remaining_time_stop0"]
        b_start0 = b["time_at_breakpoint_start0"] + b["remaining_time_stop0"]
        vergleiche_zeiten(f"{section} start0 → stop0", f_start0, b_start0, toleranz)

        f_startV = f["time_at_breakpoint_startV"] + f["remaining_time_stopV"]
        b_startV = b["time_at_breakpoint_startV"] + b["remaining_time_stopV"]
        vergleiche_zeiten(f"{section} startV → stopV", f_startV, b_startV, toleranz)

    except FileNotFoundError as e:
        print(f"⚠️ Datei fehlt für {section}: {e}")
    except Exception as e:
        print(f"❌ Fehler bei {section}: {e}")

# Speichern der JSON-Datei
output_path = os.path.join(output_ordner, "breaktimes.json")
with open(output_path, "w") as f:
    json.dump(daten, f, indent=2)

print(f"\n✅ JSON erstellt: {output_path}")