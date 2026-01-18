# Sensor Project

A distributed climate monitoring system using Raspberry Pi devices with BME280 sensors. Deploy sensors anywhere with WiFi to collect temperature, humidity, and pressure readings into a centralized cloud database—then visualize the data from anywhere via web applications.

## Overview

This project enables whole-home (or multi-location) environmental monitoring with a resilient, offline-first architecture. Each Raspberry Pi sensor node operates independently and syncs to a shared cloud database when connectivity is available.

### Use Cases

- 🏠 Monitor climate conditions across multiple rooms or buildings
- 📊 Power dashboards and visualizations for personal or portfolio projects
- 🌡️ Track temperature, humidity, and barometric pressure trends over time
- 📱 Access your data from anywhere via web apps

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SENSOR NODES (Raspberry Pi)                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   Pi + BME  │  │   Pi + BME  │  │   Pi + BME  │  │   Pi + BME  │  ...   │
│  │  (Kitchen)  │  │  (Bedroom)  │  │  (Garage)   │  │  (Outside)  │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                │                │                │               │
│         │         Local PostgreSQL        │                │               │
│         │          (offline buffer)       │                │               │
│         └────────────────┼────────────────┴────────────────┘               │
│                          │                                                  │
│                    Write API (POST)                                         │
└──────────────────────────┼──────────────────────────────────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │   ☁️  Cloud Database    │
              │      (PostgreSQL)      │
              │    Centralized Store   │
              └────────────┬───────────┘
                           │
                    Query API (GET)
                     (read-only)
                           │
                           ▼
              ┌────────────────────────┐
              │    🌐 Web Applications  │
              │   Dashboards, Charts,  │
              │   Portfolio Projects   │
              └────────────────────────┘
```

### Key Components

| Component | Description |
|-----------|-------------|
| **Sensor Nodes** | Raspberry Pi devices with BME280 sensors collecting climate data |
| **Write API** | Runs on each Pi; handles data upload to cloud database |
| **Query API** | Centralized server providing read-only access for web apps |
| **Cloud Database** | Shared PostgreSQL database (e.g., AWS RDS) storing all readings |
| **Local Database** | Per-device PostgreSQL for offline buffering when WiFi is unavailable |

### Offline Resilience

Each sensor node stores readings locally when the network is unavailable. Once WiFi reconnects, unsynced records are automatically bulk-uploaded to the cloud database. This ensures **no data loss** even during extended outages.

## Features

- **BME280 Environmental Sensing**: Temperature (°C/°F), humidity (% RH), and barometric pressure (hPa)
- **System Monitoring**: CPU temperature and disk space for device health tracking
- **Offline-First Design**: Local PostgreSQL buffer with automatic cloud sync
- **Dual API Architecture**: Write API on sensors, read-only Query API for applications
- **Automatic Disk Management**: Intelligent cleanup when storage limits are reached
- **Systemd Integration**: Run as background services for hands-off operation

## Project Structure

```
sensor_project/
├── main.py                    # Main sensor reading loop with sync
├── api_server_write.py        # Write API launcher (runs on sensor nodes)
├── api_server_query.py        # Query API launcher (runs on central server)
├── lib/
│   ├── api_client.py          # HTTP client for cloud sync
│   ├── config.py              # Shared configuration and logging
│   ├── database.py            # Local database utilities
│   ├── monitors.py            # Background monitoring tasks
│   └── server/
│       ├── models.py          # SQLAlchemy ORM models & Pydantic schemas
│       ├── query.py           # Query API routes (read-only)
│       └── writer.py          # Write API routes (POST endpoints)
├── sensors/
│   ├── bme280.py              # BME280 I2C driver
│   ├── cpu_temp.py            # Raspberry Pi CPU temperature
│   └── disk_space.py          # Disk usage monitoring
├── logs/                      # Application logs
├── sensor-main.service        # Systemd service for sensor reader
├── sensor-api-write.service   # Systemd service for write API
├── sensor-api-query.service   # Systemd service for query API
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Setup

### Prerequisites

- Python 3.9+
- PostgreSQL (local instance for offline buffering)
- Raspberry Pi with I2C enabled (for BME280 sensor)
- Cloud PostgreSQL database (e.g., AWS RDS) for centralized storage

### Hardware Setup

1. **Connect BME280 to Raspberry Pi via I2C:**
   - VCC → 3.3V (Pin 1)
   - GND → Ground (Pin 6)
   - SDA → GPIO 2 (Pin 3)
   - SCL → GPIO 3 (Pin 5)

2. **Enable I2C on Raspberry Pi:**
   ```bash
   sudo raspi-config
   # Navigate to: Interface Options > I2C > Enable
   ```

3. **Verify sensor connection:**
   ```bash
   sudo i2cdetect -y 1
   # Should show device at address 0x76 or 0x77
   ```

### Software Installation

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
   # Cloud Database (centralized storage)
   DB_USER=your_cloud_db_user
   DB_PASSWORD=your_cloud_db_password
   DB_HOST=your-rds-endpoint.amazonaws.com
   DB_NAME=sensors
   DB_PORT=5432

   # Local Database (offline buffer on each Pi)
   LOCAL_DB_HOST=127.0.0.1
   LOCAL_DB_USER=sensor_user
   LOCAL_DB_PASSWORD=strongpassword
   LOCAL_DB_NAME=sensors
   LOCAL_DB_PORT=5432

   # API Configuration
   API_HOST=0.0.0.0
   API_PORT=8000
   API_KEY=your_secret_api_key

   # Cloud API endpoint (for sensor sync)
   API_SERVER=your-api-domain.com:8000
   ```

5. **Set up local PostgreSQL database (on each Raspberry Pi)**
   ```bash
   sudo -u postgres psql
   ```
   ```sql
   CREATE DATABASE sensors;
   CREATE USER sensor_user WITH PASSWORD 'strongpassword';
   GRANT ALL PRIVILEGES ON DATABASE sensors TO sensor_user;
   \c sensors
   CREATE TABLE readings (
       id SERIAL PRIMARY KEY,
       device_id VARCHAR NOT NULL,
       ts_utc TIMESTAMP WITH TIME ZONE NOT NULL,
       ts_local TIMESTAMP WITH TIME ZONE NOT NULL,
       payload JSONB NOT NULL,
       is_synced BOOLEAN DEFAULT FALSE
   );
   ```

## Usage

### Running on Sensor Nodes (Raspberry Pi)

Each Raspberry Pi runs two processes:

1. **Sensor Reader** — Collects data and stores locally
   ```bash
   python main.py
   ```

2. **Write API** — Handles sync to cloud database
   ```bash
   python api_server_write.py
   ```

The sensor reader will:
- Read BME280, CPU temperature, and disk space every 60 seconds
- Store readings in the local PostgreSQL database
- Automatically sync to the cloud when WiFi is available
- Buffer data locally during network outages

### Running the Query API (Central Server)

On your server (or locally for development):

```bash
python api_server_query.py
```

This provides **read-only** access for web applications:
- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc

### Running as System Services

For production deployment, install the systemd services:

```bash
# Copy service files
sudo cp sensor-main.service /etc/systemd/system/
sudo cp sensor-api-write.service /etc/systemd/system/
sudo cp sensor-api-query.service /etc/systemd/system/  # Only on query server

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable sensor-main sensor-api-write
sudo systemctl start sensor-main sensor-api-write

# Check status
sudo systemctl status sensor-main
sudo systemctl status sensor-api-write
```

## API Reference

### Write API (runs on sensor nodes)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/readings` | POST | Submit a single sensor reading |
| `/readings/bulk` | POST | Bulk upload readings (for sync after offline period) |
| `/health` | GET | Health check endpoint |

### Query API (runs on central server, read-only)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/readings` | GET | Fetch readings with optional filters |
| `/readings/latest` | GET | Get most recent reading per device |
| `/readings/range` | GET | Query readings within a date range |
| `/devices` | GET | List all registered sensor devices |
| `/health` | GET | Health check endpoint |

**Query Parameters:**
- `start_date` / `end_date`: Filter by timestamp (format: `YYYY-MM-DD HH:MM:SS`)
- `device_id`: Filter by specific sensor node
- `limit` / `offset`: Pagination

## Sensor Data Format

Each reading includes:
- **device_id**: Hostname of the Raspberry Pi (identifies sensor location)
- **ts_utc**: UTC timestamp
- **ts_local**: Local timestamp
- **payload**: JSON object containing:
  ```json
  {
    "bme280": {
      "temperature": {"c": 22.5, "f": 72.5},
      "pressure": {"hpa": 1013.25},
      "humidity": {"rh": 45.2}
    },
    "cpu_temp": {"c": 48.3, "f": 118.9},
    "disk_space": {"total_mb": 29000, "used_mb": 8500, "free_mb": 20500}
  }
  ```

## Configuration

### Disk Management

The system automatically manages disk space on sensor nodes:

| Setting | Default | Description |
|---------|---------|-------------|
| `DISK_USAGE_THRESHOLD` | 50% | Triggers cleanup when exceeded |
| `DISK_CLEANUP_CHECK_INTERVAL` | 300s | How often to check disk usage |
| `DELETE_STRATEGY` | stratified | Evenly distributed deletion to preserve data trends |

### Sync Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `BULK_SYNC_BATCH_SIZE` | 360 | Records per sync batch |
| `SYNC_INTERVAL` | 60s | How often to attempt cloud sync |
| `API_SERVER` | (env var) | Cloud API endpoint for sync |

## Troubleshooting

### Sensor Issues

**I2C Device Not Found**
```bash
# Enable I2C
sudo raspi-config
# Interface Options > I2C > Enable

# Verify device is detected
sudo i2cdetect -y 1
```

**CPU Temperature Not Reading**
- The `vcgencmd` command only works on Raspberry Pi hardware
- On other systems, this sensor will return an error (this is expected)

### Database Issues

**Connection Failed**
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Verify connection
psql -h localhost -U sensor_user -d sensors
```

**Cloud Sync Failing**
- Verify `API_SERVER` environment variable is set correctly
- Check network connectivity: `ping your-api-domain.com`
- Review logs: `journalctl -u sensor-api-write -f`

### Service Issues

**Module Not Found**
```bash
# Ensure virtual environment path is correct in service file
# Edit: /etc/systemd/system/sensor-main.service
ExecStart=/home/pi/sensor_project/venv/bin/python main.py
```

**Port Already in Use**
```bash
# Find process using port
sudo lsof -i :8000

# Use different port
API_PORT=8080 python api_server_write.py
```

## Dependencies

| Package | Purpose |
|---------|---------|
| fastapi | REST API framework |
| uvicorn | ASGI server for FastAPI |
| sqlalchemy | Database ORM |
| psycopg2-binary | PostgreSQL driver |
| pydantic | Data validation |
| requests | HTTP client for cloud sync |
| adafruit-blinka | Raspberry Pi GPIO/I2C support |
| adafruit-circuitpython-bme280 | BME280 sensor driver |
| gunicorn | Production WSGI server |
| python-dotenv | Environment variable management |

## License

MIT License

## Author

Sydney Watson — [github.com/sf27sf27](https://github.com/sf27sf27)
