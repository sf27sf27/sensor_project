# Sensor Project

A Raspberry Pi-based sensor monitoring system that reads sensor data (BME280, CPU temperature, disk space) and stores it in a PostgreSQL database with API sync capabilities.

## Features

- **Multi-sensor support**: BME280 (temperature, humidity, pressure), CPU temperature, disk space monitoring
- **FastAPI REST API**: Lightweight API for sensor data storage and retrieval
- **PostgreSQL database**: Local database with cloud sync via API
- **Continuous monitoring**: Background sensor reading with configurable intervals
- **Resilient data handling**: Local buffering with automatic sync to remote API
- **Disk management**: Automatic data cleanup when storage limits reached

## Project Structure

```
sensor_project/
├── api/                  # FastAPI application
│   ├── main.py          # FastAPI routes and endpoints
│   └── models.py        # SQLAlchemy ORM models
├── sensors/             # Sensor reading modules
│   ├── __init__.py
│   ├── bme280.py        # BME280 sensor (I2C, temp/humidity/pressure)
│   ├── cpu_temp.py      # CPU temperature (vcgencmd for Raspberry Pi)
│   └── disk_space.py    # Disk space monitoring
├── docs/                # Documentation
│   ├── ARCHITECTURE.md  # System architecture
│   └── SETUP.md         # Setup guide
├── logs/                # Application logs
├── read_sensors.py      # Main sensor reading script with sync
├── run_api.py           # API server launcher script
├── test_api_connection.py
├── requirements.txt     # Python dependencies
├── pyproject.toml       # Project configuration
└── README.md
```

## Setup

### Prerequisites

- Python 3.9+
- PostgreSQL (required for local data storage)
- Raspberry Pi with I2C enabled (for BME280 sensor)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/sf27sf27/sensor_project.git
cd sensor_project
```

2. **Create virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**

Create a `.env` file in the project root:
```env
# Remote API settings (for cloud sync)
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=your-rds-endpoint.amazonaws.com
DB_NAME=your_db_name
DB_PORT=5432

# API server settings
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=False

# Optional: Override default API endpoint for sensor sync
API_SERVER=your-api-domain.com
```

5. **Set up local PostgreSQL database**
```bash
# Create database and user
sudo -u postgres psql
CREATE DATABASE sensors;
CREATE USER sensor_user WITH PASSWORD 'strongpassword';
GRANT ALL PRIVILEGES ON DATABASE sensors TO sensor_user;

# Create schema and table
\c sensors
CREATE SCHEMA sensor_project;
CREATE TABLE sensor_project.readings (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR NOT NULL,
    ts_utc TIMESTAMP WITH TIME ZONE NOT NULL,
    ts_local TIMESTAMP WITH TIME ZONE NOT NULL,
    payload JSONB NOT NULL,
    is_synced BOOLEAN DEFAULT FALSE
);
```

## Usage

### Start the Sensor Reader

The main script that continuously reads sensors and stores data:

```bash
python read_sensors.py
```

This will:
- Read all sensors every 60 seconds
- Store readings in local PostgreSQL database
- Attempt to sync with remote API when available
- Manage local disk space automatically

### Start the API Server (Optional)

To run the API server locally:

```bash
python run_api.py
```

Or directly with uvicorn:
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### Access API Documentation

When the API server is running:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### Readings
- `POST /readings` - Create a single sensor reading
- `POST /readings/bulk` - Bulk create readings (for sync operations)
- `GET /readings?start_date=...&end_date=...` - Fetch readings in date range (format: YYYY-MM-DD HH:MM:SS)
- `GET /readings/latest` - Get the most recent reading

## Sensor Data Format

Each reading includes:
- **device_id**: Hostname of the device
- **ts_utc**: UTC timestamp
- **ts_local**: Local timestamp
- **payload**: JSON object containing:
  - `bme280`: {temperature: {c, f}, pressure: {hpa}, humidity: {rh}}
  - `cpu_temp`: {c, f}
  - `disk_space`: {total_mb, used_mb, free_mb}

## Configuration

### Local Database (read_sensors.py)
Update the `LOCAL_DB_CONFIG` in [read_sensors.py](read_sensors.py):
```python
LOCAL_DB_CONFIG = {
    "host": "localhost",
    "dbname": "sensors",
    "user": "sensor_user",
    "password": "strongpassword",
    "port": 5432
}
```

### Disk Management
Configure in [read_sensors.py](read_sensors.py):
- `DISK_USAGE_THRESHOLD`: 50% (triggers cleanup)
- `DISK_CLEANUP_CHECK_INTERVAL`: 300 seconds
- `DELETE_STRATEGY`: "stratified" (evenly distributed deletion)

### Sync Settings
- `BULK_SYNC_BATCH_SIZE`: 360 records per batch
- `API_SERVER`: Override with environment variable

## Troubleshooting

### I2C Device Not Found
Enable I2C on Raspberry Pi:
```bash
sudo raspi-config
# Navigate to: Interface Options > I2C > Enable
```

Verify I2C devices:
```bash
sudo i2cdetect -y 1
```

### CPU Temperature Not Reading
The `vcgencmd` command only works on Raspberry Pi. On other systems, this sensor will return an error.

### Database Connection Failed
Check PostgreSQL is running:
```bash
sudo systemctl status postgresql
```

Verify connection parameters in your `.env` file or `LOCAL_DB_CONFIG`.

### Port Already in Use
Change the API port:
```bash
python run_api.py  # Uses API_PORT from .env
# or
uvicorn api.main:app --port 8001
```

### Module Not Found Errors
Ensure virtual environment is activated:
```bash
source venv/bin/activate
```

## System Service (Optional)

Run as a systemd service on Raspberry Pi:

```bash
# Copy service file
sudo cp sensor-api.service /etc/systemd/system/

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable sensor-api
sudo systemctl start sensor-api

# Check status
sudo systemctl status sensor-api
```

## Development

### Project Dependencies
- FastAPI: Web framework for API
- SQLAlchemy: ORM for database
- psycopg2-binary: PostgreSQL adapter
- adafruit-blinka & adafruit-circuitpython-bme280: BME280 sensor driver
- uvicorn: ASGI server
- gunicorn: Production WSGI server
- python-dotenv: Environment variable management

## License

MIT License

## Author

Sydney Watson - https://github.com/sf27sf27
