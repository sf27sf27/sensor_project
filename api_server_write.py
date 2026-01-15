"""
Writer API Server entry point.
Starts the FastAPI server for writing sensor readings (POST endpoints).

Sensor devices that write data should connect to this server.

Usage:
    python3 api_server_write.py
    
Or with uvicorn:
    uvicorn lib.server.writer:app --host 0.0.0.0 --port 8000
"""
from dotenv import load_dotenv
load_dotenv()

import uvicorn
from lib.server.writer import app

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False  # Set to True for development
    )
