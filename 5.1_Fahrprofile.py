import pandas as pd
import numpy as np
import yaml
import matplotlib.pyplot as plt
import os
from matplotlib.collections import LineCollection
from matplotlib.ticker import FuncFormatter

# === Eingaben ===
abschnitt = "S5"               # z. B. "S3"
start_v = False               # True = Start mit Geschwindigkeit > 0
halt_am_ende = True          # True = Zug hält am Ende

# Konstanten die nicht geändert werden sollen
yaml_pfad = "2_Vprofil.yaml" # Zielprofil (YAML)
csv_ordner = "csv"            # Ordner mit Simulationsdaten
a_toleranz = 0.01             # Schwelle zur Phasenerkennung

# === Dateinamen zusammensetzen ===
v_start = "v" if start_v else "0"
v_stop = "0" if halt_am_ende else "v"
csv_datei = f"{abschnitt}_{v_start}_to_{v_stop}.csv"
csv_pfad = os.path.join(csv_ordner, csv_datei)

if not os.path.exists(csv_pfad):
    raise FileNotFoundError(f"❌ Datei nicht gefunden: {csv_pfad}")

# === CSV laden ===
df = pd.read_csv(csv_pfad)

# === Zielprofil aus YAML laden ===
with open(yaml_pfad, "r") as f:
    yaml_data = yaml.safe_load(f)

geschwindigkeits_map = []
pos = 0
for profil in yaml_data["v_profile"]:
    for seg in profil["v_segment"]:
        start = pos
        end = pos + seg["length"]
        geschwindigkeits_map.append((start, end, seg["v"]))
        pos = end

# === Step-Profil vorbereiten (für Plot in km/h) ===
step_x, step_y = [], []
for start, end, v in geschwindigkeits_map:
    step_x.extend([start, end])
    step_y.extend([v, v])

# === Grenzen der Strecke aus CSV ===
start_x = df["Position [m]"].min()
end_x = df["Position [m]"].max()

# === Beschleunigungsphasen finden ===
phasen = []
start_idx = None
for i in range(1, len(df)):
    a_prev = df.loc[i - 1, "Beschleunigung [m/s²]"]
    a_curr = df.loc[i,     "Beschleunigung [m/s²]"]
    prev_in = abs(a_prev) >= a_toleranz
    curr_in = abs(a_curr) >= a_toleranz

    if not prev_in and curr_in:
        start_idx = i
    elif prev_in and not curr_in and start_idx is not None:
        t0, t1 = df.loc[start_idx, 'Zeit [s]'], df.loc[i - 1, 'Zeit [s]']
        v0, v1 = df.loc[start_idx, 'Geschwindigkeit [m/s]'], df.loc[i - 1, 'Geschwindigkeit [m/s]']
        xm = (df.loc[start_idx, 'Position [m]'] + df.loc[i - 1, 'Position [m]']) / 2
        a_eff = (v1 - v0) / (t1 - t0) if t1 != t0 else 0
        phasen.append((xm, a_eff))
        start_idx = None

# === Letzte Phase bis zum Ende (falls offen) ===
if start_idx is not None:
    t0 = df.loc[start_idx, "Zeit [s]"]
    t1 = df.loc[len(df) - 1, "Zeit [s]"]
    v0 = df.loc[start_idx, "Geschwindigkeit [m/s]"]
    v1 = df.loc[len(df) - 1, "Geschwindigkeit [m/s]"]
    xm = (df.loc[start_idx, 'Position [m]'] + df.loc[len(df) - 1, 'Position [m]']) / 2
    a_eff = (v1 - v0) / (t1 - t0) if t1 != t0 else 0
    phasen.append((xm, a_eff))

# === Plot vorbereiten ===
fig, ax = plt.subplots(figsize=(12, 6))

# --- Zielprofil (grau, gestrichelt) ---
ax.step(step_x, step_y, where="post", label="V-Profil (km/h)", linestyle="--", color="gray")

# --- Effektive Geschwindigkeit ---
x = df["Position [m]"].values
y = df["Geschwindigkeit [m/s]"].values * 3.6
a = df["Beschleunigung [m/s²]"].values

points = np.array([x, y]).T.reshape(-1, 1, 2)
segments = np.concatenate([points[:-1], points[1:]], axis=1)

farben = ["green" if ai > a_toleranz else "red" if ai < -a_toleranz else "gray" for ai in a[:-1]]
lc = LineCollection(segments, colors=farben, linewidths=2, label="v (km/h)")
ax.add_collection(lc)

# --- Phasen annotieren ---
for xm, a_eff in phasen:
    farbe = 'green' if a_eff > 0 else 'red'
    align = 'left' if a_eff > 0 else 'right'
    x_pos = xm + 50 if a_eff > 0 else xm - 50
    v_interp = np.interp(xm, x, y)
    ax.text(x_pos, v_interp, f"{a_eff:+.2f} m/s²", ha=align, va='center', color=farbe, fontsize=10)

# --- Achsen und Layout ---
ax.set_xlabel("Position [m]")
ax.set_ylabel("Geschwindigkeit [km/h]")
ax.set_title(f"Streckenabschnitt {abschnitt} (Start {v_start} to Stop {v_stop})", fontsize=16, fontweight='bold', pad=15)
ax.set_xlim(start_x, end_x)
ax.set_ylim(bottom=0)

def schweizer_format(x, pos): return f"{x:,.0f}".replace(",", "'")
ax.xaxis.set_major_formatter(FuncFormatter(schweizer_format))

# Abschnittsgrenzen markieren
x_min, x_max = ax.get_xlim()
x_range = x_max - x_min
ax.text(start_x - 0.02 * x_range, -4, f"{start_x:,.0f} m".replace(",", "'"), ha='center', va='center', fontsize=10)
ax.text(end_x + 0.02 * x_range, -4, f"{end_x:,.0f} m".replace(",", "'"), ha='center', va='center', fontsize=10)

# Legende und Zeit
ax.grid(True)
ax.legend()
gesamtzeit = df["Zeit [s]"].iloc[-1]
y_max = ax.get_ylim()[1]
ax.text(end_x, y_max + 5, f"Gesamtzeit: {gesamtzeit:.1f} s", ha='right', va='top', fontsize=12, color='black')

plt.tight_layout()
plt.subplots_adjust(top=0.88, left=0.08, right=0.92)
plt.show()