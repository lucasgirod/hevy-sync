import logging
import garth
import os
import requests

logger = logging.getLogger(__name__)

class GarminClient:
    def __init__(self, email: str, password: str, tokens_file: str = "~/.garminconnect"):
        self.email = email
        self.password = password
        self.tokens_file = os.path.expanduser(tokens_file)
        self.client = None

    def _authenticate(self):
        """
        Authenticates with Garmin Connect using garth.
        Attempts to resume session from tokens file, otherwise logs in.
        Handles MFA if required.
        """
        if self.client:
            return

        try:
            logger.info(f"Attempting to resume Garmin Connect session from {self.tokens_file}...")
            garth.resume(self.tokens_file)
            self.client = garth.client
            logger.info("Garmin Connect session resumed successfully.")
        except (garth.GarthException, FileNotFoundError) as e:
            logger.warning(f"Could not resume Garmin Connect session: {e}. Attempting full login...")
            try:
                # prompt_mfa=True will make garth prompt in terminal if MFA is enabled
                garth.login(self.email, self.password, prompt_mfa=True)
                garth.dump(self.tokens_file) # Save tokens for future use
                self.client = garth.client
                logger.info("Successfully logged into Garmin Connect and saved tokens.")
            except garth.GarthException as e:
                logger.error(f"Garmin Connect login failed: {e}")
                raise

    def upload_activity_file(self, file_path: str, activity_name: str = None):
        """
        Uploads a FIT activity file to Garmin Connect.
        Uses garth to simulate the web upload process.
        """
        self._authenticate()

        if not os.path.exists(file_path):
            logger.error(f"FIT file not found at: {file_path}")
            raise FileNotFoundError(f"FIT file not found: {file_path}")

        logger.info(f"Uploading FIT file '{file_path}' to Garmin Connect...")

        # Garmin Connect's manual upload endpoint
        # This endpoint is typically used for manual uploads via the web interface.
        # The exact URL might vary slightly or require specific headers.
        # Based on common patterns and tools like GcpUploader [4] and fit-file-faker [5],
        # a multipart/form-data POST request is expected.
        upload_url = "https://connect.garmin.com/modern/proxy/upload-service/upload/.fit"
        
        # garth.client is a requests.Session object, so we can use its post method
        # to send multipart/form-data.
        
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f, 'application/octet-stream')}
                
                # The DI-Backend header is sometimes required for Garmin unofficial APIs [6]
                # However, for direct file upload, it might not be strictly necessary if mimicking browser.
                # Adding it for robustness.
                headers = {
                    "DI-Backend": "connectapi.garmin.com", # [6]
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36" # Mimic browser
                }

                response = self.client.post(upload_url, files=files, headers=headers)
                response.raise_for_status()
                
                # Garmin's upload service usually returns JSON with status and activity ID
                upload_result = response.json()
                
                if upload_result and upload_result.get('failures') ==:
                    logger.info(f"Successfully uploaded activity: {upload_result.get('uploadUuid')}")
                    # Optionally, you can get the activity ID from the response if available
                    # and log it or store it for idempotency.
                    # The response structure can vary, so check keys like 'activityId', 'activityIds'.
                    activity_ids = upload_result.get('activityIds')
                    if activity_ids:
                        logger.info(f"Garmin Activity IDs: {activity_ids}")
                    return True
                else:
                    logger.error(f"Failed to upload activity: {upload_result}")
                    return False

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error during Garmin upload: {e.response.status_code} - {e.response.text}")
            raise
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error during Garmin upload: {e}")
            raise
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout error during Garmin upload: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"An unexpected error occurred during Garmin upload: {e}")
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred during file upload: {e}")
            raise
