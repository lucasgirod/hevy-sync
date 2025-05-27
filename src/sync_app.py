import logging
import os
from datetime import datetime, timedelta, timezone

from config import (
    HEVY_API_KEY, GARMIN_EMAIL, GARMIN_PASSWORD,
    GARMIN_TOKENS_FILE, LAST_SYNC_DATE_FILE, logger
)
from hevy_client import HevyClient
from garmin_client import GarminClient
from fit_generator import FitGenerator

def get_last_sync_date() -> datetime:
    """Reads the last synchronization date from a file."""
    if os.path.exists(LAST_SYNC_DATE_FILE):
        with open(LAST_SYNC_DATE_FILE, 'r') as f:
            date_str = f.read().strip()
            if date_str:
                try:
                    # Assume UTC for consistency
                    return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
                except ValueError:
                    logger.warning(f"Invalid date format in {LAST_SYNC_DATE_FILE}. Starting from scratch.")
    # Default to a past date if file doesn't exist or is invalid
    return datetime.now(timezone.utc) - timedelta(days=30) # Sync last 30 days by default

def set_last_sync_date(sync_date: datetime):
    """Writes the last synchronization date to a file."""
    with open(LAST_SYNC_DATE_FILE, 'w') as f:
        f.write(sync_date.isoformat())

def main():
    logger.info("Starting hevy-to-garmin-sync process...")

    # Initialize clients
    hevy_client = HevyClient(api_key=HEVY_API_KEY)
    garmin_client = GarminClient(email=GARMIN_EMAIL, password=GARMIN_PASSWORD, tokens_file=GARMIN_TOKENS_FILE)
    fit_generator = FitGenerator()

    # Determine date range for synchronization
    last_sync_date = get_last_sync_date()
    current_time = datetime.now(timezone.utc)
    
    # Fetch workouts from Hevy
    try:
        # Fetch workouts from the day after last sync up to now
        # Add a small buffer to current_time to ensure all recent workouts are caught
        workouts_to_sync = hevy_client.get_workouts(last_sync_date, current_time + timedelta(hours=1))
        logger.info(f"Found {len(workouts_to_sync)} workouts from Hevy since {last_sync_date.isoformat()}.")
    except Exception as e:
        logger.error(f"Failed to fetch workouts from Hevy: {e}")
        return

    if not workouts_to_sync:
        logger.info("No new workouts to sync from Hevy.")
        set_last_sync_date(current_time) # Update sync date even if no new workouts
        return

    # Process and upload each workout
    successful_uploads = 0
    latest_workout_time = last_sync_date

    for workout in workouts_to_sync:
        workout_start_time_str = workout.get('start_time')
        if workout_start_time_str:
            try:
                workout_start_time = datetime.fromisoformat(workout_start_time_str).replace(tzinfo=timezone.utc)
                if workout_start_time <= last_sync_date:
                    logger.info(f"Skipping already synced workout: {workout.get('title')} ({workout_start_time_str})")
                    continue # Skip workouts older than or equal to last sync date
                
                # Update latest_workout_time for setting the next sync point
                if workout_start_time > latest_workout_time:
                    latest_workout_time = workout_start_time
            except ValueError:
                logger.warning(f"Could not parse start_time for workout: {workout.get('title')}. Skipping.")
                continue

        try:
            # Generate FIT file
            fit_file_path = fit_generator.generate_strength_activity_fit(workout)
            
            # Upload to Garmin Connect
            if garmin_client.upload_activity_file(fit_file_path, workout.get('title')):
                logger.info(f"Successfully synced workout '{workout.get('title')}' to Garmin Connect.")
                successful_uploads += 1
            else:
                logger.error(f"Failed to sync workout '{workout.get('title')}' to Garmin Connect.")
        except Exception as e:
            logger.error(f"Error processing or uploading workout '{workout.get('title')}': {e}")
        finally:
            # Clean up generated FIT file
            if 'fit_file_path' in locals() and os.path.exists(fit_file_path):
                os.remove(fit_file_path)
                logger.debug(f"Removed temporary FIT file: {fit_file_path}")

    # Update last sync date to the latest workout's start time (or current time if no new workouts)
    # Adding a small buffer (e.g., 1 second) to avoid re-fetching the exact same workout on next run
    set_last_sync_date(latest_workout_time + timedelta(seconds=1))
    
    logger.info(f"Synchronization complete. Successfully uploaded {successful_uploads} workouts.")
    logger.info(f"Next sync will start from: {get_last_sync_date().isoformat()}")

if __name__ == "__main__":
    main()
