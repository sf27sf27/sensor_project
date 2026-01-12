# Sensor Project Architecture

## System Overview

This system consists of two main components:
1. **Sensor Reader** (`read_sensors.py`) - Runs on Raspberry Pi, reads sensors, stores locally, syncs to cloud
2. **API Server** (`api/main.py`) - Receives and stores sensor data in cloud PostgreSQL database

```
┌──────────────────────────────────────────────────────────────────┐
│                    RASPBERRY PI DEVICE                            │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │          Sensor Reading Loop (read_sensors.py)         │     │
│  │              (60 second intervals)                      │     │
│  └─────────┬──────────────────────────────────────────────┘     │
│            │                                                      │
│      ┌─────┴──────┐                                              │
│      │ ThreadPool │                                              │
│      │ Executor   │                                              │
│      └┬────┬────┬─┘                                              │
│       │    │    │                                                │
│   ┌───▼┐ ┌▼───┐ ┌▼────────┐                                     │
│   │BME │ │CPU │ │  Disk   │                                     │
│   │280 │ │Temp│ │  Space  │                                     │
│   │I2C │ │vcg │ │ shutil  │                                     │
│   └───┬┘ └┬───┘ └┬────────┘                                     │
│       └───┴──────┘                                               │
│            │                                                      │
│            ▼                                                      │
│  ┌─────────────────────┐                                         │
│  │  Local PostgreSQL   │                                         │
│  │    Database         │                                         │
│  │  (sensor_project    │                                         │
│  │   .readings table)  │                                         │
│  │  - Buffers data     │                                         │
│  │  - is_synced flag   │                                         │
│  └──────────┬──────────┘                                         │
│             │                                                     │
│             │ Sync attempts                                      │
│             │ (every cycle)                                      │
│             │                                                     │
└─────────────┼─────────────────────────────────────────────────────┘
              │
              │ HTTPS/HTTP
              │ POST /readings/bulk
              │
              ▼
┌──────────────────────────────────────────────────────────────────┐
│                     CLOUD / REMOTE SERVER                         │
│                                                                   │
│  ┌────────────────────────────────────────────────────────┐     │
│  │          FastAPI Application (api/main.py)             │     │
│  │            Endpoints:                                   │     │
│  │  - POST /readings (single)                             │     │
│  │  - POST /readings/bulk (batch sync)                    │     │
│  │  - GET /readings?start_date&end_date                   │     │
│  │  - GET /readings/latest                                │     │
│  └─────────────────────┬──────────────────────────────────┘     │
│                        │                                          │
│                        ▼                                          │
│  ┌────────────────────────────────────────────────────────┐     │
│  │         SQLAlchemy ORM (models.py)                     │     │
│  └─────────────────────┬──────────────────────────────────┘     │
│                        │                                          │
│                        ▼                                          │
│  ┌────────────────────────────────────────────────────────┐     │
│  │     PostgreSQL Database (RDS/Cloud)                    │     │
│  │     sensor_project.readings table                      │     │
│  │  - Permanent storage                                   │     │
│  │  - Query capabilities                                  │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

## File Structure

```
sensor_project/
├── api/                          # FastAPI application (cloud/remote)
│   ├── main.py                  # API routes and endpoints
│   └── models.py                # SQLAlchemy ORM models & Pydantic schemas
│
├── sensors/                      # Sensor driver modules (Raspberry Pi)
│   ├── __init__.py              
│   ├── bme280.py                # BME280 I2C sensor (temp/humidity/pressure)
│   ├── cpu_temp.py              # Raspberry Pi CPU temp (vcgencmd)
│   └── disk_space.py            # Disk usage monitoring (shutil)
│
├── logs/                         # Application logs
│   └── read_sensors.log         # Sensor reading and sync logs
│
├── docs/                         # Documentation
│   ├── SETUP.md                 # Detailed setup guide
│   └── ARCHITECTURE.md          # This file
│
├── read_sensors.py              # Main sensor reading script (Raspberry Pi)
├── run_api.py                   # API server launcher with .env support
├── test_api_connection.py       # API connectivity testing
├── requirements.txt             # Python dependencies
├── pyproject.toml               # Project configuration & metadata
├── sensor-api.service           # systemd service file
├── .env                         # Environment variables (not in git)
└── README.md                    # Project overview
```

## Component Details

### Sensor Reader (`read_sensors.py`)

**Purpose**: Continuously read sensors and maintain local/remote data sync

**Key Features**:
- **Parallel sensor reading**: Uses ThreadPoolExecutor to read all sensors concurrently
- **Local database buffering**: Stores all readings in local PostgreSQL with `is_synced` flag
- **Automatic sync**: Periodically attempts to sync unsynced records to remote API
- **Disk management**: Monitors disk usage and performs stratified deletion when threshold exceeded
- **Resilient**: Continues operation even when remote API is unavailable

**Main Loop**:
1. Read all sensors in parallel (60-second intervals)
2. Store reading in local database with `is_synced=false`
3. Attempt to sync unsynced records to remote API in batches
4. Mark successfully synced records with `is_synced=true`
5. Background thread monitors disk usage and cleans old data if needed

**Configuration**:
- `LOCAL_DB_CONFIG`: Local PostgreSQL connection parameters
- `API_SERVER`: Remote API endpoint (can be set via environment variable)
- `BULK_SYNC_BATCH_SIZE`: 360 records per sync batch
- `DISK_USAGE_THRESHOLD`: 50% triggers cleanup
- `DELETE_STRATEGY`: "stratified" for even temporal deletion

### API Module (`api/`)

**main.py** - FastAPI application
- **POST /readings**: Create single sensor reading
- **POST /readings/bulk**: Batch insert for sync operations
- **GET /readings**: Query readings by date range (ts_local)
- **GET /readings/latest**: Get most recent reading
- Uses dependency injection for database sessions

**models.py** - Data models
- **SQLAlchemy ORM**:
  - `ReadingORM`: Database table model (sensor_project.readings schema)
  - Columns: id, device_id, ts_utc, ts_local, payload (JSONB)
- **Pydantic Models**:
  - `ReadingCreate`: Input validation for new readings
  - `ReadingResponse`: API response format
  - `BulkReadingCreate`: Batch insert request
  - `LatestReadingResponse`: Latest reading response
- **Database**: Connects to PostgreSQL using environment variables (DB_USER, DB_PASSWORD, DB_HOST, etc.)

### Sensors Module (`sensors/`)

**bme280.py** - BME280 Environmental Sensor
- **Interface**: I2C communication via adafruit-blinka
- **I2C Address**: 0x77 (configurable)
- **Returns**: `{temperature: {c, f}, pressure: {hpa}, humidity: {rh}}`
- **Requirements**: I2C enabled on Raspberry Pi

**cpu_temp.py** - CPU Temperature Monitor
- **Interface**: Raspberry Pi vcgencmd utility
- **Returns**: `{c, f}`
- **Platform**: Raspberry Pi only
- **Error handling**: Returns error dict on non-Pi systems

**disk_space.py** - Disk Space Monitor
- **Interface**: Python shutil.disk_usage()
- **Returns**: `{total_mb, used_mb, free_mb}`
- **Path**: Monitors root filesystem ("/")
- **Platform**: Cross-platform (macOS, Linux, Windows)

## Data Flow

### 1. Sensor Reading Flow (Raspberry Pi)
```
Sensors (BME280, CPU, Disk) 
  → ThreadPoolExecutor (parallel reads)
  → Combined payload with timestamps
  → Local PostgreSQL INSERT (is_synced=false)
  → Log to file
```

### 2. Sync Flow (Raspberry Pi → Cloud)
```
Local DB query (is_synced=false records)
  → Batch into groups of 360
  → HTTP POST to /readings/bulk
  → On success: UPDATE is_synced=true
  → On failure: Retry next cycle
```

### 3. Disk Cleanup Flow (Raspberry Pi)
```
Background thread (every 5 min)
  → Check disk usage %
  → If > 50%: Calculate records to delete
  → Stratified deletion (evenly across time)
  → Free up space
```

### 4. API Query Flow (Cloud)
```
Client HTTP GET /readings?start_date&end_date
  → FastAPI endpoint validation
  → SQLAlchemy ORM query
  → Filter by ts_local datetime range
  → Return JSON response
```

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| API Framework | FastAPI | RESTful API with automatic OpenAPI docs |
| ASGI Server | Uvicorn | High-performance async server |
| ORM | SQLAlchemy 2.0 | Database abstraction & queries |
| Database | PostgreSQL | Relational data storage (local & cloud) |
| I2C Interface | Adafruit Blinka | GPIO/I2C abstraction for CircuitPython |
| Sensor Driver | adafruit-circuitpython-bme280 | BME280 sensor library |
| Environment Config | python-dotenv | Load .env variables |
| HTTP Client | requests | API sync communication |
| Production Server | Gunicorn | Optional production WSGI server |

## Database Schema

### Local Database (Raspberry Pi)
```sql
CREATE SCHEMA sensor_project;

CREATE TABLE sensor_project.readings (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR NOT NULL,
    ts_utc TIMESTAMP WITH TIME ZONE NOT NULL,
    ts_local TIMESTAMP WITH TIME ZONE NOT NULL,
    payload JSONB NOT NULL,
    is_synced BOOLEAN DEFAULT FALSE  -- Sync tracking flag
);

CREATE INDEX idx_is_synced ON sensor_project.readings(is_synced);
CREATE INDEX idx_ts_local ON sensor_project.readings(ts_local);
```

### Cloud Database
```sql
CREATE SCHEMA sensor_project;

CREATE TABLE sensor_project.readings (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR NOT NULL,
    ts_utc TIMESTAMP WITH TIME ZONE NOT NULL,
    ts_local TIMESTAMP WITH TIME ZONE NOT NULL,
    payload JSONB NOT NULL  -- No is_synced column
);

CREATE INDEX idx_device_ts ON sensor_project.readings(device_id, ts_local);
CREATE INDEX idx_ts_local ON sensor_project.readings(ts_local);
```

## Key Design Patterns

### 1. Buffered Sync Pattern
- Local-first data storage ensures no data loss
- Asynchronous sync allows operation during network outages
- `is_synced` flag tracks synchronization state

### 2. Parallel Sensor Reading
- ThreadPoolExecutor reads all sensors concurrently
- Reduces total read time from sum to maximum
- Handles individual sensor failures gracefully

### 3. Stratified Data Deletion
- Deletes records evenly across time range
- Maintains data distribution when storage limited
- Preserves recent and historical context

### 4. Separation of Concerns
- Sensor modules: Hardware interaction only
- read_sensors.py: Orchestration & sync logic
- API: Remote data access & querying
- Models: Data validation & ORM

### 5. Environment-Based Configuration
- .env files for deployment-specific settings
- No hardcoded credentials or endpoints
- Easy multi-environment deployment

## Deployment Architecture

### Raspberry Pi (Edge Device)
```
read_sensors.py (continuously running)
  ↓
Local PostgreSQL (buffering)
  ↓
Sync to remote API (when available)
```

**Run as systemd service**:
```bash
sudo systemctl enable sensor-api
sudo systemctl start sensor-api
```

### Cloud Server (API & Database)
```
FastAPI application (api/main.py)
  ↓
PostgreSQL RDS/Cloud Database
```

**Run with uvicorn or gunicorn**:
```bash
# Development
uvicorn api.main:app --reload

# Production
gunicorn api.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## Performance Considerations

### Sensor Reading
- **Parallel execution**: Sensors read concurrently (not sequentially)
- **Timeout handling**: Individual sensor failures don't block others
- **60-second interval**: Balances data granularity with system load

### Database
- **Connection pooling**: 2-10 connections (SimpleConnectionPool)
- **Batch inserts**: Bulk sync reduces HTTP overhead (360 records/batch)
- **JSONB payload**: Flexible schema without table alterations
- **Indexes**: Optimized for time-range queries and sync status

### Network Resilience
- **Local buffering**: No data loss during network outages
- **Retry logic**: Failed syncs retry on next cycle
- **Timeout**: 5-second connection timeout for API calls

## Adding New Sensors

1. Create new module in `sensors/` (e.g., `sensors/new_sensor.py`)
2. Implement `read()` function returning dict
3. Import in `read_sensors.py`
4. Add to ThreadPoolExecutor futures
5. Sensor data automatically included in payload

Example:
```python
# sensors/new_sensor.py
def read():
    try:
        # Your sensor reading logic
        return {"value": 123, "unit": "custom"}
    except Exception as e:
        return {"error": str(e)}
```

## Monitoring & Logging

- **Log location**: `logs/read_sensors.log`
- **Log format**: `%(asctime)s - %(levelname)s - %(message)s`
- **Log levels**: INFO for normal operations, ERROR for failures
- **Console output**: Duplicated to stdout for debugging

## Security Considerations

- **Database credentials**: Stored in .env (not in git)
- **API authentication**: Not implemented (add JWT/OAuth if exposing publicly)
- **HTTPS**: Recommended for production API endpoints
- **SQL injection**: Protected by SQLAlchemy parameterized queries

## Future Enhancements

- [ ] User authentication & authorization for API
- [ ] Real-time WebSocket updates for live monitoring
- [ ] Data visualization dashboard (Grafana integration)
- [ ] Threshold-based alerts/notifications
- [ ] Additional sensor types (light, motion, gas)
- [ ] Historical data analytics and trend analysis
- [ ] Multi-device management interface
