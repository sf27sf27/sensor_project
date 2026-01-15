# SQLAlchemy Everywhere Refactoring - Complete

## Overview
Consolidated database access from mixed psycopg2/SQLAlchemy to unified SQLAlchemy ORM throughout the codebase. This improves maintainability, type safety, and reduces code duplication.

## Changes Made

### 1. **lib/server/models.py** - Dual Database Support
- Added `LOCAL_DATABASE_URL` configuration alongside existing `CLOUD_DATABASE_URL`
- Created separate engine instances:
  - `cloud_engine` → API servers (RDS cloud database)
  - `local_engine` → Raspberry Pi backup database
- Created separate sessionmakers:
  - `CloudSessionLocal` → For FastAPI API servers
  - `LocalSessionLocal` → For sensor reading and sync operations
- Added `get_local_db()` dependency function for local database access
- `SessionLocal` kept for backward compatibility (points to cloud)
- Both databases share the same `ReadingORM` model ✓

**Key Feature**: Environment variables now control both databases:
```python
# Cloud (API servers)
DB_USER, DB_PASSWORD, DB_HOST, DB_NAME, DB_PORT

# Local (RPi)
LOCAL_DB_HOST, LOCAL_DB_USER, LOCAL_DB_PASSWORD, LOCAL_DB_NAME, LOCAL_DB_PORT
```

### 2. **lib/database.py** - Removed Raw psycopg2
**Removed:**
- `db_pool` global variable (psycopg2 connection pool)
- `get_local_db_connection()` function
- `return_db_connection()` function
- All manual connection management code

**Refactored:**
- `initialize_connection_pool()` → Now tests SQLAlchemy connection instead of creating psycopg2 pool
- `save_to_backup()` → Uses `LocalSessionLocal` and `ReadingORM` ORM
- `reduce_data_granularity()` → Uses SQLAlchemy queries instead of raw SQL

**Before (psycopg2):**
```python
cur.execute(INSERT_SQL, (device_id, ts_utc, payload))
cur.execute(COUNT_ALL_RECORDS_SQL)
total_records = cur.fetchone()[0]
```

**After (SQLAlchemy):**
```python
db.add(ReadingORM(device_id=device_id, ts_utc=ts_utc, payload=payload))
db.commit()

total_records = db.query(ReadingORM).count()
```

### 3. **lib/api_client.py** - Replaced Raw SQL
**Removed:**
- `get_local_db_connection()` / `return_db_connection()` usage
- Raw cursor operations with `cur.execute(SELECT_UNSYNCED_SQL)`
- Manual record unpacking: `record_id, dev_id, ts_utc, ts_local, payload = record`

**Refactored:**
- `sync_backup_to_api()` → Queries using `db.query(ReadingORM)` instead of raw SQL
- Batch deletion using `db.query(ReadingORM).filter(ReadingORM.id.in_(batch_ids)).delete()`
- Type-safe record access: `record.device_id` instead of `record[1]`

**Before (raw SQL):**
```python
cur.execute(SELECT_UNSYNCED_SQL)
records = cur.fetchall()  # Returns tuples

for record in batch:
    record_id, dev_id, ts_utc, ts_local, payload = record  # Unpacking
```

**After (SQLAlchemy):**
```python
records = db.query(ReadingORM).all()  # Returns ORM objects

for record in batch:
    dev_id = record.device_id  # Type-safe, IDE autocomplete
    ts_utc = record.ts_utc
```

### 4. **main.py** - Simplified Imports
- Removed: `get_local_db_connection`, `return_db_connection` imports
- These functions are no longer needed; SQLAlchemy handles pooling automatically

### 5. **lib/monitors.py** - SQLAlchemy Connection Testing
- Refactored `connection_pool_monitor()` to test connections via `LocalSessionLocal`
- Removed references to global `db_pool` variable
- Now uses SQLAlchemy's built-in connection validation

### 6. **lib/config.py** - Cleaned Up SQL Strings
- Removed `INSERT_SQL`, `SELECT_UNSYNCED_SQL`, `DELETE_SYNCED_SQL`, etc.
- Removed `COUNT_ALL_RECORDS_SQL`, `GET_TIMESTAMP_RANGE_SQL`, `GET_RECORDS_FOR_DELETION_SQL`, `DELETE_RECORDS_BY_ID_SQL`
- Removed `LOCAL_DB_CONFIG` dictionary (now in models.py)
- All database logic now in ORM layer ✓

---

## Benefits

| Aspect | Before | After |
|--------|--------|-------|
| **Connection Pooling** | Manual psycopg2 pool | Automatic SQLAlchemy |
| **Code Duplication** | SQL strings copied across files | Single ORM models |
| **Type Safety** | Tuple unpacking `record[1]` | Object access `record.device_id` |
| **Testing** | Mocking psycopg2 connections | Mocking ORM sessions |
| **Maintenance** | Update SQL in multiple places | Update ORM model once |
| **IDE Support** | No autocomplete for tuples | Full IDE autocomplete |
| **Error Handling** | Generic DB exceptions | `SQLAlchemyError` for ORM |

---

## Testing

All imports validated ✓
- `lib.server.models` (LOCAL/CloudSessionLocal, ReadingORM)
- `lib.database` (initialize_connection_pool, save_to_backup, reduce_data_granularity)
- `lib.api_client` (check_api_health, insert_reading, sync_backup_to_api)
- `lib.monitors` (disk_space_monitor, connection_pool_monitor)

No syntax errors in modified files ✓

---

## Migration Steps for Deployment

1. **Update environment variables on Raspberry Pi:**
   ```bash
   # Existing (cloud API):
   export DB_USER=your_cloud_user
   export DB_PASSWORD=your_cloud_pass
   export DB_HOST=your_cloud_host
   export DB_NAME=your_cloud_db
   
   # New (local backup):
   export LOCAL_DB_HOST=127.0.0.1
   export LOCAL_DB_USER=sensor_user
   export LOCAL_DB_PASSWORD=strongpassword
   export LOCAL_DB_NAME=sensors
   ```

2. **Test locally:**
   ```bash
   python -m pytest tests/
   python main.py  # Should start without errors
   ```

3. **Deploy to Raspberry Pi:**
   - Copy updated code
   - Restart systemd services: `systemctl restart sensor-reader sensor-api-write`
   - Monitor logs: `journalctl -u sensor-reader -f`

---

## Backward Compatibility

✓ `SessionLocal` still points to cloud database (for existing API code)
✓ `initialize_connection_pool()` still exists (graceful degradation)
✓ All function signatures unchanged (only internals refactored)

---

## Future Work

1. **Add Alembic migrations** (when schema changes needed):
   ```bash
   alembic init alembic
   alembic revision --autogenerate -m "add_column_x"
   alembic upgrade head
   ```

2. **Add structured JSON logging** (for distributed systems):
   ```python
   from pythonjsonlogger import jsonlogger
   ```

3. **Stricter type validation** (if needed):
   - Lock `payload` to specific sensor schema
   - Create `SensorPayload` Pydantic model

---

## Questions?

The refactoring is complete. All database operations now use SQLAlchemy ORM.
Key file to reference: **lib/server/models.py** (single source of truth for database schema)
