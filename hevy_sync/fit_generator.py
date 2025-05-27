import datetime
import os
import logging
from fit_tool.fit_file import FitFile
from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.session_message import SessionMessage
from fit_tool.profile.messages.event_message import EventMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.profile_type import FileType, Manufacturer, Sport, Event, EventType

logger = logging.getLogger(__name__)

class FitGenerator:
    """
    Generates Garmin FIT-Activity-Dateien aus Hevy-Trainingsdaten.
    """
    def generate_strength_activity_fit(self, hevy_workout_data: dict, output_dir: str = "temp_fit_files") -> str:
        """
        Generiert eine FIT-Datei für eine Krafttrainingsaktivität aus Hevy-Daten.

        Args:
            hevy_workout_data (dict): Ein Dictionary, das die Hevy-Trainingsdaten darstellt.
                                      Erwartet Felder wie 'title', 'start_time', 'end_time',
                                      und eine Liste von 'exercises', wobei jede Übung
                                      'exercise_title', 'sets' (Liste von Dictionaries mit 'reps', 'weight_lbs', 'duration_seconds') enthält.
            output_dir (str): Verzeichnis zum Speichern der generierten FIT-Datei.

        Returns:
            str: Der Pfad zur generierten FIT-Datei.
        """
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Zeitstempel für die FIT-Datei (Garmin Epoch ist 1989-12-31 00:00:00 UTC)
        # Ensure datetime objects are timezone-aware (UTC)
        start_datetime = datetime.datetime.fromisoformat(hevy_workout_data['start_time'])
        end_datetime = datetime.datetime.fromisoformat(hevy_workout_data['end_time'])
        
        # FIT-Zeitstempel sind Sekunden seit Garmin Epoch
        garmin_epoch = datetime.datetime(1989, 12, 31, 0, 0, 0, tzinfo=datetime.timezone.utc)
        
        # Sicherstellen, dass start_datetime und end_datetime UTC sind, wenn sie aus ISO kommen
        if start_datetime.tzinfo is None:
            start_datetime = start_datetime.replace(tzinfo=datetime.timezone.utc)
        if end_datetime.tzinfo is None:
            end_datetime = end_datetime.replace(tzinfo=datetime.timezone.utc)

        timestamp_fit_start = int((start_datetime - garmin_epoch).total_seconds())
        timestamp_fit_end = int((end_datetime - garmin_epoch).total_seconds())
        
        total_elapsed_time_seconds = (end_datetime - start_datetime).total_seconds()
        
        # Geschätzte Kalorien für Krafttraining (z.B. 6 kcal/Minute)
        total_calories = int((total_elapsed_time_seconds / 60) * 6)

        builder = FitFileBuilder(auto_define=True)

        # 1. FileIdMessage [7, 8, 9, 10, 11, 12, 13, 14]
        file_id_message = FileIdMessage()
        file_id_message.type = FileType.ACTIVITY
        file_id_message.manufacturer = Manufacturer.GARMIN # Faking a Garmin device [5]
        file_id_message.product = 12345 # Example product ID
        file_id_message.serial_number = 0x12345678
        file_id_message.time_created = timestamp_fit_start
        builder.add(file_id_message)

        # 2. SessionMessage [7, 8, 9, 10, 12, 13, 14]
        session_message = SessionMessage()
        session_message.start_time = timestamp_fit_start
        session_message.start_position_lat = 0 # Not applicable for strength, set to 0
        session_message.start_position_long = 0 # Not applicable for strength, set to 0
        session_message.total_elapsed_time = total_elapsed_time_seconds
        session_message.total_timer_time = total_elapsed_time_seconds # Assuming no pauses for simplicity
        session_message.sport = Sport.STRENGTH_TRAINING # [10, 15]
        session_message.sub_sport = Sport.GENERIC
        session_message.total_calories = total_calories
        session_message.avg_heart_rate = 0 # Can be estimated if available, otherwise 0
        session_message.max_heart_rate = 0 # Can be estimated if available, otherwise 0
        session_message.total_distance = 0 # Not applicable for strength
        session_message.num_laps = 1 # One session, one lap for simplicity
        session_message.timestamp = timestamp_fit_end # End of session timestamp
        session_message.message_index = 0 # Unique index for session message
        session_message.event = Event.SESSION
        session_message.event_type = EventType.STOP
        builder.add(session_message)

        # 3. EventMessages (TIMER_START, TIMER_STOP) [7, 8, 9, 12, 13, 14]
        event_start_message = EventMessage()
        event_start_message.timestamp = timestamp_fit_start
        event_start_message.event = Event.TIMER
        event_start_message.event_type = EventType.START
        builder.add(event_start_message)

        event_stop_message = EventMessage()
        event_stop_message.timestamp = timestamp_fit_end
        event_stop_message.event = Event.TIMER
        event_stop_message.event_type = EventType.STOP
        builder.add(event_stop_message)

        # 4. RecordMessages [7, 8, 9, 12, 13, 14]
        # For strength training, records can be sparse.
        # We'll create one record per exercise, or even per set, to show progression.
        # For simplicity, let's create a record at the start of each exercise.
        
        current_timestamp_offset = 0
        for exercise in hevy_workout_data.get('exercises',):
            # Calculate a timestamp for the start of each exercise
            exercise_start_time = start_datetime + datetime.timedelta(seconds=current_timestamp_offset)
            timestamp_fit_exercise_start = int((exercise_start_time - garmin_epoch).total_seconds())

            record_message = RecordMessage()
            record_message.timestamp = timestamp_fit_exercise_start
            record_message.distance = 0.0 # No distance for strength
            record_message.calories = 0 # Calories are aggregated in session message
            record_message.heart_rate = 0 # If available from Hevy, can be set here
            record_message.power = 0 # If available from Hevy, can be set here
            builder.add(record_message)

            # Advance time for next exercise/set
            # A simple heuristic: assume each set takes 60 seconds (including rest)
            # Or use actual duration_seconds if available for time-based exercises
            exercise_duration = sum(s.get('duration_seconds', 60) for s in exercise.get('sets',))
            current_timestamp_offset += exercise_duration

        # Ensure a final record message at the end of the workout if not already covered
        # This handles cases where the calculated offset might not perfectly align with end_datetime
        # or if there are no exercises.
        if not hevy_workout_data.get('exercises') or timestamp_fit_end > (start_datetime + datetime.timedelta(seconds=current_timestamp_offset) - garmin_epoch).total_seconds():
            final_record_message = RecordMessage()
            final_record_message.timestamp = timestamp_fit_end
            final_record_message.distance = 0.0
            final_record_message.calories = 0
            builder.add(final_record_message)

        # Build FIT File
        fit_file = builder.build()

        # Save to a temporary file
        file_name = f"hevy_strength_workout_{start_datetime.strftime('%Y%m%d_%H%M%S')}.fit"
        output_path = os.path.join(output_dir, file_name)
        fit_file.to_file(output_path)
        logger.info(f"FIT file generated at: {output_path}")

        return output_path
