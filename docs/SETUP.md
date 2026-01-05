# Sensor Project Documentation

Welcome to the Sensor Project documentation! This guide will help you get started with the sensor monitoring system.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Running the Application](#running-the-application)
5. [API Reference](#api-reference)
6. [Sensor Types](#sensor-types)
7. [Troubleshooting](#troubleshooting)

## Quick Start

Get up and running in 5 minutes:

```bash
# Clone the repo
git clone https://github.com/sf27sf27/sensor_project.git
cd sensor_project

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the API
uvicorn api.main:app --reload
```

Visit http://localhost:8000/docs to see the interactive API documentation.

## Installation

### System Requirements

- **Python**: 3.9 or higher
- **OS**: macOS, Linux, or Windows
- **Optional**: PostgreSQL for data persistence

### Step-by-Step Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/sf27sf27/sensor_project.git
   cd sensor_project
   ```

2. **Create a Python virtual environment**
   ```bash
   # macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   
   # Windows
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Verify Python version** (should be 3.9+)
   ```bash
   python --version
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

5. **(Optional) Install development tools**
   ```bash
   pip install -e ".[dev]"
   ```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Database (optional - defaults to SQLite if not set)
DATABASE_URL=postgresql://username:password@localhost:5432/sensor_db

# API Settings
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=true

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/app.log

# Sensor Readings
SENSOR_READ_INTERVAL=60  # seconds
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
# Read sensors once
python read_sensors.py

# Run in background (macOS/Linux)
nohup python read_sensors.py > logs/sensors.log 2>&1 &
```

### Deploy as Systemd Services (Production)

For production deployments on Linux, use systemd to manage both the sensor reader and API server as background services.

#### API Service (`sensor-api.service`)

The API server can be deployed as a systemd service to run automatically on system startup and restart on failure.

**Setup on remote device:**

1. Edit `sensor-api.service` and replace `<your-username>` with your actual username:
   ```bash
   # Replace <your-username> with the actual user (e.g., sf27)
   sed -i 's/<your-username>/your_actual_username/g' sensor-api.service
   ```

2. Copy the updated `sensor-api.service` to the systemd directory:
   ```bash
   sudo cp sensor-api.service /etc/systemd/system/
   ```

3. Reload systemd configuration:
   ```bash
   sudo systemctl daemon-reload
   ```

4. Enable and start the service:
   ```bash
   sudo systemctl enable sensor-api.service
   sudo systemctl start sensor-api.service
   ```

5. Verify the service is running:
   ```bash
   sudo systemctl status sensor-api.service
   ```

**Service Details:**
- Runs as the configured user (replace `<your-username>` in the service file)
- Working directory: `/home/<your-username>/sensor_project`
- Listens on `0.0.0.0:8000` (all interfaces)
- Auto-restarts on failure with 10-second delay
- Environment: `DEBUG=False` (disable reload in production)

**Useful Commands:**

```bash
# View recent logs
journalctl -u sensor-api.service -n 50

# Follow logs in real-time
journalctl -u sensor-api.service -f

# Stop the service
sudo systemctl stop sensor-api.service

# Restart the service
sudo systemctl restart sensor-api.service
```

**Sensor Reader Service:**

The remote device should already have `sensor-reader.service` running to submit sensor readings to the API. The reader calls `http://localhost:8000/readings` to POST data.

### Access the Application

- **API Docs (Swagger UI)**: http://localhost:8000/docs
- **Alternative Docs (ReDoc)**: http://localhost:8000/redoc
- **API Base URL**: http://localhost:8000

## API Reference

### Health Check

```http
GET /health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-04T12:00:00Z"
}
```

### Get All Sensors

```http
GET /sensors
```

Returns array of all sensor readings.

### Get Sensor by ID

```http
GET /sensors/{sensor_id}
```

Returns specific sensor data.

### Record Sensor Data

```http
POST /sensors
Content-Type: application/json

{
  "sensor_type": "bme280",
  "temperature": 23.5,
  "humidity": 45.2,
  "pressure": 1013.25
}
```

## Sensor Types

### 1. BME280 (Temperature, Humidity, Pressure)

**File**: `sensors/bme280.py`

Reads from Adafruit BME280 sensor via I2C.

```python
from sensors.bme280 import BME280Sensor

sensor = BME280Sensor()
data = sensor.read()
# Returns: {temperature, humidity, pressure}
```

### 2. CPU Temperature

**File**: `sensors/cpu_temp.py`

Reads system CPU temperature.

```python
from sensors.cpu_temp import CPUTempSensor

sensor = CPUTempSensor()
temp = sensor.read()  # Returns float (degrees Celsius)
```

### 3. Disk Space

**File**: `sensors/disk_space.py`

Monitors disk usage.

```python
from sensors.disk_space import DiskSpaceSensor

sensor = DiskSpaceSensor()
data = sensor.read()
# Returns: {total, used, free, percent}
```

## Troubleshooting

### Virtual Environment Issues

**Problem**: `ModuleNotFoundError` or `No module named 'fastapi'`

**Solution**:
```bash
# Make sure venv is activated
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate     # Windows

# Reinstall dependencies
pip install -r requirements.txt
```

### Port Already in Use

**Problem**: `Address already in use: ('0.0.0.0', 8000)`

**Solution**:
```bash
# Use a different port
uvicorn api.main:app --port 8001

# Or kill the process using port 8000
# macOS/Linux:
lsof -ti :8000 | xargs kill -9
# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Sensor Not Detected

**Problem**: `I2C device not found` or sensor read fails

**Solution**:
```bash
# Check I2C devices (Linux)
i2cdetect -y 1

# Enable I2C on Raspberry Pi
sudo raspi-config
# Interface Options → I2C → Enable

# Verify Adafruit board
python -c "import board; print(board.I2C())"
```

### Database Connection Error

**Problem**: `psycopg2.OperationalError: could not connect to server`

**Solution**:
```bash
# Check PostgreSQL is running
# macOS:
brew services list

# Linux:
sudo systemctl status postgresql

# Verify connection string in .env
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
```

### High Disk Space Usage

**Problem**: Repository or logs taking too much space

**Solution**:
```bash
# Clean up old logs
rm logs/*.log

# Clean up Python cache
find . -type d -name __pycache__ -exec rm -r {} +
find . -type f -name "*.pyc" -delete

# Check repo size
du -sh .
```

## Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Docs](https://docs.sqlalchemy.org/)
- [Adafruit BME280 Guide](https://learn.adafruit.com/adafruit-bme280-humidity-barometric-pressure-temperature-sensor-breakout/)
- [Uvicorn Documentation](https://www.uvicorn.org/)

## Support

For issues and questions:
- Check [GitHub Issues](https://github.com/sf27sf27/sensor_project/issues)
- Review logs in `logs/` directory
- Enable debug logging in `.env`: `LOG_LEVEL=DEBUG`
