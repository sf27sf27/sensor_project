"""
Background monitoring threads for system health and database connectivity.
Uses SQLAlchemy for all database operations.
"""
import time
from sqlalchemy.sql import text

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
from lib.server.models import local_engine


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
    """Monitor database connection health and attempt reconnection if needed"""
    while True:
        try:
            # Test the database connection by creating a session and executing a simple query
            from lib.server.models import LocalSessionLocal
            db = LocalSessionLocal()
            try:
                db.execute(text("SELECT 1"))
                # Silently succeed; only log warnings if there's an issue
            except Exception as e:
                logger.warning(f"Database connection health check failed: {e}")
                # Attempt to reinitialize the connection pool
                if not initialize_connection_pool():
                    logger.error("Failed to reinitialize database connection pool")
            finally:
                db.close()
                    
        except Exception as e:
            logger.error(f"Connection pool monitor error: {e}", exc_info=True)
        
        time.sleep(30)  # Check every 30 seconds

