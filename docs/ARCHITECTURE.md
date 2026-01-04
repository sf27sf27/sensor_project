# Sensor Project Architecture

## System Overview

```
┌─────────────────────────────────────────────────────┐
│         External Clients / API Consumers             │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              FastAPI Application                     │
│         (api/main.py - Port 8000)                   │
│  - REST API Endpoints                               │
│  - Request Routing                                  │
│  - Response Formatting                              │
└──────────────────────┬──────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │ Sensor   │  │ Sensor   │  │ Sensor   │
  │ Module 1 │  │ Module 2 │  │ Module 3 │
  │(BME280)  │  │(CPU Temp)│  │(Disk)    │
  └──────────┘  └──────────┘  └──────────┘
        │              │              │
        └──────────────┼──────────────┘
                       │
                       ▼
        ┌──────────────────────────┐
        │  Data Persistence Layer  │
        │   (SQLAlchemy ORM)       │
        └──────────────┬───────────┘
                       │
                       ▼
        ┌──────────────────────────┐
        │    PostgreSQL Database   │
        │  (or SQLite for local)   │
        └──────────────────────────┘
```

## File Structure

```
sensor_project/
├── api/                          # FastAPI application
│   ├── __init__.py              
│   ├── main.py                  # FastAPI app, routes, and startup
│   └── models.py                # SQLAlchemy ORM models
│
├── sensors/                      # Sensor driver modules
│   ├── __init__.py              
│   ├── bme280.py                # BME280 sensor (temp/humidity/pressure)
│   ├── cpu_temp.py              # CPU temperature sensor
│   └── disk_space.py            # Disk space monitoring
│
├── logs/                         # Application logs
│   ├── app.log                  # API server logs
│   ├── sensors.log              # Sensor reading logs
│   └── errors.log               # Error logs
│
├── docs/                         # Documentation
│   ├── SETUP.md                 # This file
│   └── ARCHITECTURE.md          # System architecture
│
├── read_sensors.py              # Standalone sensor reading script
├── test_api_connection.py       # API testing script
├── requirements.txt             # Python dependencies
├── pyproject.toml               # Project configuration & metadata
├── .python-version              # Python version specification
├── .gitignore                   # Git ignore rules
├── .env                         # Environment variables (local)
└── README.md                    # Project README
```

## Component Details

### API Module (`api/`)

**main.py** - FastAPI application
- Initializes FastAPI app
- Defines routes and endpoints
- Handles request validation
- Implements error handling
- Manages startup/shutdown events

**models.py** - SQLAlchemy models
- Defines database schema
- Sensor data model
- Reading history model

### Sensors Module (`sensors/`)

**bme280.py** - BME280 Sensor Driver
- I2C communication
- Reads temperature, humidity, pressure
- Error handling and logging

**cpu_temp.py** - CPU Temperature Monitor
- Reads `/proc/cpuinfo` (Linux) or equivalent
- Polling mechanism
- Cross-platform support

**disk_space.py** - Disk Space Monitor
- Uses `shutil.disk_usage()`
- Calculates percentages
- Monitors all mounted drives

### Data Flow

1. **Sensor Reading**
   - Sensor module reads hardware/system data
   - Returns structured data (dict or object)
   - Logged to disk

2. **API Endpoint**
   - Client requests `/sensors` endpoint
   - FastAPI receives request
   - Queries database for latest readings
   - Returns JSON response

3. **Data Storage**
   - Sensor readings are inserted into database
   - SQLAlchemy ORM handles transactions
   - PostgreSQL persists data

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| API Framework | FastAPI | RESTful API |
| ASGI Server | Uvicorn | Application server |
| ORM | SQLAlchemy 2.0 | Database abstraction |
| Database | PostgreSQL | Data persistence |
| Hardware I2C | Adafruit Blinka | I2C communication |
| Sensor Driver | adafruit-circuitpython-bme280 | BME280 sensor |
| Environment | python-dotenv | Config management |
| Production WSGI | Gunicorn | Production server |

## Key Design Patterns

### 1. Separation of Concerns
- Sensor logic isolated in `sensors/` module
- API logic in `api/` module
- Clean interfaces between components

### 2. ORM Pattern
- SQLAlchemy abstracts database operations
- Easy to switch databases (SQLite → PostgreSQL)
- Type-safe queries

### 3. Environment Configuration
- `.env` file for sensitive data
- Configurable via environment variables
- Supports multiple deployment environments

### 4. Modular Sensors
- Each sensor type is a separate module
- Can be enabled/disabled independently
- Easy to add new sensors

## Configuration

### Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:password@localhost/sensor_db

# API
API_HOST=0.0.0.0
API_PORT=8000
RELOAD=true  # Development only

# Logging
LOG_LEVEL=INFO
```

### Deployment Modes

**Development**
```bash
uvicorn api.main:app --reload
```

**Production**
```bash
gunicorn -w 4 -k uvicorn.workers.UvicornWorker api.main:app
```

## Performance Considerations

1. **Database Indexing**: Create indexes on frequently queried columns
2. **Connection Pooling**: SQLAlchemy manages connection pool
3. **API Response Caching**: Consider caching sensor readings
4. **Sensor Read Interval**: Adjust based on hardware capabilities
5. **Logging**: Use appropriate log levels (INFO for prod, DEBUG for dev)

## Security

1. **Database Credentials**: Store in `.env`, never commit
2. **API Authentication**: Can be added via FastAPI middleware
3. **HTTPS**: Use reverse proxy (Nginx/Apache) in production
4. **Input Validation**: FastAPI auto-validates via Pydantic
5. **SQL Injection**: ORM prevents via parameterized queries

## Future Enhancements

- [ ] User authentication & authorization
- [ ] Real-time WebSocket updates
- [ ] Data visualization dashboard
- [ ] Alerts/notifications
- [ ] Sensor calibration UI
- [ ] Historical data analytics
- [ ] Multi-device support
