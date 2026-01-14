"""
Background monitoring threads for system health and database connectivity.
"""
import time

from lib.config import (
    logger,
    DISK_CLEANUP_CHECK_INTERVAL,
    DISK_USAGE_THRESHOLD,
)
from lib.database import (
    initialize_connection_pool,
    get_disk_usage_percent,
    reduce_data_granularity,
)


def disk_space_monitor():
    """Periodically monitor disk usage and trigger cleanup if needed"""
    while True:
        try:
            disk_usage = get_disk_usage_percent()
            
            if disk_usage is not None:
                logger.info(f"Disk usage: {disk_usage:.1f}%")
                
                if disk_usage > DISK_USAGE_THRESHOLD:
                    logger.warning(f"Disk usage ({disk_usage:.1f}%) exceeds threshold ({DISK_USAGE_THRESHOLD}%)")
                    logger.info("Triggering data granularity reduction...")
                    reduce_data_granularity()
                    
                    # Re-check after cleanup
                    new_usage = get_disk_usage_percent()
                    if new_usage is not None:
                        logger.info(f"Disk usage after cleanup: {new_usage:.1f}%")
                        
        except Exception as e:
            logger.error(f"Disk space monitor error: {e}", exc_info=True)
        
        time.sleep(DISK_CLEANUP_CHECK_INTERVAL)


def connection_pool_monitor():
    """Monitor connection pool health and attempt reconnection if needed"""
    while True:
        try:
            # Import db_pool from module to check current state
            import lib.database as database
            
            if database.db_pool is None:
                logger.warning("Connection pool is None, attempting to reinitialize...")
                initialize_connection_pool()
            else:
                # Test the connection pool by getting and returning a connection
                try:
                    conn = database.db_pool.getconn()
                    database.db_pool.putconn(conn)
                    # Silently log only periodically to avoid spam
                except Exception as e:
                    logger.warning(f"Connection pool health check failed: {e}")
                    database.db_pool = None  # Reset to None to trigger reinitialization
                    
        except Exception as e:
            logger.error(f"Connection pool monitor error: {e}", exc_info=True)
        
        time.sleep(30)  # Check every 30 seconds
