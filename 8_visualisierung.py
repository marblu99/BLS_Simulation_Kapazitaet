import pygame
import yaml
import os
import sys
import json
import time as time_module
import random
from collections import defaultdict

class InfrastructureVisualizer:
    def __init__(self, infra_path="1_Infrastruktur.yaml", sim_log_path="json/simulation_log.json"):
        pygame.init()

        self.element_occupancy_times = defaultdict(float)
        self.total_simulation_time = 0
        self.total_track_length = 0

        self.completed_trains = {"SO->BDF": 0, "BDF->SO": 0}
        self.trains_seen_at_destination = set()
        self.train_start_locations = {}  # Speichert, wo ein Zug gestartet ist
        
        # Verzögerungsprotokoll - ohne Scroll-Variablen
        self.delay_log = []
        self.train_delays = {}
        self.wait_start_times = {}
        
        self.width = 1500
        self.height = 650

        # Farben
        self.BLACK = (0, 0, 0)
        self.WHITE = (255, 255, 255)
        self.GRAY = (200, 200, 200)
        self.DARK_GRAY = (100, 100, 100)
        self.LIGHT_GRAY = (230, 230, 230)
        
        # Vordefinierte Farben für Züge
        self.RED = (255, 0, 0)
        self.BLUE = (0, 0, 255)
        self.GREEN = (0, 180, 0)
        self.ORANGE = (255, 165, 0)
        self.PURPLE = (128, 0, 128)
        self.PINK = (255, 105, 180)
        self.CYAN = (0, 255, 255)
        self.MAGENTA = (255, 0, 255)
        self.YELLOW = (255, 255, 0)
        self.BROWN = (165, 42, 42)
        
        # Anfängliche leere Farbtabelle
        self.train_colors = {}

        self.simulation_time = 0
        self.simulation_running = False
        self.simulation_data = []
        self.speed_factor = 1

        self.train_segments = {}

        self.infra_path = infra_path
        self.sim_log_path = sim_log_path
        self.route = []
        self.infrastructure = {}
        self.stations = []
        self.sections = []
        self.section_lengths = {}
        self.positions = {}

        # Definiere die Größe des Hauptbereichs für die Strecke
        self.main_area_width = self.width - 250  # 300px für das Verzögerungsprotokoll reservieren
        
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Infrastruktur Visualisierung mit Simulation")

        self.font_small = pygame.font.SysFont("Arial", 12)
        self.font_medium = pygame.font.SysFont("Arial", 14, bold=True)
        self.font_large = pygame.font.SysFont("Arial", 24, bold=True)

        # Rechtseitiges Verzögerungsprotokoll
        self.delay_log_rect = pygame.Rect(self.main_area_width, 0, 250, self.height)
        self.delay_log_title = "Verzögerungsprotokoll"
        
        # Button-Positionen und -Größen
        button_y = self.height - 60  # Unten mit Abstand
        button_width = 150
        button_height = 40
        button_spacing = 10
        speed_button_width = 80

        # Play/Pause Button
        self.play_button_rect = pygame.Rect(20, button_y, button_width, button_height)
        
        # Restart Button
        self.restart_button_rect = pygame.Rect(20 + button_width + button_spacing, button_y, button_width, button_height)
        
        # Speed Buttons mit neuen Werten
        self.speed_buttons = []
        speed_factors = [1, 10, 60, 120]
        
        for i, factor in enumerate(speed_factors):
            x_pos = 20 + 2 * (button_width + button_spacing) + i * (speed_button_width + button_spacing)
            button_rect = pygame.Rect(x_pos, button_y, speed_button_width, button_height)
            self.speed_buttons.append((button_rect, factor))

        self.success = self._load_infrastructure()
        if self.success:
            self._calculate_positions()
            self._load_simulation_data()
            self._create_train_segments()
            self._calculate_element_occupancy()
            self._calculate_total_track_length()
            self._preprocess_delay_data()  # Methode zur Vorberechnung von Verzögerungen
    
    



    def _preprocess_delay_data(self):
        """Berechnet vorab alle Verzögerungen aus den Simulationsdaten"""
        print("Vorberechnung der Verzögerungsdaten...")
        
        # Temporäre Speicherung der aktuellen Wartezeiten
        waiting_trains = {}
        
        # Analysiere chronologisch alle Simulationsdaten
        for time_data in sorted(self.simulation_data, key=lambda x: x["time"]):
            sim_time = time_data["time"]
            
            # Für jeden Zug prüfen, ob er auf freie Kapazität wartet oder weiterfährt
            for train_id, train_data in time_data["trains"].items():
                station = train_data["element"]
                breaktime_info = train_data.get("breaktime_info", "")
                train_status = train_data.get("status", "")
                
                # Prüfe, ob der Zug auf freie Kapazität wartet
                if "Wartet auf freie Kapazitaet" in breaktime_info:
                    # Wenn dieser Zug noch nicht als wartend registriert ist, beginnt hier die Wartezeit
                    if train_id not in waiting_trains or waiting_trains[train_id]["station"] != station:
                        waiting_trains[train_id] = {
                            "station": station,
                            "start_time": sim_time,
                            "last_element": station  # Speichere das letzte bekannte Element
                        }
                        print(f"Vorberechnung: Zug {train_id} beginnt, an Station {station} zu warten bei {sim_time:.1f}s")
                else:
                    # Wenn der Zug zuvor gewartet hat und jetzt nicht mehr wartet
                    # Entweder weil breaktime_info geändert wurde ODER weil der Status "in Fahrt" ist
                    if train_id in waiting_trains and (
                    waiting_trains[train_id]["station"] == station or 
                    (train_status == "in Fahrt" and waiting_trains[train_id]["last_element"] == station)):
                        
                        # Berechne die gesamte Wartezeit
                        wait_duration = sim_time - waiting_trains[train_id]["start_time"]
                        
                        # Speichere nur Verzögerungen über einer Mindestschwelle (z.B. 0.5 Sekunden)
                        if wait_duration > 0.5:
                            self.delay_log.append({
                                "train_id": train_id,
                                "station": station,
                                "start_time": waiting_trains[train_id]["start_time"],
                                "end_time": sim_time,
                                "wait_duration": wait_duration
                            })
                            print(f"Vorberechnung: Zug {train_id} hat das Warten an Station {station} nach {wait_duration:.1f}s beendet")
                            print(f"  Status: {train_status}, Breaktime_info: {breaktime_info}")
                        
                        # Entferne Zug aus der Liste der wartenden Züge
                        del waiting_trains[train_id]
                    elif train_id in waiting_trains:
                        # Aktualisiere das letzte bekannte Element für den Fall, dass der Zug weiterfährt
                        waiting_trains[train_id]["last_element"] = station
        
        # Sortiere die Verzögerungen nach Startzeit
        self.delay_log = sorted(self.delay_log, key=lambda x: x["start_time"])
        print(f"Vorberechnung abgeschlossen. {len(self.delay_log)} Verzögerungen gefunden.")

    def _calculate_total_track_length(self):
        """Berechnet die Gesamtlänge aller Streckenabschnitte"""
        self.total_track_length = sum(self.section_lengths.values())
        print(f"Gesamtlänge der Strecke: {self.total_track_length} m")

    def _assign_train_colors(self):
        """Weist jedem Zug in den Simulationsdaten eine eindeutige Farbe zu."""
        # Sammle alle vorhandenen Zug-IDs
        train_ids = set()
        for time_data in self.simulation_data:
            for train_id in time_data.get("trains", {}).keys():
                train_ids.add(train_id)
        
        # Liste der vordefinierten Farben
        colors = [
            self.RED, self.BLUE, self.GREEN, self.ORANGE, self.PURPLE,
            self.PINK, self.CYAN, self.MAGENTA, self.YELLOW, self.BROWN
        ]
        
        # Wenn mehr Züge als vordefinierte Farben, generiere weitere Farben
        if len(train_ids) > len(colors):
            # Generiere zusätzliche zufällige Farben
            for _ in range(len(train_ids) - len(colors)):
                r = random.randint(50, 200)
                g = random.randint(50, 200)
                b = random.randint(50, 200)
                colors.append((r, g, b))
        
        # Weise jedem Zug eine Farbe zu
        for i, train_id in enumerate(sorted(train_ids)):
            self.train_colors[train_id] = colors[i % len(colors)]
        
        print(f"Farben zugewiesen für {len(train_ids)} Züge")

    def _calculate_element_occupancy(self):
        """Berechnet die Belegungszeit jedes Elements während der gesamten Simulation."""
        # Berechne die Gesamtzeit der Simulation
        if self.simulation_data:
            self.total_simulation_time = self.simulation_data[-1]["time"]
        else:
            self.total_simulation_time = 0
            
        # Berechne die Belegungszeiten pro Element
        for time_index in range(len(self.simulation_data) - 1):
            current_time_data = self.simulation_data[time_index]
            next_time_data = self.simulation_data[time_index + 1]
            
            # Zeitdifferenz zwischen den Datenpunkten
            time_diff = next_time_data["time"] - current_time_data["time"]
            
            # Für jedes reservierte Element die Belegungszeit erhöhen
            for train_info in current_time_data.get("trains", {}).values():
                for element in train_info.get("reserved", []):
                    self.element_occupancy_times[element] += time_diff
        
        print("Belegungszeiten für Elemente berechnet:")
        for element, occ_time in sorted(self.element_occupancy_times.items()):
            # Kapazität berücksichtigen
            capacity = 1
            if element in self.infrastructure:
                capacity = self.infrastructure[element].get("normal_capacity", 1)
            
            # Prozentuale Belegung unter Berücksichtigung der Kapazität
            occ_percent = (occ_time / self.total_simulation_time * 100) / capacity
            print(f"  {element}: {occ_time:.1f}s ({occ_percent:.1f}% bei Kapazität {capacity})")

    def _load_infrastructure(self):
        try:
            with open(self.infra_path, 'r') as f:
                infra_data = yaml.safe_load(f)

            self.route = infra_data.get("route", [])
            self.infrastructure = infra_data.get("infrastructure", {})
            self.stations = [item for item in self.route if not item.startswith('S') or item == "SO"]
            self.sections = [item for item in self.route if item.startswith('S') and item != "SO"]

            for section in self.sections:
                if section in self.infrastructure:
                    self.section_lengths[section] = self.infrastructure[section].get("length", 1000)

            print(f"Infrastruktur geladen: {len(self.stations)} Stationen, {len(self.sections)} Abschnitte")
            return True
        except Exception as e:
            print(f"Fehler beim Laden der Infrastruktur: {e}")
            return False

    def _calculate_positions(self):
        margin = 50
        track_y = self.height // 2
        total_length = sum(self.section_lengths.values())
        # Benutze main_area_width statt width für die Positionsberechnung
        usable_width = self.main_area_width - 2 * margin
        current_x = margin

        for element in self.route:
            if element in self.sections:
                length = self.section_lengths.get(element, 1000)
                width = (length / total_length) * usable_width
                self.positions[element] = {
                    'start': current_x,
                    'middle': current_x + width / 2,
                    'end': current_x + width,
                    'width': width,
                    'y': track_y
                }
                current_x += width
            elif element in self.stations:
                self.positions[element] = {
                    'x': current_x,
                    'y': track_y
                }

    def _load_simulation_data(self):
        try:
            with open(self.sim_log_path, 'r') as f:
                self.simulation_data = json.load(f)
                # Speichere Startstation jedes Zuges
                for time_data in self.simulation_data:
                    for train_id, train_info in time_data.get("trains", {}).items():
                        if train_id not in self.train_start_locations:
                            self.train_start_locations[train_id] = train_info.get("element")

            print(f"Simulationsdaten geladen: {len(self.simulation_data)} Zeitpunkte")
            
            # Weise jedem Zug eine Farbe zu
            self._assign_train_colors()
            
            return True
        except Exception as e:
            print(f"Fehler beim Laden der Simulationsdaten: {e}")
            return False

    def _create_train_segments(self):
        train_timeline = {}
        for time_data in self.simulation_data:
            time = time_data["time"]
            for train_id, train_data in time_data["trains"].items():
                train_timeline.setdefault(train_id, []).append({
                    "time": time,
                    "element": train_data["element"],
                    "status": train_data["status"],
                    "direction": train_data["direction"]
                })

        for train_id, timeline in train_timeline.items():
            timeline.sort(key=lambda x: x["time"])
            self.train_segments[train_id] = []
            station_changes = [i for i, pt in enumerate(timeline) if pt["element"] in self.stations]
            for i in range(len(station_changes) - 1):
                start = timeline[station_changes[i]]
                end = timeline[station_changes[i + 1]]
                y_offset = 17 if start["direction"] == "forward" else -17
                track_y = self.height // 2
                start_x = self.positions[start["element"]]["x"]
                end_x = self.positions[end["element"]]["x"]
                self.train_segments[train_id].append({
                    "start_time": start["time"],
                    "end_time": end["time"],
                    "start_x": start_x,
                    "start_y": track_y + y_offset,
                    "end_x": end_x,
                    "end_y": track_y + y_offset,
                    "status": "in Fahrt",
                    "start_station": start["element"],
                    "end_station": end["element"]
                })

    def get_current_reservations(self, sim_time):
        reservations = defaultdict(list)
        # Finde den Eintrag mit genau diesem Zeitpunkt oder den nächstgelegenen
        closest_time_data = None
        closest_time_diff = float('inf')
        
        for time_data in self.simulation_data:
            time_diff = abs(time_data["time"] - sim_time)
            if time_diff < closest_time_diff:
                closest_time_diff = time_diff
                closest_time_data = time_data
        
        if closest_time_data:
            for train_id, train_info in closest_time_data["trains"].items():
                for element in train_info.get("reserved", []):
                    reservations[element].append(train_id)
                    
        return reservations
    
    def get_active_trains_at_time(self, sim_time):
        """Gibt eine Liste der aktiven Züge zu einem bestimmten Zeitpunkt zurück"""
        active_trains = set()
        
        # Finde den Eintrag mit genau diesem Zeitpunkt oder den nächstgelegenen
        closest_time_data = None
        closest_time_diff = float('inf')
        
        for time_data in self.simulation_data:
            time_diff = abs(time_data["time"] - sim_time)
            if time_diff < closest_time_diff:
                closest_time_diff = time_diff
                closest_time_data = time_data
        
        if closest_time_data:
            active_trains = set(closest_time_data["trains"].keys())
                    
        return active_trains
    
    def check_for_current_delays(self, sim_time):
        """Identifiziert aktuell wartende Züge zum angegebenen Zeitpunkt"""
        current_delays = []
        
        for delay in self.delay_log:
            start_time = delay["start_time"]
            end_time = delay.get("end_time", float('inf'))  # Falls kein Ende definiert
            
            # Wenn die Verzögerung zum aktuellen Zeitpunkt aktiv ist
            if start_time <= sim_time <= end_time:
                # Berechne die aktuelle Dauer der Verzögerung
                current_duration = sim_time - start_time
                current_delay = delay.copy()
                current_delay["current_duration"] = current_duration
                current_delays.append(current_delay)
        
        # Sortiere nach aktueller Wartezeit (längste zuerst)
        return sorted(current_delays, key=lambda x: x["current_duration"], reverse=True)

    def draw_capacity_circles(self, x, y, capacity, reservations=None, element=None, circle_radius=8, circle_spacing=20):
        reserved_by = reservations.get(element, []) if reservations else []
        reserved_by = sorted(reserved_by)[:capacity]  # Sortiere z. B. Z1, Z2, ...

        for i in range(capacity):
            circle_y = y - i * circle_spacing
            if i < len(reserved_by):
                train_id = reserved_by[i]
                color = self.train_colors.get(train_id, self.PURPLE)
                pygame.draw.circle(self.screen, color, (int(x), int(circle_y)), circle_radius)
            pygame.draw.circle(self.screen, self.BLACK, (int(x), int(circle_y)), circle_radius, 1)

    def draw_delay_log(self):
        """Zeichnet das Verzögerungsprotokoll in einem schmalen Bereich rechts"""
        # Hintergrund für Verzögerungsprotokoll
        pygame.draw.rect(self.screen, self.LIGHT_GRAY, self.delay_log_rect)
        pygame.draw.rect(self.screen, self.DARK_GRAY, self.delay_log_rect, 1)  # Rahmen
        
        # Titel des Verzögerungsprotokolls
        title_text = self.font_medium.render(self.delay_log_title, True, self.BLACK)
        title_rect = title_text.get_rect(center=(self.delay_log_rect.centerx, 20))
        self.screen.blit(title_text, title_rect)
        
        # Aktuelle Verzögerungen markieren
        current_delays = self.check_for_current_delays(self.simulation_time)
        
        # Gesamtzahl der Verzögerungen anzeigen
        total_count_text = self.font_small.render(f"Gesamt: {len(self.delay_log)} | Aktuell: {len(current_delays)}", 
                                        True, self.BLACK)
        total_count_rect = total_count_text.get_rect(center=(self.delay_log_rect.centerx, 40))
        self.screen.blit(total_count_text, total_count_rect)
        
        # Einträge des Verzögerungsprotokolls anzeigen - vereinfacht
        line_height = 20
        start_y = 60  # Beginn der Listeneinträge
        
        # Sortiere die Verzögerungen nach Startzeit
        sorted_delays = sorted(self.delay_log, key=lambda x: x["start_time"])
        
        for i, log_entry in enumerate(sorted_delays):
            train_id = log_entry["train_id"]
            start_time = log_entry["start_time"]
            wait_duration = log_entry["wait_duration"]
            station = log_entry["station"]  # Position/Station des Zuges
            
            # Vereinfachtes Format mit der Station/Position des Zuges
            log_text = f"{train_id}: wartet für {station}, {int(start_time)} wartet {int(wait_duration)}s"
        
            
            # Prüfe, ob diese Verzögerung aktuell aktiv ist
            is_active = False
            for active_delay in current_delays:
                if (active_delay["train_id"] == train_id and 
                    abs(active_delay["start_time"] - start_time) < 0.1):
                    is_active = True
                    # Aktuelle Wartezeit für aktive Verzögerungen
                    current_duration = active_delay["current_duration"]
                    log_text = f"{train_id}: wartet für {station}, {int(start_time)} wartet {int(wait_duration)}s *"
                    break
            
            # Position für diesen Eintrag
            entry_y = start_y + i * line_height
            
            # Prüfe, ob der Eintrag noch in den Bereich passt
            if entry_y + line_height > self.height:
                break  # Nicht mehr anzeigen, wenn es nicht mehr passt
            
            # Hintergrund für aktive Verzögerungen
            if is_active:
                entry_rect = pygame.Rect(
                    self.delay_log_rect.left + 5, 
                    entry_y - 2, 
                    self.delay_log_rect.width - 10, 
                    line_height
                )
                pygame.draw.rect(self.screen, (240, 240, 200), entry_rect)
            
            # Farbe aus der Zugtabelle
            text_color = self.train_colors.get(train_id, self.BLACK)
            if not is_active:
                # Dunkleres Grau für nicht aktive Verzögerungen
                text_color = self.DARK_GRAY
                
            log_render = self.font_small.render(log_text, True, text_color)
            log_rect = log_render.get_rect(midleft=(self.delay_log_rect.left + 10, entry_y + line_height // 2))
            self.screen.blit(log_render, log_rect)

    def draw_buttons(self):
        """Zeichnet alle Buttons (Play/Pause, Restart und Geschwindigkeitsbuttons)"""
        # Play/Pause Button
        button_color = self.ORANGE if self.simulation_running else self.GREEN
        pygame.draw.rect(self.screen, button_color, self.play_button_rect)

        button_text = "Pause" if self.simulation_running else "Start"
        text_surf = self.font_medium.render(button_text, True, self.BLACK)
        text_rect = text_surf.get_rect(center=self.play_button_rect.center)
        self.screen.blit(text_surf, text_rect)
        
        # Restart Button
        pygame.draw.rect(self.screen, self.GRAY, self.restart_button_rect)
        
        restart_text = self.font_medium.render("Restart", True, self.BLACK)
        restart_rect = restart_text.get_rect(center=self.restart_button_rect.center)
        self.screen.blit(restart_text, restart_rect)

        # Geschwindigkeitsbuttons
        for button_rect, factor in self.speed_buttons:
            button_color = self.DARK_GRAY if self.speed_factor == factor else self.GRAY
            pygame.draw.rect(self.screen, button_color, button_rect)

            text_surf = self.font_medium.render(f"x{factor}", True, self.BLACK)
            text_rect = text_surf.get_rect(center=button_rect.center)
            self.screen.blit(text_surf, text_rect)

    def get_train_position(self, train_id, sim_time):
        if train_id not in self.train_segments:
            return None, None, None

        segments = self.train_segments[train_id]
        for segment in segments:
            if segment["start_time"] <= sim_time <= segment["end_time"]:
                segment_duration = segment["end_time"] - segment["start_time"]
                if segment_duration <= 0:
                    progress = 0
                else:
                    progress = (sim_time - segment["start_time"]) / segment_duration
                    progress = max(0.0, min(1.0, progress))

                x = segment["start_x"] + (segment["end_x"] - segment["start_x"]) * progress
                y = segment["start_y"] + (segment["end_y"] - segment["start_y"]) * progress

                return x, y, segment["status"]

        sorted_segments = sorted(segments, key=lambda x: x["end_time"], reverse=True)
        for segment in sorted_segments:
            if sim_time >= segment["end_time"]:
                return segment["end_x"], segment["end_y"], "geplant"
            elif sim_time <= segment["start_time"]:
                return segment["start_x"], segment["start_y"], "geplant"

        return None, None, None

    def draw_infrastructure(self):
        self.screen.fill(self.WHITE)
        self._update_completed_trains()

        
        count_text = self.font_small.render(
            f"SO→BDF: {self.completed_trains['SO->BDF']} | BDF→SO: {self.completed_trains['BDF->SO']}",
            True, self.BLACK)
        self.screen.blit(count_text, (20, 45))

        # Simulationszeit anzeigen (oben links)
        time_display = self.font_medium.render(f"Simulationszeit: {self.simulation_time:.1f}s", True, self.BLACK)
        self.screen.blit(time_display, (20, 20))
        
        # Gesamtlänge der Strecke anzeigen (oben rechts im Hauptbereich)
        total_length_text = self.font_medium.render(f"Gesamtlänge: {self.total_track_length} m", True, self.BLACK)
        total_length_rect = total_length_text.get_rect(topright=(self.main_area_width - 20, 20))
        self.screen.blit(total_length_text, total_length_rect)
        
        track_y = self.height // 2
        reservations = self.get_current_reservations(self.simulation_time)

        start_x = self.positions[self.route[0]]['x']
        end_x = self.positions[self.route[-1]]['x']
        pygame.draw.line(self.screen, self.DARK_GRAY, (start_x, track_y), (end_x, track_y), 3)

        # Abwechselnd Versatz in der Höhe für die Belegungszeit der Streckenabschnitte und Stationen
        section_offset_alt = False
        station_offset_alt = False

        for element, info in self.positions.items():
            is_station = element in self.stations
            is_section = element in self.sections

            # Berechne Belegungszeit und prozentuale Belegung
            occ_time = self.element_occupancy_times.get(element, 0)
            
            # Kapazität berücksichtigen
            capacity = 1
            if element in self.infrastructure:
                capacity = self.infrastructure[element].get("normal_capacity", 1)
            
            # Prozentuale Belegung unter Berücksichtigung der Kapazität
            occ_percent = (occ_time / self.total_simulation_time * 100) / capacity if capacity > 0 else 0
            
            # Erstelle Text für die Belegungszeit
            occ_text = self.font_small.render(f"{occ_time:.1f}s ({occ_percent:.1f}%)", True, self.DARK_GRAY)

            if is_section:
                middle_x = info['middle']
                section_text = self.font_medium.render(element, True, self.BLACK)
                text_rect = section_text.get_rect(center=(middle_x, track_y + 35))
                self.screen.blit(section_text, text_rect)
                
                # Streckenlänge
                length = self.section_lengths.get(element, "?")
                length_text = self.font_small.render(f"{length}m", True, self.DARK_GRAY)
                length_rect = length_text.get_rect(center=(middle_x, track_y + 50))
                self.screen.blit(length_text, length_rect)
                
                # Belegungszeit anzeigen (mit Versatz für Streckenabschnitte)
                occ_y_pos = track_y + 70
                if section_offset_alt:
                    occ_y_pos += 20
                section_offset_alt = not section_offset_alt  # Umschalten für nächstes Element
                
                occ_rect = occ_text.get_rect(center=(middle_x, occ_y_pos))
                self.screen.blit(occ_text, occ_rect)
                
                # Kapazitätskreise für Abschnitte mit mehr
                # Kapazitätskreise für Abschnitte mit mehr Abstand nach oben
                capacity_base_y = track_y - 120  # 60 Pixel weiter nach oben
                self.draw_capacity_circles(middle_x, capacity_base_y, capacity, reservations, element)

            if is_station:
                station_x = info['x']
                
                # Belegungszeit für Stationen oberhalb der Stationsbeschriftung anzeigen (mit Versatz)
                occ_y_pos = track_y - 50
                if station_offset_alt:
                    occ_y_pos -= 20  # Nach oben versetzt
                station_offset_alt = not station_offset_alt  # Umschalten für nächste Station
                
                occ_rect = occ_text.get_rect(center=(station_x, occ_y_pos))
                self.screen.blit(occ_text, occ_rect)
                
                # Stationsname
                station_text = self.font_medium.render(element, True, self.BLACK)
                text_rect = station_text.get_rect(center=(station_x, track_y - 35))
                self.screen.blit(station_text, text_rect)
                
                pygame.draw.circle(self.screen, self.BLACK, (int(station_x), track_y), 7)
                
                # Kapazitätskreise für Stationen mit mehr Abstand nach oben
                capacity_base_y = track_y - 120  # 60 Pixel weiter nach oben
                self.draw_capacity_circles(station_x, capacity_base_y, capacity, reservations, element)
                
        # Verzögerungsprotokoll zeichnen
        self.draw_delay_log()
        
        # Buttons zeichnen
        self.draw_buttons()

        # Nur aktive Züge zur aktuellen Zeit anzeigen
        active_trains = self.get_active_trains_at_time(self.simulation_time)
        
        for train_id in self.train_segments.keys():
            # Prüfen, ob der Zug zu diesem Zeitpunkt aktiv ist
            if train_id not in active_trains:
                continue
                
            x, y, status = self.get_train_position(train_id, self.simulation_time)
            if x is not None and y is not None:
                train_color = self.train_colors.get(train_id, self.PURPLE)
                train_width, train_height = 30, 15
                train_rect = pygame.Rect(x - train_width // 2, y - train_height // 2, train_width, train_height)
                pygame.draw.rect(self.screen, train_color, train_rect)

                id_text = self.font_small.render(train_id, True, self.WHITE)
                id_rect = id_text.get_rect(center=(x, y))
                self.screen.blit(id_text, id_rect)

        pygame.display.flip()


    def _update_completed_trains(self):
        for time_data in self.simulation_data:
            if time_data["time"] > self.simulation_time:
                break

            for train_id, train_info in time_data["trains"].items():
                if train_id in self.trains_seen_at_destination:
                    continue

                current_element = train_info.get("element")
                start_element = self.train_start_locations.get(train_id)

                if current_element in ["SO", "BDF"] and current_element != start_element:
                    if current_element == "BDF":
                        self.completed_trains["SO->BDF"] += 1
                    elif current_element == "SO":
                        self.completed_trains["BDF->SO"] += 1

                    self.trains_seen_at_destination.add(train_id)

    
    
    
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                elif event.key == pygame.K_SPACE:
                    self.simulation_running = not self.simulation_running
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()
                
                # Play/Pause Button
                if self.play_button_rect.collidepoint(mouse_pos):
                    self.simulation_running = not self.simulation_running
                
                # Restart Button
                elif self.restart_button_rect.collidepoint(mouse_pos):
                    self.restart_simulation()
                
                # Geschwindigkeitsbuttons
                for button_rect, factor in self.speed_buttons:
                    if button_rect.collidepoint(mouse_pos):
                        self.speed_factor = factor
                        print(f"Simulationsgeschwindigkeit: x{self.speed_factor}")
        
        return True

    def restart_simulation(self):
        """Setzt die Simulation auf den Anfang zurück"""
        self.simulation_time = 0
        self.simulation_running = False
        print("Simulation zurückgesetzt")

    def run(self):
        if not self.success:
            print("Konnte Infrastrukturdaten nicht laden. Beende...")
            return

        running = True
        last_time = time_module.time()

        while running:
            current_time = time_module.time()
            delta_time = current_time - last_time
            last_time = current_time

            if not self.handle_events():
                break

            if self.simulation_running:
                self.simulation_time += delta_time * self.speed_factor
                if self.simulation_data:
                    max_time = self.simulation_data[-1]["time"]
                    if self.simulation_time > max_time:
                        self.simulation_time = max_time
                        self.simulation_running = False

            self.draw_infrastructure()
            pygame.time.delay(30)

        pygame.quit()
        sys.exit()

def main():
    infra_path = "1_Infrastruktur.yaml"
    sim_log_path = "json/simulation_log.json"

    if not os.path.exists(infra_path):
        print(f"Die Datei {infra_path} wurde nicht gefunden.")
        return

    if not os.path.exists(sim_log_path):
        print(f"Die Datei {sim_log_path} wurde nicht gefunden.")
        return

    visualizer = InfrastructureVisualizer(infra_path, sim_log_path)
    visualizer.run()

if __name__ == "__main__":
    main()