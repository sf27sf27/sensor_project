"""
Main orchestration script for the sensor reading system.
Coordinates sensor reads, API communication, and background monitoring threads.
Includes circuit breaker, backpressure, and watchdog integration.
"""
import time
import json
import socket
import threading
from datetime import datetime, timezone

from lib.config import (
    logger,
    READINGS_ENDPOINT,
    DISK_USAGE_THRESHOLD,
)
from lib.database import (
    initialize_connection_pool,
)
from lib.api_client import (
    check_api_health,
    insert_reading,
    sync_backup_to_api,
    api_circuit_breaker,
)
from lib.monitors import (
    disk_space_monitor,
    connection_pool_monitor,
)
from lib.watchdog import watchdog
from sensors.disk_space import read as read_disk_space
from sensors.cpu_temp import read as read_cpu_temp
from sensors.bme280 import read as read_bme280
from concurrent.futures import ThreadPoolExecutor, as_completed


def read_all_sensors():
    """
    Read all sensors in parallel using ThreadPoolExecutor.
    Returns a dict with sensor data or error messages.
    """
    sensor_data = {}
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        # Submit all sensor read tasks
        futures = {
            executor.submit(read_disk_space): 'disk_space',
            executor.submit(read_cpu_temp): 'cpu_temp',
            executor.submit(read_bme280): 'bme280'
        }
        
        # Collect results as they complete
        for future in as_completed(futures):
            sensor_name = futures[future]
            try:
                sensor_data[sensor_name] = future.result()
            except Exception as e:
                sensor_data[sensor_name] = {"error": str(e)}
                logger.error(f"{sensor_name} read failed: {e}")
    
    return sensor_data


def validate_startup():
    """Validate system readiness before starting main loop"""
    # Database is already validated during initialize_connection_pool()
    # No additional verification needed - SQLAlchemy pool is ready
    logger.info("Database connectivity verified")
    
    # Check API health (non-fatal)
    if not check_api_health():
        logger.error("API server is not reachable. Please check connectivity.")
        logger.info("Make sure to set API_SERVER environment variable if API is on different host")
        logger.info("Example: export API_SERVER=192.168.1.100:8000")
    
    return True


def start_background_threads():
    """Start all background monitoring threads"""
    # Start the connection pool monitor thread as a daemon
    pool_monitor_thread = threading.Thread(target=connection_pool_monitor, daemon=True)
    pool_monitor_thread.start()
    logger.info("Started connection pool monitor thread")
    
    # Start the backup sync thread as a daemon
    sync_thread = threading.Thread(target=sync_backup_to_api, daemon=True)
    sync_thread.start()
    logger.info("Started backup sync thread")
    
    # Start the disk space monitor thread as a daemon
    disk_monitor_thread = threading.Thread(target=disk_space_monitor, daemon=True)
    disk_monitor_thread.start()
    logger.info("Started disk space monitor thread")


def main_loop():
    """Main sensor reading loop"""
    device_id = socket.gethostname()
    api_failure_count = 0
    
    while True:
        try:
            # Notify systemd watchdog that we're alive
            watchdog.notify()
            
            logger.info("Starting sensor read cycle")
            ts_utc = datetime.now(timezone.utc)
            
            # Backpressure: slow down readings if API is unhealthy
            if not api_circuit_breaker.is_available():
                api_failure_count += 1
                logger.warning(f"API unavailable - entering backpressure mode (count={api_failure_count})")
                # Increase sleep time to reduce load: 10s -> 30s -> 60s
                backpressure_sleep = min(10 + (api_failure_count * 20), 60)
                logger.info(f"Backpressure: sleeping {backpressure_sleep}s before next read")
                time.sleep(backpressure_sleep)
                continue
            else:
                api_failure_count = 0
            
            # Read all sensors in parallel
            sensor_data = read_all_sensors()
            
            pi_data = {
                "disk_space": sensor_data['disk_space'],
                "cpu_temp": sensor_data['cpu_temp'],
            }
            data = {
                "rasp_pi": pi_data,
                "bme280": sensor_data['bme280']
            }

            json_data = json.dumps(data)

            # Send to API
            result = insert_reading(device_id, ts_utc, data)
            logger.info(f"Insert result: {result}")

            time.sleep(10)  # Read sensors every 10 seconds
        except Exception as e:
            logger.error(f"Main loop error: {e}", exc_info=True)
            time.sleep(10)


if __name__ == "__main__":
    logger.info(f"Starting sensor reader, API endpoint: {READINGS_ENDPOINT}")
    logger.info(f"Disk usage threshold: {DISK_USAGE_THRESHOLD}%")
    
    # Start systemd watchdog
    watchdog.start()
    
    # Initialize connection pool
    initialize_connection_pool()
    
    # Validate system readiness
    if not validate_startup():
        watchdog.stop()
        exit(1)
    
    # Start background monitoring threads
    start_background_threads()
    
    # Run main sensor reading loop
    try:
        main_loop()
    except KeyboardInterrupt:
        logger.info("Sensor reader shut down gracefully")
        watchdog.stop()
        exit(0)
    finally:
        watchdog.stop()
