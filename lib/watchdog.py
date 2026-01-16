"""
Watchdog timer support for systemd integration.
Periodically notifies systemd that the service is alive.
"""
import os
import signal
import threading
from lib.config import logger


class SystemdWatchdog:
    """
    Manages systemd watchdog notifications.
    Prevents systemd from restarting the service due to watchdog timeout.
    """
    def __init__(self):
        self.watchdog_usec = None
        self.enabled = False
        self.running = False
        self.ping_thread = None
        self._parse_watchdog()
    
    def _parse_watchdog(self):
        """
        Parse WATCHDOG_USEC from environment.
        systemd sets this if WatchdogSec is configured.
        """
        watchdog_usec = os.getenv('WATCHDOG_USEC')
        if not watchdog_usec:
            logger.info("Watchdog not enabled (WATCHDOG_USEC not set)")
            return
        
        try:
            self.watchdog_usec = int(watchdog_usec)
            # Convert microseconds to seconds and use 50% of timeout
            self.enabled = True
            logger.info(f"Watchdog enabled - will ping every {self.watchdog_usec / 2_000_000:.1f}s")
        except ValueError:
            logger.warning(f"Invalid WATCHDOG_USEC value: {watchdog_usec}")
    
    def start(self):
        """Start the watchdog ping thread"""
        if not self.enabled:
            return
        
        self.running = True
        self.ping_thread = threading.Thread(target=self._ping_loop, daemon=True)
        self.ping_thread.start()
        logger.info("Watchdog thread started")
    
    def stop(self):
        """Stop the watchdog ping thread"""
        self.running = False
        if self.ping_thread:
            self.ping_thread.join(timeout=2)
    
    def _ping_loop(self):
        """Send periodic SIGALRM to notify systemd"""
        if not self.enabled:
            return
        
        # Use 50% of watchdog timeout as the ping interval
        ping_interval = (self.watchdog_usec / 2_000_000)
        
        while self.running:
            try:
                # SIGALRM tells systemd we're alive
                os.kill(os.getpid(), signal.SIGALRM)
                logger.debug(f"Watchdog ping sent")
            except Exception as e:
                logger.warning(f"Failed to send watchdog ping: {e}")
            
            # Sleep for the interval
            threading.Event().wait(ping_interval)
    
    def notify(self):
        """Manually notify systemd that we're alive"""
        if not self.enabled:
            return
        
        try:
            os.kill(os.getpid(), signal.SIGALRM)
        except Exception as e:
            logger.debug(f"Failed to send watchdog notification: {e}")


# Global watchdog instance
watchdog = SystemdWatchdog()
