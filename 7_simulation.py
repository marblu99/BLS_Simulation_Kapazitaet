# Log-Funktion fuer alte Event-Logs (wird nur fuer Kompatibilität beibehalten)
def log_event(env, train_id, current_element, event, reserved):
    # Diese Funktion wird beibehalten, um bestehenden Code nicht zu brechen
    # Die Ereignisse werden aber nicht mehr gespeichert
    pass

import simpy
import yaml
import json

# ==== Einstellungen ====
max_sim_time = 3600  # Maximale Simulationszeit in Sekunden



log_schritte = 1    # Intervall in Sekunden fuer die Statusausgabe

# ==== Infrastruktur laden ====
with open("1_infrastructure.yaml") as f:
    infra_data   = yaml.safe_load(f)
    route        = infra_data["route"]
    infra_yaml   = infra_data["infrastructure"]

with open("3_timetable.yaml") as f:
    timetable_data = yaml.safe_load(f)["timetable"]

with open("json/breaktimes.json") as f:
    breaktimes   = json.load(f)

# ==== Ressourcen pro Abschnitt ====
class InfrastrukturElement:
    def __init__(self, env, name, capacity):
        self.name = name
        self.res  = simpy.Resource(env, capacity=capacity)

# ==== Simulationsumgebung ====
env = simpy.Environment()
infra = {
    name: InfrastrukturElement(env, name, data.get("normal_capacity", 1))
    for name, data in infra_yaml.items()
}

# ==== Globales Log fuer Zugstatus ====
status_log = []  # fuer Systemzustände in regelmäßigen Intervallen

# ==== Globales Zugstatus-Dictionary ====
zugstatus = {}  # Format: {zug_id: {"element": current_element, "reserved": [liste der reservierten elemente]}}

# ==== Status-Ausgabe-Prozess ====
def status_ausgabe(env):
    last_time = -1
    while True:
        # Zeit vor der Timeout-Operation abrufen und runden
        current_time = round(env.now, 1)
        
        # Überprüfen, ob Zeit sich geändert hat und Status ausgeben
        # Berücksichtige log_schritte fuer das Ausgabeintervall
        if current_time != last_time and (int(current_time) % log_schritte == 0 or current_time == 0):
            # Erstelle einen Eintrag fuer den aktuellen Zeitstempel
            status_entry = {
                "time": current_time,
                "trains": {}
            }
            
            if zugstatus:
                # Sammle Informationen über alle aktiven Züge
                for zug_id in sorted(zugstatus.keys()):
                    status = zugstatus[zug_id]
                    status_entry["trains"][zug_id] = {
                        "element": status['element'],
                        "status": status['status'],
                        "direction": "forward" if status.get('is_forward', True) else "backward",
                        "breaktime_info": status['breaktime_info'],
                        "reserved": status['reserved']
                    }
            
            # Füge den Eintrag zum Log hinzu
            status_log.append(status_entry)
            
            # Optional: Zeige auch auf der Konsole an (kann fuer Debugging aktiviert werden)
            if True:  # Setze auf False um Terminal-Ausgabe zu deaktivieren
                print(f"\n[{current_time:.1f}s] Systemstatus:")
                print("-" * 80)
                
                if zugstatus:
                    # Sortierte Ausgabe nach Zug-ID
                    for zug_id in sorted(zugstatus.keys()):
                        status = zugstatus[zug_id]
                        print(f"  Zug {zug_id}:")
                        print(f"    - Element: {status['element']}")
                        print(f"    - Status: {status['status']}")
                        print(f"    - Richtung: {'vorwärts' if status.get('is_forward', True) else 'rückwärts'}")
                        print(f"    - Breaktime: {status['breaktime_info']}")
                        print(f"    - Reserviert: {status['reserved']}")
                else:
                    print("  Keine Züge aktiv")
                
                print("-" * 80)
            
            last_time = current_time
            
        # Nach der Ausgabe warten wir
        yield env.timeout(log_schritte)  # Prüfe alle 0.1 Simulationseinheiten

# ==== Zugprozess ====
def zugfahrt(env, zug):
    zid             = zug["train_id"]
    verhalten       = zug["behaviour"]
    depart_station  = zug["depart"]["station"]
    depart_time     = zug["depart"]["time"]
    arrival_station = zug["arrival"]["station"]
    # Zeit, die die Abfahrtsstation vor der eigentlichen Abfahrt bereits belegt ist
    occupied_before_start = zug["depart"].get("occupied_before_start", 0)
    stops           = {s["station"]: s.get("stop_time", 0)
                       for s in zug.get("stops", [])}
    
    # Zugstatus wird bereits vor dem Start der Simulation initialisiert

    def update_zugstatus(current_element=None, action=None, status=None, breaktime_info=None):
        """Aktualisiert den globalen Zugstatus"""
        if current_element:
            zugstatus[zid]["element"] = current_element
        if status:
            zugstatus[zid]["status"] = status
        if breaktime_info:
            zugstatus[zid]["breaktime_info"] = breaktime_info
        
        # Aktualisiere die reservierten Elemente basierend auf dem aktuellen Status der Ressourcen
        reserved_elements = [n for n, e in infra.items() 
                           if e.res.count > 0 and any(u.proc == env.active_process for u in e.res.users)]
        
        # Sortiere die reservierten Elemente nach ihrer Position im Streckenverlauf
        # basierend auf der aktuellen Fahrtrichtung
        def route_element_order(element):
            if element in route:
                return route.index(element)
            return -1  # Falls Element nicht in der Route
        
        # Hole die aktuelle Fahrtrichtung aus dem zugstatus
        is_forward = zugstatus[zid].get("is_forward", True)
        
        # Sortiere nach Routenindex (bei forward) oder umgekehrt (bei backward)
        if is_forward:
            sorted_reserved = sorted(reserved_elements, key=route_element_order)
        else:
            sorted_reserved = sorted(reserved_elements, key=route_element_order, reverse=True)
        
        # Aktualisiere den Status
        zugstatus[zid]["reserved"] = sorted_reserved
        
        # Führe auch den Log-Eintrag durch
        if current_element and action:
            log_event(env, zid, current_element, action, sorted_reserved)

    def simulate_direction(depart_station, arrival_station):
        idx_depart  = route.index(depart_station)
        idx_arrival = route.index(arrival_station)
        is_forward  = idx_depart < idx_arrival
        route_used  = (
            route[idx_depart:idx_arrival+1]
            if is_forward else
            list(reversed(route[idx_arrival:idx_depart+1]))
        )

        # Merke die aktuelle Richtung fuer die Sortierung der reservierten Elemente
        zugstatus[zid]["is_forward"] = is_forward
        
        # Reserviere die Abfahrtsstation bereits vor der eigentlichen Abfahrt, wenn spezifiziert
        if is_forward and occupied_before_start > 0:
            # Berechne den Zeitpunkt, zu dem die Vorabreservierung stattfinden soll
            early_reservation_time = max(0, depart_time - occupied_before_start)
            
            # Warte bis zum Zeitpunkt der Vorabreservierung
            if env.now < early_reservation_time:
                yield env.timeout(early_reservation_time - env.now)
            
            # Reserviere die Abfahrtsstation vorzeitig
            if not any(u.proc==env.active_process for u in infra[depart_station].res.users):
                req = infra[depart_station].res.request()
                yield req
                update_zugstatus(
                    current_element=depart_station, 
                    action="early_reserve", 
                    status="bereitgestellt", 
                    breaktime_info=f"Abfahrtsstation {occupied_before_start}s vor Abfahrt reserviert"
                )
                
                # Warte noch bis zur eigentlichen Abfahrtszeit
                remaining_wait = max(0, depart_time - env.now)
                if remaining_wait > 0:
                    update_zugstatus(
                        current_element=depart_station,
                        action="waiting_for_departure",
                        status="wartet auf Abfahrt",
                        breaktime_info=f"Abfahrt in {remaining_wait:.1f}s geplant"
                    )
                    yield env.timeout(remaining_wait)
            
        # Sonst normale Abfahrtslogik (fuer Rückfahrt oder ohne Vorabreservierung)
        elif is_forward:
            # Wenn Wartezeit bis zur Abfahrt notwendig ist
            wait_time = max(0, depart_time - env.now)
            if wait_time > 0:
                update_zugstatus(
                    current_element=depart_station,
                    action="waiting_for_departure",
                    status="wartet auf Abfahrt",
                    breaktime_info=f"Abfahrt in {wait_time:.1f}s geplant"
                )
                yield env.timeout(wait_time)

        # Erstreservierung Abfahrt
        if is_forward and occupied_before_start > 0:
            # Die Abfahrtsstation wurde bereits vor der Abfahrt reserviert
            # Keine erneute Reservierung notwendig
            pass
        elif not any(u.proc==env.active_process for u in infra[depart_station].res.users):
            req = infra[depart_station].res.request()
            yield req
            update_zugstatus(
                current_element=depart_station, 
                action="reserve", 
                status="initialisiert", 
                breaktime_info=""
            )

        # Hilfsfunktionen fuer Reservierung
        def finde_naechste_knoten_mit_mehr_kapazitaet(start_idx):
            """Finde den nächsten Knoten mit Kapazität > 1 ab start_idx"""
            for j in range(start_idx+1, len(route_used)):
                k = route_used[j]
                if infra_yaml[k]["normal_capacity"] > 1:
                    return j
            return len(route_used)-1

        def versuche_reservierung(train, start_idx, limit_idx=None, include_highcap=True):
            """Versuche Reservierung aller Abschnitte von start_idx+1 bis limit_idx
               include_highcap=True bedeutet, dass auch der Knoten mit hoher Kapazität selbst reserviert wird
            """
            if limit_idx is None:
                ziel_idx = finde_naechste_knoten_mit_mehr_kapazitaet(start_idx)
            else:
                ziel_idx = limit_idx
                
            # Bestimme alle zu reservierenden Elemente
            needed = route_used[start_idx+1:ziel_idx+1]
            
            # Prüfe zuerst, ob alle Elemente frei oder vom eigenen Prozess reserviert sind
            for n in needed:
                r = infra[n].res
                if not (r.count < r.capacity or any(u.proc==env.active_process for u in r.users)):
                    return False
            
            # Wenn alle verfügbar sind, reserviere sie nacheinander
            for n in needed:
                r = infra[n].res
                if not any(u.proc==env.active_process for u in r.users):
                    req = r.request()
                    yield req
                    update_zugstatus(n, "reserve")
            return True

        def kapazitaet_frei_oder_selbst_reserviert(start_idx, ziel_idx):
            """Prüfe, ob alle Elemente zwischen start_idx+1 und ziel_idx frei oder selbst reserviert sind"""
            needed = route_used[start_idx+1:ziel_idx+1]
            for n in needed:
                r = infra[n].res
                if not (r.count < r.capacity or any(u.proc==env.active_process for u in r.users)):
                    return False
            return True

        # Initiale Vorreservierung ab Startstation
        # Reserviere explizit bis zum nächsten Knoten mit hoher Kapazität (einschließlich dieses Knotens)
        start_idx = route_used.index(depart_station)
        next_highcap_idx = finde_naechste_knoten_mit_mehr_kapazitaet(start_idx)
        
        # Warte bis Reservierung möglich
        while not (yield from versuche_reservierung(zid, start_idx, next_highcap_idx)):
            yield env.timeout(1)

        # Durchlauf aller Zwischenabschnitte
        for i in range(start_idx+1, len(route_used)-1):
            current = route_used[i]
            prev    = route_used[i-1]
            next_el = route_used[i+1]

            # Release previous element
            for req in list(infra[prev].res.users):
                if req.proc==env.active_process:
                    infra[prev].res.release(req)
                    update_zugstatus(prev, "release")

            # Einfahrt in aktuelles Element
            update_zugstatus(current, "start")

            # Breaktime fuer Einfahrt (start0/startV)
            section = current if current not in ["BDF","SO"] else prev
            forward_phys = route.index(prev)<route.index(current)
            bt = breaktimes.get(section, {}).get("forward" if forward_phys else "backward", {})
            
            # Zeit fuer Einfahrt in aktuelles Element 
            # start0 wenn im vorherigen Element ein Halt war, sonst startV
            start_key = f"time_at_breakpoint_{'start0' if prev in stops else 'startV'}"
            breaktime_value = bt.get(start_key, 0)
            direction = "forward" if forward_phys else "backward"
            update_zugstatus(
                current_element=current, 
                action="start", 
                status="in Fahrt", 
                breaktime_info=f"{start_key} ({direction}): {breaktime_value:.1f}s"
            )
            yield env.timeout(breaktime_value)

            # Prüfe zuerst auf Halt im aktuellen Element, bevor Breakpoint-Reservierung versucht wird
            if current in stops:
                update_zugstatus(
                    current_element=current, 
                    action="stop", 
                    status="Halt", 
                    breaktime_info=f"Planmaessiger Halt fuer {stops[current]:.1f}s"
                )
                yield env.timeout(stops[current])
            
            # Breakpoint-Logik erst nach dem Halt ausführen:
            # 1. Prüfen, ob nächstes Element Kapazität = 1 oder >1 hat
            # 2. Abhängig davon unterschiedliche Reservierungsstrategie und Fahrprofilwahl
            if i+1 < len(route_used)-1:  # Überprüfe, ob wir nicht schon am Ende sind
                next_el = route_used[i+1]
                next_el_capacity = infra_yaml[next_el]["normal_capacity"]
                next_stop = next_el in stops  # Hält der Zug im nächsten Element?
                
                # Verschiedene Strategien je nach Kapazität des nächsten Elements
                if next_el_capacity == 1:  # Nächstes Element hat Kapazität = 1
                    # 1. Reserviere alle Elemente bis zur nächsten Entlastung
                    next_highcap_idx = len(route_used) - 1  # Standard: Ende der Route
                    for j in range(i+1, len(route_used)):
                        k = route_used[j]
                        if infra_yaml[k]["normal_capacity"] > 1:
                            next_highcap_idx = j
                            break
                    
                    # Warte, bis Reservierung möglich
                    waiting_reported = False
                    while not kapazitaet_frei_oder_selbst_reserviert(i, next_highcap_idx):
                        if not waiting_reported:
                            update_zugstatus(
                                current_element=current, 
                                action="waiting", 
                                status="wartet", 
                                breaktime_info="Wartet auf freie Kapazitaet"
                            )
                            waiting_reported = True
                        yield env.timeout(1)
                    
                    # Reservierung durchführen
                    yield from versuche_reservierung(zid, i, next_highcap_idx)
                    
                    # 2. Fahrzeitprofil nach Halt/Durchfahrt wählen
                    stop_key = f"remaining_time_{'stop0' if next_stop else 'stopV'}"
                    breaktime_value = bt.get(stop_key, 0)
                    direction = "forward" if forward_phys else "backward"
                    
                    update_zugstatus(
                        current_element=current, 
                        action="braking", 
                        status="in Fahrt", 
                        breaktime_info=f"{stop_key} ({direction}): {breaktime_value:.1f}s fuer {next_el} (Engstelle)"
                    )
                    yield env.timeout(breaktime_value)
                
                else:  # Nächstes Element hat Kapazität > 1
                    # 1. Prüfe ob der Zug hält
                    if next_stop:  # Zug hält im nächsten Element
                        # Verwende stop0-Profil
                        stop_key = "remaining_time_stop0"
                        breaktime_value = bt.get(stop_key, 0)
                        direction = "forward" if forward_phys else "backward"
                        
                        update_zugstatus(
                            current_element=current, 
                            action="braking", 
                            status="in Fahrt", 
                            breaktime_info=f"{stop_key} ({direction}): {breaktime_value:.1f}s fuer {next_el} (Entlastung)"
                        )
                        yield env.timeout(breaktime_value)
                    
                    else:  # Zug fährt durch
                        # Reserviere ab dem übernächsten Element bis zur nächsten Entlastung
                        if i+2 < len(route_used):
                            next_next_el_idx = i+2
                            next_highcap_idx = len(route_used) - 1  # Standard: Ende der Route
                            
                            for j in range(next_next_el_idx, len(route_used)):
                                k = route_used[j]
                                if infra_yaml[k]["normal_capacity"] > 1:
                                    next_highcap_idx = j
                                    break
                            
                            # Warte, bis Reservierung möglich (ab dem übernächsten Element)
                            waiting_reported = False
                            while not kapazitaet_frei_oder_selbst_reserviert(i+1, next_highcap_idx):
                                if not waiting_reported:
                                    update_zugstatus(
                                        current_element=current, 
                                        action="waiting", 
                                        status="wartet", 
                                        breaktime_info="Wartet auf freie Kapazitaet (nach Entlastung)"
                                    )
                                    waiting_reported = True
                                yield env.timeout(1)
                            
                            # Reservierung durchführen (ab übernächstem Element)
                            yield from versuche_reservierung(zid, i+1, next_highcap_idx)
                        
                        # Verwende stopV-Profil fuer Durchfahrt
                        stop_key = "remaining_time_stopV"
                        breaktime_value = bt.get(stop_key, 0)
                        direction = "forward" if forward_phys else "backward"
                        
                        update_zugstatus(
                            current_element=current, 
                            action="braking", 
                            status="in Fahrt", 
                            breaktime_info=f"{stop_key} ({direction}): {breaktime_value:.1f}s fuer {next_el} (Durchfahrt)"
                        )
                        yield env.timeout(breaktime_value)

        # Endstation separat behandeln
        prev = route_used[-2]
        end = route_used[-1]
        
        # Freigabe des vorletzten Elements
        for req in list(infra[prev].res.users):
            if req.proc==env.active_process:
                infra[prev].res.release(req)
                update_zugstatus(prev, "release")

        # Ankunft an der Endstation
        update_zugstatus(
            current_element=end, 
            action="start", 
            status="in Fahrt", 
            breaktime_info=""  # Keine Breaktime bei der finalen Einfahrt
        )
        
        # Eventueller Halt an der Endstation
        if end in stops:
            update_zugstatus(
                current_element=end, 
                action="stop", 
                status="Halt", 
                breaktime_info=f"Planmaessiger Halt fuer {stops[end]:.1f}s"
            )
            yield env.timeout(stops[end])

        update_zugstatus(
            current_element=arrival_station, 
            action="arrival", 
            status="angekommen", 
            breaktime_info=""
        )

        # Rückfahrt wenn verhalten="return"
        if verhalten=="return":
            yield from simulate_direction(arrival_station, depart_station)
        else:
            # Wenn der Zug seinen Lauf beendet hat, entferne ihn aus dem zugstatus
            if zid in zugstatus:
                del zugstatus[zid]

    # Starte Simulation
    yield from simulate_direction(depart_station, arrival_station)

# Status-Manager vor dem Start der eigentlichen Simulation starten
# Damit wird der Anfangszustand bei t=0 garantiert ausgegeben
process_status = env.process(status_ausgabe(env))

# Prozesse starten
for zug in timetable_data:
    # Initialisiere Zugstatus bereits hier vor dem Start der Simulation
    zid = zug["train_id"]
    idx_depart = route.index(zug["depart"]["station"])
    idx_arrival = route.index(zug["arrival"]["station"])
    is_forward = idx_depart < idx_arrival
    
    # Überprüfe auf occupied_before_start Parameter
    occupied_before_start = zug["depart"].get("occupied_before_start", 0)
    early_reservation_info = ""
    if occupied_before_start > 0:
        early_reservation_info = f", Vorreservierung {occupied_before_start}s vor Abfahrt"
    
    zugstatus[zid] = {
        "element": zug["depart"]["station"], 
        "reserved": [], 
        "status": "geplant",  # Neuer Status "geplant" fuer Züge vor Abfahrt
        "breaktime_info": f"Geplante Abfahrt bei {zug['depart']['time']}s{early_reservation_info}",
        "is_forward": is_forward  # Speichere die Bewegungsrichtung
    }
    
    # Starte den Zugprozess
    env.process(zugfahrt(env, zug))

# Simulation ausführen
print(f"Starte Simulation fuer {max_sim_time} Sekunden mit Log-Intervall {log_schritte}s...")
env.run(until=max_sim_time)
print("Simulation abgeschlossen.")

# Log ins JSON-Verzeichnis schreiben
with open("json/simulation_log.json", "w") as f:
    json.dump(status_log, f, indent=2)
print(f"Log gespeichert in json/simulation_log.json ({len(status_log)} Statuseinträge)")
print("Struktur: Liste von Einträgen [Zeit, Zuginfos, ...] analog zur vorherigen Terminalausgabe.")