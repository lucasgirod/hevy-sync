import os
import json
import logging
import time
import requests
from datetime import datetime

log = logging.getLogger("hevy")

HOME = os.environ.get("HOME", ".")
USER_CONFIG = os.environ.get("HEVY_USER", os.path.join(HOME, ".hevy_user.json"))
HEVY_API_URL = "https://api.hevyapp.com/v1/workouts"

class HevyException(Exception):
    pass

class HevyConfig:
    # ... (unverändert) ...

class HevyAccount:
    def __init__(self):
        self.cfg = HevyConfig(USER_CONFIG)
        self.config = self.cfg.config

        if not self.config.get("api_key"):
            self.config["api_key"] = input("Bitte gib deinen Hevy API-Key ein: ").strip()
            self.cfg.write()
            log.info("API-Key gespeichert in %s", USER_CONFIG)

    def get_lastsync(self):
        return self.config.get("last_sync", int(time.mktime(datetime.today().timetuple())))

    def set_lastsync(self):
        self.config["last_sync"] = int(time.time())
        self.cfg.write()

    def get_height(self):
        """Liest die Körpergröße des Nutzers (in Metern) aus, falls verfügbar."""
        height_val = os.getenv("HEVY_HEIGHT", "")
        if height_val:
            try:
                return float(height_val)
            except ValueError:
                log.warning("Invalid HEVY_HEIGHT value. Height not set.")
        return None  # Keine Höhe vorhanden oder konfiguriert

    def get_workouts(self, since_timestamp=None):
        headers = {"api-key": self.config["api_key"]}
        params = {}
        if since_timestamp:
            params["after"] = since_timestamp  # UNIX-Timestamp (Epoch seconds)
        response = requests.get(HEVY_API_URL, headers=headers, params=params)
        if response.status_code != 200:
            raise HevyException(f"Fehler beim Abrufen der Workouts: {response.status_code} - {response.text}")
        # Liste von Workouts zurückgeben
        return [HevyWorkout(w) for w in response.json()]

    def get_measurements(self, startdate=None, enddate=None):
        """Holt alle Workouts im gegebenen Datumsbereich als 'Messungen'."""
        try:
            workouts = self.get_workouts(since_timestamp=startdate)
        except HevyException as e:
            log.error("Hevy API error: %s", e)
            return []
        # Filtern bis Enddatum (enddate ist Epoch-Sekunden bis einschließlich)
        if enddate:
            workouts = [w for w in workouts if int(time.mktime(w.start_time.timetuple())) <= enddate]
        # Rückgabe der Workouts (als Measurement Groups)
        return workouts

class HevyWorkout:
    def __init__(self, data):
        self.raw = data
        # start_time kommt als UNIX-Timestamp (Sekunden) – in datetime umwandeln
        self.start_time = datetime.fromtimestamp(data.get("start_time", 0))
        self.exercises = data.get("exercises", [])

    def __str__(self):
        return f"Workout vom {self.start_time.strftime('%Y-%m-%d')} mit {len(self.exercises)} Übungen"

    def to_dict(self):
        return {"date": self.start_time.isoformat(), "exercises": self.exercises}

    def to_fit_summary(self):
        """Erstellt einen zusammenfassenden String aller Übungen und Sätze."""
        lines = []
        for ex in self.exercises:
            name = ex.get("name", "Unbekannt")
            for s in ex.get("sets", []):
                reps = s.get("reps")
                weight = s.get("weight")
                lines.append(f"{name}: {reps}x{weight}kg")
        return "\n".join(lines)

    # Neue Methoden für die Integration als Messungs-Objekt:
    def get_datetime(self):
        return self.start_time

    def get_weight(self):
        """Gibt das gesamte bewegte Gewicht (Summe aus Gewicht*Wdh) des Workouts zurück."""
        total = 0.0
        for ex in self.exercises:
            for s in ex.get("sets", []):
                weight = s.get("weight") or 0
                reps = s.get("reps") or 0
                total += weight * reps
        # Falls kein Zusatzgewicht bewegt (total=0), kleinen Wert einsetzen, damit Eintrag nicht übersprungen wird
        if total <= 0:
            return 1.0
        # auf zwei Nachkommastellen runden (kg)
        return round(total, 2)

    def get_fat_ratio(self):         # Körperfettanteil – nicht anwendbar
        return None

    def get_muscle_mass(self):       # Muskelmasse – nicht anwendbar
        return None

    def get_hydration(self):         # Hydration – nicht anwendbar
        return None

    def get_bone_mass(self):         # Knochenmasse – nicht anwendbar
        return None

    def get_pulse_wave_velocity(self):
        return None

    def get_heart_pulse(self):       # Puls – ggf. Teil der Übungen, hier nicht genutzt
        return None

    def get_raw_data(self):
        """Stellt Rohdaten für den JSON-Export bereit."""
        # Für Kompatibilität geben wir uns selbst als einziges Datenobjekt zurück
        return [self]

    def json_dict(self):
        """Bereitet ein Dict mit den wichtigsten Workout-Infos für JSON-Ausgabe vor."""
        summary = {"Exercises": []}
        total_volume = 0.0
        total_sets = 0
        for ex in self.exercises:
            name = ex.get("name", "Unbekannt")
            sets = ex.get("sets", [])
            ex_reps = 0
            ex_volume = 0.0
            for s in sets:
                reps = s.get("reps") or 0
                weight = s.get("weight") or 0
                ex_reps += reps
                ex_volume += weight * reps
            total_sets += len(sets)
            total_volume += ex_volume
            summary["Exercises"].append({
                "Name": name,
                "Sets": len(sets),
                "TotalReps": ex_reps,
                "TotalWeight": ex_volume
            })
        summary["TotalSets"] = total_sets
        summary["TotalVolume"] = total_volume
        summary["ExerciseCount"] = len(self.exercises)
        return {"Workout": summary}
