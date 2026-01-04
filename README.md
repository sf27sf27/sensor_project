# Sensor Project

A FastAPI-based sensor monitoring system that reads sensor data (BME280, CPU temperature, disk space) and exposes it via REST API.

## Features

- **Multi-sensor support**: BME280 (temperature, humidity, pressure), CPU temperature, disk space monitoring
- **FastAPI REST API**: Lightweight and performant API for accessing sensor data
- **Database persistence**: SQLAlchemy ORM with PostgreSQL support
- **Real-time monitoring**: Continuous sensor reading with error handling

## Project Structure

```
sensor_project/
├── api/                  # FastAPI application
│   ├── main.py          # FastAPI app and routes
│   └── models.py        # SQLAlchemy models
├── sensors/             # Sensor modules
│   ├── __init__.py
│   ├── bme280.py        # BME280 sensor driver
│   ├── cpu_temp.py      # CPU temperature monitor
│   └── disk_space.py    # Disk space monitor
├── logs/                # Application logs
├── read_sensors.py      # Standalone sensor reading script
├── test_api_connection.py
├── requirements.txt     # Python dependencies
└── README.md
```

## Setup

### Prerequisites

- Python 3.9+
- PostgreSQL (optional, for database persistence)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/sf27sf27/sensor_project.git
cd sensor_project
```

2. **Create virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables** (optional)
Create a `.env` file:
```env
# Database connection (optional)
DATABASE_URL=postgresql://user:password@localhost/sensor_db

# API settings
API_HOST=0.0.0.0
API_PORT=8000
```

## Usage

### Start the API Server

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`

### Access API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Run Sensor Reader

```bash
python read_sensors.py
```

## API Endpoints

### Sensor Data
- `GET /sensors` - Get all sensor readings
- `GET /sensors/{sensor_id}` - Get specific sensor data
- `POST /sensors` - Record sensor data

### Health
- `GET /health` - Health check endpoint

## Troubleshooting

### ModuleNotFoundError or Import errors
Ensure virtual environment is activated:
```bash
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate     # Windows
```

### Port already in use
Change the port when starting:
```bash
uvicorn api.main:app --port 8001
```

### Database connection issues
Check your `.env` file and ensure PostgreSQL is running (if using database).

## Development

### Running tests
```bash
pytest
```

### Code style
```bash
# Format code
black .

# Check linting
flake8 .
```

## Contributing

Feel free to submit issues and enhancement requests!

## License

MIT License - see LICENSE file for details

## Author

Steven Fullerton - https://github.com/sf27sf27
