# Sensor Project Setup Guide

Complete setup instructions for the Raspberry Pi sensor monitoring system with cloud sync.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Hardware Requirements](#hardware-requirements)
3. [Raspberry Pi Setup](#raspberry-pi-setup)
4. [Cloud/Remote API Setup](#cloud-remote-api-setup)
5. [Configuration](#configuration)
6. [Running the System](#running-the-system)
7. [Verification](#verification)
8. [Troubleshooting](#troubleshooting)

## Quick Start

**On Raspberry Pi** (sensor reader):
```bash
# Clone and setup
git clone https://github.com/sf27sf27/sensor_project.git
cd sensor_project
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Setup local database (see PostgreSQL setup below)
# Configure .env file
# Run sensor reader
python read_sensors.py
```

**On Cloud Server** (API):
```bash
# Same clone and setup
# Configure .env with cloud database credentials
# Run API server
python run_api.py
```

## Hardware Requirements

### Raspberry Pi Setup
- **Raspberry Pi**: 3B+ or newer (tested on Pi 4)
- **BME280 Sensor**: I2C environmental sensor
- **MicroSD Card**: 16GB+ (32GB recommended for local buffering)
- **Power Supply**: Official Raspberry Pi power adapter
- **Network**: WiFi or Ethernet connection

### BME280 Wiring
```
BME280 → Raspberry Pi
VCC    → 3.3V (Pin 1)
GND    → GND (Pin 6)
SCL    → SCL (Pin 5, GPIO 3)
SDA    → SDA (Pin 3, GPIO 2)
```

### Using PostgreSQL

1. **Install PostgreSQL**
   ```bash
   # macOS with Homebrew
   brew install postgresql
   
   # Ubuntu/Debian
   sudo apt-get install postgresql postgresql-contrib
   ```

2. **Create a database**
   ```bash
   createdb sensor_db
   ```

3. **Update `.env`**
   ```env
   DATABASE_URL=postgresql://username:password@localhost:5432/sensor_db
   ```

4. **Run migrations** (if applicable)
   ```bash
   python -m api.main  # or appropriate migration command
   ```

## Running the Application

### Start the API Server

```bash
# Development mode (with auto-reload)
uvicorn api.main:app --reload

# Production mode (using Gunicorn)
gunicorn -w 4 -k uvicorn.workers.UvicornWorker api.main:app
```

### Run Sensor Reader

```bash
## Raspberry Pi Setup

### 1. Enable I2C

```bash
sudo raspi-config
# Navigate to: Interface Options → I2C → Enable
sudo reboot
```

Verify I2C is working:
```bash
sudo i2cdetect -y 1
```

You should see the BME280 at address `0x77` (or `0x76`).

### 2. Install PostgreSQL (Local Database)

```bash
# Install PostgreSQL
sudo apt update
sudo apt install postgresql postgresql-contrib

# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user
sudo -u postgres psql

# In psql prompt:
CREATE DATABASE sensors;
CREATE USER sensor_user WITH PASSWORD 'strongpassword';
GRANT ALL PRIVILEGES ON DATABASE sensors TO sensor_user;
\q

# Connect to sensors database and create schema
sudo -u postgres psql -d sensors

# In psql prompt:
CREATE SCHEMA sensor_project;

CREATE TABLE sensor_project.readings (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR NOT NULL,
    ts_utc TIMESTAMP WITH TIME ZONE NOT NULL,
    ts_local TIMESTAMP WITH TIME ZONE NOT NULL,
    payload JSONB NOT NULL,
    is_synced BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_is_synced ON sensor_project.readings(is_synced);
CREATE INDEX idx_ts_local ON sensor_project.readings(ts_local);

GRANT ALL PRIVILEGES ON SCHEMA sensor_project TO sensor_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA sensor_project TO sensor_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA sensor_project TO sensor_user;
\q
```

### 3. Install Python Dependencies

```bash
cd /home/pi/sensor_project
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Configure Environment (Raspberry Pi)

Create `.env` file:
```env
# Remote API endpoint (your cloud server)
API_SERVER=your-api-domain.com

# Cloud database credentials (for API connection)
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=your-rds-endpoint.amazonaws.com
DB_NAME=your_db_name
DB_PORT=5432
```

**Note**: The `read_sensors.py` script uses hardcoded `LOCAL_DB_CONFIG` for the local database. To change local database credentials, edit [read_sensors.py](../read_sensors.py) lines 33-39.

## Cloud/Remote API Setup

### 1. Setup PostgreSQL (Cloud Database)

On AWS RDS, Google Cloud SQL, or your PostgreSQL server:

```sql
CREATE SCHEMA sensor_project;

CREATE TABLE sensor_project.readings (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR NOT NULL,
    ts_utc TIMESTAMP WITH TIME ZONE NOT NULL,
    ts_local TIMESTAMP WITH TIME ZONE NOT NULL,
    payload JSONB NOT NULL
);

CREATE INDEX idx_device_ts ON sensor_project.readings(device_id, ts_local);
CREATE INDEX idx_ts_local ON sensor_project.readings(ts_local);
```

### 2. Install Python Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment (Cloud Server)

Create `.env` file:
```env
# Cloud database connection
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=your-database-host
DB_NAME=your_db_name
DB_PORT=5432

# API server settings
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=False
```

## Configuration

### Sensor Reader Configuration

Edit [read_sensors.py](../read_sensors.py) to customize:

```python
# Local database (lines 33-39)
LOCAL_DB_CONFIG = {
    "host": "localhost",
    "dbname": "sensors",
    "user": "sensor_user",
    "password": "strongpassword",
    "port": 5432
}

# Sync settings (lines 58-62)
API_SERVER = os.getenv("API_SERVER", "localhost:8000")
BULK_SYNC_BATCH_SIZE = 360  # Records per batch

# Disk management (lines 64-66)
DISK_USAGE_THRESHOLD = 50  # Percentage
DISK_CLEANUP_CHECK_INTERVAL = 300  # Seconds
```

### BME280 I2C Address

If your BME280 uses address `0x76` instead of `0x77`, edit [sensors/bme280.py](../sensors/bme280.py):

```python
# Line 8: Change from 0x77 to 0x76
bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x76)
```

## Running the System

### Raspberry Pi (Sensor Reader)

**Development/Testing**:
```bash
source venv/bin/activate
python read_sensors.py
```

**Production (systemd service)**:
```bash
# Create service file
sudo nano /etc/systemd/system/sensor-reader.service
```

Add:
```ini
[Unit]
Description=Sensor Reader Service
After=network.target postgresql.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/sensor_project
Environment="PATH=/home/pi/sensor_project/venv/bin"
ExecStart=/home/pi/sensor_project/venv/bin/python read_sensors.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable sensor-reader
sudo systemctl start sensor-reader
sudo systemctl status sensor-reader
```

### Cloud Server (API)

**Development**:
```bash
source venv/bin/activate
python run_api.py
```

**Production (systemd service)**:
Use the included [sensor-api.service](../sensor-api.service) file:

```bash
# Edit the service file with your username
sudo nano sensor-api.service

# Copy to systemd
sudo cp sensor-api.service /etc/systemd/system/

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable sensor-api
sudo systemctl start sensor-api
sudo systemctl status sensor-api
```

## Verification

### Check Sensor Readings

On Raspberry Pi:
```bash
# Check local database
psql -U sensor_user -d sensors -c "SELECT COUNT(*) FROM sensor_project.readings;"

# View recent readings
psql -U sensor_user -d sensors -c "SELECT * FROM sensor_project.readings ORDER BY ts_local DESC LIMIT 5;"
```

### Check API

```bash
# Health check
curl http://your-api-server/docs

# Latest reading
curl "http://your-api-server/readings/latest"

# Date range query
curl "http://your-api-server/readings?start_date=2026-01-01%2000:00:00&end_date=2026-01-05%2023:59:59"
```

### Monitor Logs

**Raspberry Pi**:
```bash
# Sensor reader logs
tail -f logs/read_sensors.log

# System service logs
sudo journalctl -u sensor-reader -f
```

**Cloud Server**:
```bash
# API service logs
sudo journalctl -u sensor-api -f
```

## Troubleshooting

### I2C Device Not Found

**Problem**: BME280 sensor not detected

**Solution**:
```bash
# Check I2C devices
sudo i2cdetect -y 1

# Enable I2C
sudo raspi-config
# Interface Options → I2C → Enable → Reboot

# Verify wiring (VCC→3.3V, GND→GND, SCL→GPIO3, SDA→GPIO2)

# Check I2C address in code
python3 -c "import board, busio; i2c = busio.I2C(board.SCL, board.SDA); print(i2c.scan())"
```

### CPU Temperature Not Working

**Problem**: CPU temp sensor returns error

**Solution**:
- `vcgencmd` only works on Raspberry Pi
- On other systems, this sensor will return `{"error": "..."}` (expected behavior)
- Check if command works: `vcgencmd measure_temp`

### Database Connection Failed

**Problem**: `psycopg2.OperationalError` or connection refused

**Solution**:
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Verify credentials
psql -U sensor_user -d sensors -h localhost

# Check pg_hba.conf allows local connections
sudo nano /etc/postgresql/*/main/pg_hba.conf
# Ensure line exists: local   all   all   md5

# Restart PostgreSQL
sudo systemctl restart postgresql
```

### API Server Not Reachable

**Problem**: Sensor reader can't connect to remote API

**Solution**:
```bash
# Test API from Raspberry Pi
curl http://your-api-server/docs

# Check API_SERVER environment variable
echo $API_SERVER

# Verify .env file has correct endpoint
cat .env | grep API_SERVER

# Check firewall on cloud server allows port 8000
```

### Disk Space Full

**Problem**: Local database disk usage at 100%

**Solution**:
- The system should auto-cleanup at 50% (check logs)
- Manually run cleanup query or lower `DISK_USAGE_THRESHOLD`
- Check sync is working (unsynced records accumulate)
- Verify `is_synced` flag is being set correctly

### Module Not Found Errors

**Problem**: `ModuleNotFoundError: No module named 'fastapi'`

**Solution**:
```bash
# Activate virtual environment
source venv/bin/activate

# Verify Python is from venv
which python

# Reinstall dependencies
pip install -r requirements.txt
```

### Port Already in Use

**Problem**: `Address already in use`

**Solution**:
```bash
# Find process using port
sudo lsof -i :8000

# Kill process
sudo kill -9 <PID>

# Or use different port
python run_api.py  # Edit API_PORT in .env
```

### Sync Not Working

**Problem**: Readings stored locally but not syncing to cloud

**Solution**:
```bash
# Check logs for sync errors
tail -f logs/read_sensors.log | grep -i sync

# Verify API endpoint
curl -X POST http://your-api-server/readings/bulk \
  -H "Content-Type: application/json" \
  -d '{"readings": []}'

# Check unsynced count
psql -U sensor_user -d sensors -c \
  "SELECT COUNT(*) FROM sensor_project.readings WHERE is_synced = false;"
```

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/)
- [Adafruit BME280 Guide](https://learn.adafruit.com/adafruit-bme280-humidity-barometric-pressure-temperature-sensor-breakout/)
- [Raspberry Pi I2C Setup](https://learn.adafruit.com/adafruits-raspberry-pi-lesson-4-gpio-setup/configuring-i2c)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

## Support

For issues and questions:
- Review logs: `logs/read_sensors.log`
- Check system logs: `sudo journalctl -u sensor-reader -n 100`
- GitHub Issues: https://github.com/sf27sf27/sensor_project/issues
