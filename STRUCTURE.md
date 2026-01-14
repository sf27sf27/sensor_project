# Final Project Structure

## Overview

```
sensor_project/
├── main.py                  # Sensor reader entry point
├── api_server.py            # API server entry point
│
├── lib/                     # All system infrastructure
│   ├── __init__.py
│   ├── config.py           # Shared configuration & constants
│   ├── database.py         # Connection pooling, DB queries
│   ├── api_client.py       # API communication, syncing
│   ├── monitors.py         # Background monitoring threads
│   └── server/             # FastAPI server
│       ├── __init__.py
│       ├── models.py       # Pydantic & SQLAlchemy models
│       └── main.py         # FastAPI app & endpoints
│
├── sensors/                # Domain-specific sensor readers
│   ├── __init__.py
│   ├── disk_space.py
│   ├── cpu_temp.py
│   └── bme280.py
│
├── logs/                   # Runtime logs (auto-created)
├── read_sensors.py         # Original backup script
└── [config files, docs, etc]
```

## Running the System

### Sensor Reader (Reads sensors, sends to API, manages backups)
```bash
python3 main.py
```

### API Server (Receives and stores readings)
```bash
python3 api_server.py
```

Or with uvicorn directly:
```bash
uvicorn lib.server.main:app --reload --host 0.0.0.0 --port 8000
```

## Architecture

### Root Level (Entry Points)
- **main.py** - Sensor reading orchestration
- **api_server.py** - FastAPI server runner

### lib/ (System Infrastructure)
All reusable system code grouped together:

- **config.py** - API endpoints, DB credentials, logging, SQL queries, thresholds
- **database.py** - Connection pooling, backup storage, data granularity management
- **api_client.py** - Sensor → API communication, bulk sync logic
- **monitors.py** - Background threads (disk monitoring, connection health)
- **server/** - REST API server
  - **models.py** - Pydantic schemas, SQLAlchemy ORM models, DB session
  - **main.py** - FastAPI routes, API key verification

### sensors/ (Domain Code)
Independent sensor reader modules:
- Each module exports a `read()` function
- No dependencies on other sensor modules
- Can be tested and deployed independently

## Key Design Decisions

1. **Two Entry Points**
   - `main.py` runs the sensor reader
   - `api_server.py` runs the API server
   - Can run independently or together

2. **Shared Configuration**
   - `lib/config.py` contains all settings
   - Both sensor reader and API can use the same config values
   - Centralized logging setup

3. **Clean Separation**
   - `lib/` contains all system/infrastructure code
   - `sensors/` contains domain logic
   - API server isolated in `lib/server/`
   - Reduces coupling, easier to test

4. **Scalability**
   - Easy to add new monitoring threads (`lib/monitors.py`)
   - Easy to add new API endpoints (`lib/server/main.py`)
   - Easy to add new sensors (`sensors/`)
   - Easy to add new infrastructure (`lib/new_module.py`)

## Development Workflow with AI

This structure is ideal for AI-assisted development because:

1. **Focused Conversations** - "Fix the API bulk sync" → examine `lib/api_client.py`
2. **Isolated Context** - Each module is self-contained
3. **Clear Intent** - File structure documents responsibility
4. **Reusable** - Can ask AI to fix the same module multiple times across sessions

## Example: Adding a Cache Layer

To add Redis caching, you would:

1. Create `lib/cache.py` with caching functions
2. Import and use in `lib/database.py` or `lib/api_client.py`
3. Add config in `lib/config.py`
4. No changes needed to `main.py`, sensors, or API endpoints

## Systemd Service Files

For production, create two systemd services:

### sensor-reader.service
```ini
[Service]
ExecStart=/usr/bin/python3 /path/to/sensor_project/main.py
```

### sensor-api.service
```ini
[Service]
ExecStart=/usr/bin/python3 /path/to/sensor_project/api_server.py
```

Both can run on the same machine or separate machines, sharing the same PostgreSQL database.
