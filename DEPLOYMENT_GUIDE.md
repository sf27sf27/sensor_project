# Sensor Project: Resilience & Recovery Guide

## Problem Summary

On 2026-01-15 at 16:09:35, your sensor system became completely unresponsive:
- HTTP timeout from `insert_reading()`: `Read timed out (timeout=10)`
- SSH became unreachable
- Physical power cycle was required to recover

### Root Cause

The **backup sync thread** (`sync_backup_to_api`) had a critical flaw:
1. When API server became unresponsive, the bulk upload request hung
2. Database session cleanup (`db.close()`) on hung connection didn't release resources
3. SQLAlchemy connection pool filled up with dead connections
4. New sensor readings couldn't get connections, blocking main thread
5. All daemon threads competed for limited resources
6. System resource exhaustion made SSH unreachable

## Solutions Implemented

### 1. **Circuit Breaker Pattern** (NEW)
- Tracks API failures and stops sending requests when API is unhealthy
- Prevents resource exhaustion from hanging requests
- Auto-recovery after timeout period

**File**: [lib/api_client.py](lib/api_client.py)
**Classes**: `CircuitBreakerState`, `APICircuitBreaker`

### 2. **Backpressure in Main Loop** (NEW)
- When API is unreachable, main loop slows down sensor readings
- Progressively increases sleep: 10s → 30s → 60s
- Reduces load on system during API outages

**File**: [main.py](main.py)
**Key Change**: `api_failure_count` and adaptive sleep in `main_loop()`

### 3. **Timeout on Database Operations** (CRITICAL FIX)
- All database sessions now explicitly close with error handling
- Network requests have specific timeout types (Timeout, ConnectionError)
- Prevents hanging on dead database connections

**File**: [lib/api_client.py](lib/api_client.py)
**Key Change**: `sync_backup_to_api()` with try/except/finally on `db.close()`

### 4. **Systemd Watchdog Integration** (NEW)
- Services notify systemd every 15 seconds they're alive
- If no notification for 30 seconds, systemd auto-restarts service
- Prevents zombie processes from running indefinitely

**Files**: 
- [lib/watchdog.py](lib/watchdog.py) - Watchdog implementation
- [sensor-main.service](sensor-main.service) - Updated with watchdog
- [sensor-api-write.service](sensor-api-write.service) - Updated with watchdog

### 5. **Resource Limits** (NEW)
- Memory limit: 256MB (API server), 512MB (main reader)
- CPU quota: 75% per service
- Max tasks: 100 (API), 200 (main)
- Prevents single service from consuming all system resources

**Files**: Updated systemd service files

### 6. **Safer Timeout Configuration**
- API requests: 10 second timeout
- Bulk uploads: 30 second timeout
- Explicit timeout exception handling (Timeout vs ConnectionError)

---

## Deployment Steps

### Step 1: Update Code on Raspberry Pi

```bash
# On your local machine, commit and push changes
git add -A
git commit -m "Add circuit breaker, backpressure, watchdog, and resource limits"
git push

# On Raspberry Pi
cd ~/sensor_project
git pull origin main
```

### Step 2: Reinstall Python Dependencies (if needed)

```bash
# Only if lib/watchdog.py introduces new imports (it doesn't currently)
source ~/sensor_project/venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Update Systemd Services

```bash
# Copy new service files
sudo cp ~/sensor_project/sensor-main.service /etc/systemd/system/
sudo cp ~/sensor_project/sensor-api-write.service /etc/systemd/system/

# Reload systemd configuration
sudo systemctl daemon-reload

# Restart services
sudo systemctl stop sensor-main sensor-api-write
sudo systemctl start sensor-api-write
sleep 5
sudo systemctl start sensor-main

# Verify status
sudo systemctl status sensor-main sensor-api-write
```

### Step 4: Verify Watchdog is Working

```bash
# Check watchdog is enabled
sudo systemctl show sensor-main -p WatchdogSec --no-pager
sudo systemctl show sensor-api-write -p WatchdogSec --no-pager

# Should show: WatchdogSec=30s
```

### Step 5: Set Up Monitoring (Optional but Recommended)

```bash
# Make recovery script executable
chmod +x ~/sensor_project/monitor_and_recover.sh

# Add to crontab to run every 5 minutes
# (Opens editor - add this line)
*/5 * * * * ~/sensor_project/monitor_and_recover.sh >> /tmp/sensor_recovery.log 2>&1

crontab -e
```

---

## How the New System Protects You

### Scenario 1: API Server Becomes Unresponsive
**OLD BEHAVIOR:**
- Main loop hangs on timeout for 10 seconds
- Backup sync thread hangs on 30-second timeout
- Connection pool fills up
- System becomes unresponsive

**NEW BEHAVIOR:**
- Circuit breaker detects 3 consecutive failures
- Circuit opens - future requests rejected immediately
- Main loop enters backpressure mode (slower readings)
- Backup sync thread skips API attempts
- System remains responsive
- SSH stays available
- After 60 seconds, circuit attempts recovery

### Scenario 2: Database Connection Leak
**OLD BEHAVIOR:**
- Connection pool could hang indefinitely
- Resources not released

**NEW BEHAVIOR:**
- Each database operation explicitly closes with error handling
- Timeouts applied at each step
- Failed operations logged with full traceback
- System automatically restarts if watchdog not pinged

### Scenario 3: Memory Leak or Runaway Process
**OLD BEHAVIOR:**
- Process could consume unlimited memory
- No automatic recovery

**NEW BEHAVIOR:**
- Each service limited to 256MB (API) or 512MB (main)
- OOM killer won't touch services (OOMScoreAdjust=-500)
- System protects SSH access
- If process exceeds limit, systemd auto-restarts
- Watchdog detects hang and restarts

### Scenario 4: Graceful API Recovery
**OLD BEHAVIOR:**
- Required manual restart or power cycle

**NEW BEHAVIOR:**
- Backpressure reduces load on API
- Circuit breaker periodically tests recovery
- Auto-restart within 60 seconds if healthy
- Normal operation resumes without intervention

---

## Monitoring & Debugging

### Check Service Status

```bash
# Real-time status
sudo systemctl status sensor-main -l
sudo systemctl status sensor-api-write -l

# View recent logs (last 50 lines)
sudo journalctl -u sensor-main -n 50 -f
sudo journalctl -u sensor-api-write -n 50 -f

# View specific error patterns
sudo journalctl -u sensor-main | grep "circuit breaker"
sudo journalctl -u sensor-main | grep "ERROR"
```

### Check Resource Usage

```bash
# Real-time monitoring
watch -n 1 'ps aux | grep python | grep -v grep'

# Check memory limits
systemctl show sensor-main -p MemoryLimit --no-pager
systemctl show sensor-api-write -p MemoryLimit --no-pager
```

### View Circuit Breaker State

The circuit breaker state is logged. Look for lines like:
```
WARNING - Circuit breaker OPEN - API failures exceeded threshold (3)
INFO - Circuit breaker HALF_OPEN - attempting recovery
```

### Run Recovery Script Manually

```bash
# Test the recovery script
~/sensor_project/monitor_and_recover.sh

# View recovery logs
tail -f /tmp/sensor_recovery.log
```

---

## Configuration Reference

### Systemd Watchdog
- **WatchdogSec**: 30 seconds - systemd will restart if service doesn't signal
- **TimeoutStopSec**: 5 seconds - time to shutdown before SIGKILL

### Circuit Breaker
- **Failure threshold**: 3 consecutive failures to open
- **Recovery timeout**: 60 seconds before attempting to close

### Resource Limits (Raspberry Pi)
- **API Memory**: 256MB
- **Main Memory**: 512MB
- **CPU Quota**: 75% (1 core on 4-core Pi)
- **Max Tasks**: 100/200 (prevents thread explosion)

---

## What to Monitor Going Forward

### Daily Checks
1. Verify both services running: `systemctl status sensor-*`
2. Check recent logs for errors: `journalctl -u sensor-main -n 20`
3. Look for circuit breaker warnings

### If Issues Recur
1. Check API server health - ensure it's responding
2. Review disk space on Raspberry Pi (disk full can cause hangs)
3. Check network connectivity
4. Review recent log entries for patterns

### Performance Baseline
- Main loop should read sensors every 10 seconds when API healthy
- API server should respond within 1 second
- Backup sync should process batches every 5 seconds when API available
- No "circuit breaker" warnings in normal operation

---

## Key Files Changed

1. **[lib/api_client.py](lib/api_client.py)** - Added circuit breaker, improved error handling
2. **[lib/watchdog.py](lib/watchdog.py)** - NEW - Systemd watchdog support
3. **[main.py](main.py)** - Added backpressure, watchdog integration
4. **[sensor-main.service](sensor-main.service)** - Added watchdog, resource limits
5. **[sensor-api-write.service](sensor-api-write.service)** - Added watchdog, resource limits
6. **[monitor_and_recover.sh](monitor_and_recover.sh)** - NEW - Optional monitoring script
7. **[INCIDENT_ANALYSIS.md](INCIDENT_ANALYSIS.md)** - NEW - Detailed incident breakdown

---

## Rollback Plan (if needed)

If issues arise, roll back using:

```bash
# Restore previous versions
git checkout HEAD~1 -- sensor-main.service sensor-api-write.service main.py lib/api_client.py

# Reload services
sudo systemctl daemon-reload
sudo systemctl restart sensor-main sensor-api-write
```

---

## Testing the Protections (Optional)

### Test Circuit Breaker
```bash
# Stop the API server
sudo systemctl stop sensor-api-write

# Watch main loop - should enter backpressure after 3 failures
sudo journalctl -u sensor-main -f

# After ~60 seconds, restart API server
sudo systemctl start sensor-api-write

# Watch recovery
```

### Test Watchdog (careful - will restart service)
```bash
# The watchdog pings every 15 seconds
# If you comment out watchdog.notify() in main loop, 
# service will restart after 30 seconds
# This is a good way to verify watchdog is working
```

---

## Questions & Support

If you encounter issues:
1. Check logs: `journalctl -u sensor-main -n 100`
2. Review this guide's "Monitoring & Debugging" section
3. Check [INCIDENT_ANALYSIS.md](INCIDENT_ANALYSIS.md) for technical details
4. Run recovery script: `~/sensor_project/monitor_and_recover.sh`

