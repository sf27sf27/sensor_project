"""
API communication and synchronization functions.
Uses SQLAlchemy ORM for all database access.
"""
import json
import time
import requests
from sqlalchemy.exc import SQLAlchemyError

from lib.config import (
    logger,
    API_BASE_URL,
    READINGS_ENDPOINT,
    READINGS_BULK_ENDPOINT,
    API_HEADERS,
    BULK_SYNC_BATCH_SIZE,
)
from lib.database import save_to_backup
from lib.server.models import LocalSessionLocal, ReadingORM


def check_api_health():
    """Check if API server is reachable"""
    try:
        response = requests.get(f"{API_BASE_URL}/docs", timeout=5)
        if response.status_code == 200:
            logger.info(f"API server is reachable at {API_BASE_URL}")
            return True
    except requests.exceptions.RequestException as e:
        logger.warning(f"API server health check failed: {e}")
        return False


def insert_reading(device_id, ts_utc, json_data, retry_count=0, max_retries=3):
    """Send reading to API endpoint with retry logic, fallback to local DB on failure"""
    try:
        # Parse JSON data if it's a string
        if isinstance(json_data, str):
            payload = json.loads(json_data)
        else:
            payload = json_data
        
        # Prepare the request payload according to API spec
        request_payload = {
            "device_id": device_id,
            "ts_utc": ts_utc.isoformat(),
            "payload": payload
        }
        
        # Send POST request to API
        response = requests.post(
            READINGS_ENDPOINT,
            json=request_payload,
            headers=API_HEADERS,
            timeout=10
        )
        
        if response.status_code == 201:
            logger.info(f"Reading successfully sent to API: {response.json()}")
            return True
        elif response.status_code >= 500 and retry_count < max_retries:
            # Server error - retry with exponential backoff
            wait_time = 2 ** retry_count  # 1s, 2s, 4s
            logger.warning(f"API server error ({response.status_code}), retrying in {wait_time}s (attempt {retry_count + 1}/{max_retries})")
            time.sleep(wait_time)
            return insert_reading(device_id, ts_utc, json_data, retry_count + 1, max_retries)
        else:
            logger.error(f"API returned status {response.status_code}: {response.text}")
            # Fallback to backup database
            save_to_backup(device_id, ts_utc, json_data)
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send reading to API: {e}")
        # Fallback to backup database
        save_to_backup(device_id, ts_utc, json_data)
        return False
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON payload: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending to API: {e}")
        # Fallback to backup database
        save_to_backup(device_id, ts_utc, json_data)
        return False


def sync_backup_to_api():
    """Periodically sync unsynced records from local backup to API using bulk upload"""
    while True:
        db = LocalSessionLocal()
        try:
            # Fetch unsynced records from backup DB using ORM
            unsynced_records = db.query(ReadingORM).all()
            
            if unsynced_records:
                logger.info(f"Found {len(unsynced_records)} records in backup database to sync")
                
                # Process records in batches
                total_synced = 0
                for batch_start in range(0, len(unsynced_records), BULK_SYNC_BATCH_SIZE):
                    batch_end = min(batch_start + BULK_SYNC_BATCH_SIZE, len(unsynced_records))
                    batch = unsynced_records[batch_start:batch_end]
                    
                    try:
                        # Prepare batch payload from ORM objects
                        batch_readings = []
                        batch_record_ids = []
                        
                        for record in batch:
                            batch_record_ids.append(record.id)
                            
                            # Build reading entry from ORM object
                            reading_entry = {
                                "device_id": record.device_id,
                                "ts_utc": record.ts_utc.isoformat(),
                                "payload": record.payload  # Already a dict from JSONB column
                            }
                            batch_readings.append(reading_entry)
                        
                        # Send batch to API with retry logic
                        bulk_payload = {"readings": batch_readings}
                        
                        # Retry helper for bulk sync
                        def attempt_bulk_sync(attempt=0, max_attempts=3):
                            try:
                                response = requests.post(
                                    READINGS_BULK_ENDPOINT,
                                    json=bulk_payload,
                                    headers=API_HEADERS,
                                    timeout=30  # Allow longer timeout for bulk uploads
                                )
                                
                                if response.status_code == 201:
                                    response_data = response.json()
                                    created_count = response_data.get("created", 0)
                                    logger.info(f"Bulk synced {created_count} records to API (batch {batch_start // BULK_SYNC_BATCH_SIZE + 1})")
                                    return True, response
                                elif response.status_code >= 500 and attempt < max_attempts:
                                    # Server error - retry with exponential backoff
                                    wait_time = 2 ** attempt
                                    logger.warning(f"API server error during sync ({response.status_code}), retrying in {wait_time}s (attempt {attempt + 1}/{max_attempts})")
                                    time.sleep(wait_time)
                                    return attempt_bulk_sync(attempt + 1, max_attempts)
                                else:
                                    logger.warning(f"Failed to sync batch: API returned {response.status_code} - {response.text}")
                                    return False, response
                            except requests.exceptions.RequestException as e:
                                if attempt < max_attempts:
                                    wait_time = 2 ** attempt
                                    logger.warning(f"Bulk sync request failed, retrying in {wait_time}s: {e}")
                                    time.sleep(wait_time)
                                    return attempt_bulk_sync(attempt + 1, max_attempts)
                                else:
                                    logger.error(f"Bulk sync failed after {max_attempts} attempts: {e}")
                                    return False, None
                        
                        success, response = attempt_bulk_sync()
                        
                        if success and response.status_code == 201:
                            # Delete successfully uploaded records from local DB
                            try:
                                db.query(ReadingORM).filter(
                                    ReadingORM.id.in_(batch_record_ids)
                                ).delete()
                                db.commit()
                                logger.info(f"Deleted {len(batch_record_ids)} synced records from backup database")
                                total_synced += len(batch_record_ids)
                            except SQLAlchemyError as e:
                                logger.error(f"Failed to delete synced records: {e}")
                                db.rollback()
                        else:
                            logger.warning(f"Skipping deletion of batch records due to API sync failure")
                            
                    except Exception as e:
                        logger.error(f"Failed to sync batch: {e}")
                
                if total_synced > 0:
                    logger.info(f"Successfully synced {total_synced} total records to API")
            
        except SQLAlchemyError as e:
            logger.error(f"Backup sync to API failed: {e}")
            db.rollback()
        except Exception as e:
            logger.error(f"Unexpected error in backup sync: {e}")
        finally:
            db.close()
        
        # Wait before next sync attempt
        time.sleep(5)

