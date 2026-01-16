#!/bin/bash
# Recovery and monitoring script for sensor services on Raspberry Pi
# Run this as part of cron to monitor and recover from failures

SERVICE_API="sensor-api-write"
SERVICE_MAIN="sensor-main"
JOURNAL_DIR="/var/log/journal"
LOG_FILE="/tmp/sensor_recovery.log"
RECOVERY_THRESHOLD=3  # Max consecutive failures before recovery

log_message() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

check_service_status() {
    local service=$1
    if systemctl is-active --quiet "$service"; then
        return 0  # Service is running
    else
        return 1  # Service is not running
    fi
}

get_service_state() {
    local service=$1
    systemctl show "$service" -p StateChangeTimestampMonotonic --no-pager | cut -d= -f2
}

check_ssh_responsive() {
    # Quick check if SSH is responding
    nc -zw1 localhost 22 > /dev/null 2>&1
    return $?
}

restart_service() {
    local service=$1
    log_message "Attempting to restart $service..."
    
    if sudo systemctl restart "$service"; then
        log_message "Successfully restarted $service"
        return 0
    else
        log_message "Failed to restart $service"
        return 1
    fi
}

recover_from_deadlock() {
    log_message "CRITICAL: System appears deadlocked - attempting emergency recovery"
    
    # Try to kill stuck processes
    log_message "Killing hung sensor processes..."
    sudo pkill -9 -f "python.*main.py" 2>/dev/null
    sudo pkill -9 -f "python.*api_server" 2>/dev/null
    
    sleep 2
    
    # Restart services
    log_message "Restarting services after cleanup..."
    sudo systemctl restart "$SERVICE_API"
    sleep 5
    sudo systemctl restart "$SERVICE_MAIN"
    
    log_message "Emergency recovery attempted"
}

check_circuit_breaker() {
    # Check if too many API failures are happening
    local api_error_count=$(journalctl -u "$SERVICE_MAIN" -n 100 --no-pager | grep -c "circuit breaker" || true)
    
    if [ "$api_error_count" -gt 10 ]; then
        log_message "WARNING: Circuit breaker triggered many times - possible API server issue"
        return 1
    fi
    return 0
}

# Main monitoring logic
log_message "=== Sensor Service Monitor ==="

# Check if SSH is responsive
if ! check_ssh_responsive; then
    log_message "ERROR: SSH not responding - system may be deadlocked"
    recover_from_deadlock
    exit 1
fi

# Check both services
api_ok=true
main_ok=true

if ! check_service_status "$SERVICE_API"; then
    log_message "WARNING: $SERVICE_API is not running"
    api_ok=false
    if ! restart_service "$SERVICE_API"; then
        log_message "ERROR: Failed to restart $SERVICE_API"
    fi
    sleep 5
fi

if ! check_service_status "$SERVICE_MAIN"; then
    log_message "WARNING: $SERVICE_MAIN is not running"
    main_ok=false
    if ! restart_service "$SERVICE_MAIN"; then
        log_message "ERROR: Failed to restart $SERVICE_MAIN"
    fi
fi

# Check for circuit breaker issues
if ! check_circuit_breaker; then
    log_message "WARNING: Circuit breaker activity detected - check API server connectivity"
fi

# Log status
if check_service_status "$SERVICE_API" && check_service_status "$SERVICE_MAIN"; then
    log_message "Status: OK - All services running"
else
    log_message "Status: DEGRADED - Some services not running"
fi

log_message "=== Monitor cycle complete ==="
