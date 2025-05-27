import os
import io
import logging
from datetime import datetime
from hevy_sync.fit import FitEncoderStrength  # Du musst diese Klasse separat erstellen

log = logging.getLogger("hevy")


def prepare_hevy_syncdata(workouts):
    """Bereitet Hevy-Trainingsdaten zum Export in Garmin/FIT-Datei vor"""
    syncdata = []
    for workout in workouts:
        for ex in workout.exercises:
            for s in ex.get("sets", []):
                entry = {
                    "date_time": workout.start_time,
                    "exercise_name": ex.get("name", "Unbekannt"),
                    "weight": s.get("weight", 0.0),
                    "reps": s.get("reps", 0),
                    "type": "strength"
                }
                log.debug("Prepared exercise entry: %s", entry)
                syncdata.append(entry)
    return syncdata


def generate_strength_fitdata(syncdata):
    """Erstellt ein FIT-File aus Hevy-Krafttrainingsdaten"""
    if not syncdata:
        logging.info("Keine Hevy-Trainingsdaten gefunden.")
        return None

    fit = FitEncoderStrength()
    fit.write_file_info()
    fit.write_file_creator()
    fit.write_device_info(timestamp=datetime.now())

    for entry in syncdata:
        fit.write_strength_training(
            timestamp=entry["date_time"],
            exercise_name=entry["exercise_name"],
            weight=entry["weight"],
            reps=entry["reps"]
        )

    fit.finish()
    return fit


def write_to_fitfile(filename, fit_data):
    logging.info("Writing fitfile to %s.", filename)
    try:
        with open(filename, "wb") as fitfile:
            fitfile.write(fit_data.getvalue())
    except OSError:
        logging.error("Unable to open output fitfile! %s", filename)


# Beispielintegration im Hauptscript (sync.py)
# Statt Withings Daten:
#
# from hevy_sync.hevy import HevyAccount
# hevy = HevyAccount()
# workouts = hevy.get_workouts()
# syncdata = prepare_hevy_syncdata(workouts)
# fit_data = generate_strength_fitdata(syncdata)
# write_to_fitfile("output.strength.fit", fit_data)

# Hinweis: Du brauchst ein passendes Modul `FitEncoderStrength` mit Methoden:
# - write_file_info()
# - write_file_creator()
# - write_device_info(timestamp)
# - write_strength_training(timestamp, exercise_name, weight, reps)
# - finish()
