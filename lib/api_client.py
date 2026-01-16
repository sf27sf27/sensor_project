"""
API communication and synchronization functions.
Uses SQLAlchemy ORM for all database access.
Includes circuit breaker, timeout protection, and backpressure handling.
"""
import json
import time
import requests
import threading
from enum import Enum
from datetime import datetime, timedelta
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


class CircuitBreakerState(Enum):
    """States for the circuit breaker pattern"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if API recovered


class APICircuitBreaker:
    """
    Circuit breaker to prevent cascading failures when API is unavailable.
    Prevents resource exhaustion by stopping requests to a failing API.
    """
    def __init__(self, failure_threshold=3, recovery_timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitBreakerState.CLOSED
        self.last_failure_time = None
        self.lock = threading.Lock()
    
    def record_success(self):
        """Record a successful API call"""
        with self.lock:
            self.failure_count = 0
            self.state = CircuitBreakerState.CLOSED
    
    def record_failure(self):
        """Record a failed API call"""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                logger.warning(f"Circuit breaker OPEN - API failures exceeded threshold ({self.failure_count})")
    
    def is_available(self):
        """Check if API is available for calls"""
        with self.lock:
            if self.state == CircuitBreakerState.CLOSED:
                return True
            
            if self.state == CircuitBreakerState.OPEN:
                # Check if recovery timeout has elapsed
                elapsed = datetime.now() - self.last_failure_time
                if elapsed > timedelta(seconds=self.recovery_timeout):
                    self.state = CircuitBreakerState.HALF_OPEN
                    logger.info("Circuit breaker HALF_OPEN - attempting recovery")
                    return True
                return False
            
            # HALF_OPEN state
            return True
    
    def get_state(self):
        """Get current circuit breaker state"""
        with self.lock:
            return self.state.value


# Global circuit breaker instance
api_circuit_breaker = APICircuitBreaker(failure_threshold=3, recovery_timeout=60)


def check_api_health():
    """Check if API server is reachable"""
    if not api_circuit_breaker.is_available():
        logger.warning("Circuit breaker is OPEN - API assumed unreachable")
        return False
    
    try:
        response = requests.get(f"{API_BASE_URL}/docs", timeout=5)
        if response.status_code == 200:
            api_circuit_breaker.record_success()
            logger.info(f"API server is reachable at {API_BASE_URL}")
            return True
    except requests.exceptions.RequestException as e:
        api_circuit_breaker.record_failure()
        logger.warning(f"API server health check failed: {e}")
        return False
    
    api_circuit_breaker.record_failure()
    return False


def insert_reading(device_id, ts_utc, json_data):
    """Send reading to API endpoint, fallback to local DB on failure"""
    # Check circuit breaker before attempting
    if not api_circuit_breaker.is_available():
        logger.warning("API circuit breaker is open - falling back to backup database")
        save_to_backup(device_id, ts_utc, json_data)
        return False
    
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
        
        # Send POST request to API with timeout
        response = requests.post(
            READINGS_ENDPOINT,
            json=request_payload,
            headers=API_HEADERS,
            timeout=10
        )
        
        if response.status_code == 201:
            api_circuit_breaker.record_success()
            logger.info(f"Reading successfully sent to API: {response.json()}")
            return True
        else:
            api_circuit_breaker.record_failure()
            logger.error(f"API returned status {response.status_code}: {response.text}")
            # Fallback to backup database
            save_to_backup(device_id, ts_utc, json_data)
            return False
            
    except requests.exceptions.Timeout:
        api_circuit_breaker.record_failure()
        logger.error(f"API request timeout - failed to send reading: {READINGS_ENDPOINT}")
        save_to_backup(device_id, ts_utc, json_data)
        return False
    except requests.exceptions.ConnectionError as e:
        api_circuit_breaker.record_failure()
        logger.error(f"API connection error: {e}")
        save_to_backup(device_id, ts_utc, json_data)
        return False
    except requests.exceptions.RequestException as e:
        api_circuit_breaker.record_failure()
        logger.error(f"Failed to send reading to API: {e}")
        # Fallback to backup database
        save_to_backup(device_id, ts_utc, json_data)
        return False
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON payload: {e}")
        return False
    except Exception as e:
        api_circuit_breaker.record_failure()
        logger.error(f"Unexpected error sending to API: {e}")
        # Fallback to backup database
        save_to_backup(device_id, ts_utc, json_data)
        return False


def sync_backup_to_api():
    """Periodically sync unsynced records from local backup to API using bulk upload"""
    while True:
        db = None
        try:
            # Skip if circuit breaker is open
            if not api_circuit_breaker.is_available():
                logger.debug("Circuit breaker is open - skipping backup sync")
                time.sleep(5)
                continue
            
            db = LocalSessionLocal()
            
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
                        
                        # Send batch to API with timeout
                        bulk_payload = {"readings": batch_readings}
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
                                api_circuit_breaker.record_success()
                                
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
                                api_circuit_breaker.record_failure()
                                logger.warning(f"Failed to sync batch: API returned {response.status_code} - {response.text}")
                                break  # Stop trying other batches if API is having issues
                        
                        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                            api_circuit_breaker.record_failure()
                            logger.error(f"Failed to sync batch (timeout/connection error): {e}")
                            break  # Stop trying other batches
                        except requests.exceptions.RequestException as e:
                            api_circuit_breaker.record_failure()
                            logger.error(f"Failed to sync batch (request error): {e}")
                            break  # Stop trying other batches
                            
                    except Exception as e:
                        logger.error(f"Failed to prepare batch: {e}", exc_info=True)
                        break
                
                if total_synced > 0:
                    logger.info(f"Successfully synced {total_synced} total records to API")
            
        except SQLAlchemyError as e:
            logger.error(f"Backup sync database error: {e}")
            if db:
                try:
                    db.rollback()
                except:
                    pass
        except Exception as e:
            logger.error(f"Unexpected error in backup sync: {e}", exc_info=True)
        finally:
            # Safely close database session with timeout protection
            if db:
                try:
                    db.close()
                except Exception as e:
                    logger.warning(f"Error closing database session: {e}")
        
        # Wait before next sync attempt
        time.sleep(5)


