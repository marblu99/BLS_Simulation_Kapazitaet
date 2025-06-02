import yaml
import json
import os
import sys

# YAML-Dateien laden
with open("1_infrastructure.yaml", "r") as f:
    infra_data = yaml.safe_load(f)

with open("2_vprofile.yaml", "r") as f:
    vprofile_data = yaml.safe_load(f)

route = infra_data["route"]
infrastructure = infra_data["infrastructure"]
v_segments = vprofile_data["v_profile"][0]["v_segment"]

# Gesamtlängen berechnen
infra_total = sum(
    infrastructure[elem]["length"]
    for elem in route
    if infrastructure.get(elem, {}).get("type") == "section"
)
vprofile_total = sum(v["length"] for v in v_segments)

# Prüfung am Anfang
print(f"📐 Infrastruktur (Summe aller Sections): {infra_total} m")
print(f"📊 v_profile.yaml (Summe aller Segmente): {vprofile_total} m")

if infra_total != vprofile_total:
    differenz = abs(infra_total - vprofile_total)
    print(f"❌ Fehler: Längen stimmen nicht überein! Differenz: {differenz} m")
    sys.exit(1)

# Position im v_profile + Restlänge
v_index = 0
used_in_current = 0

def get_speed_segments(target_length):
    global v_index, used_in_current
    segments = []
    to_cover = target_length

    while to_cover > 0:
        current_segment = v_segments[v_index]
        available = current_segment["length"] - used_in_current

        if available > to_cover:
            segments.append({
                "length": to_cover,
                "v_ziel": current_segment["v"]
            })
            used_in_current += to_cover
            to_cover = 0
        else:
            segments.append({
                "length": available,
                "v_ziel": current_segment["v"]
            })
            to_cover -= available
            v_index += 1
            used_in_current = 0

    return segments

# Alle Sections verarbeiten und in ein Dict schreiben
all_sections = {}
for element in route:
    info = infrastructure.get(element, {})
    if info.get("type") == "section":
        length = info["length"]
        abschnitte = get_speed_segments(length)
        all_sections[element] = abschnitte
        print(f"✔ Abschnitt {element}: {length} m → {len(abschnitte)} mit V-Abschnitte(n)")

# In eine einzige JSON-Datei schreiben
os.makedirs("json", exist_ok=True)  # <- NEU: Ordner anlegen, falls nicht vorhanden
output_path = "json/streckenabschnitte.json"
with open(output_path, "w") as f:
    json.dump(all_sections, f, indent=2)

print(f"\n📄 Eine Datei geschrieben: {output_path}")

# Gesamtlängen zur Kontrolle ausgeben
json_total = sum(
    sum(segment["length"] for segment in abschnitte)
    for abschnitte in all_sections.values()
)

print(f"📐 Infrastruktur (Summe aller Sections): {infra_total} m")
print(f"🗃️  JSON-Datei (Summe aller Teilstücke): {json_total} m")
print(f"📊 v_profile.yaml (Summe aller Segmente): {vprofile_total} m")
