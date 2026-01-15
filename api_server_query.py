"""
Query API Server entry point.
Starts the FastAPI server for querying sensor readings (GET endpoints).

Devices that query/retrieve data should connect to this server.

Usage:
    python3 api_server_query.py
    
Or with uvicorn:
    uvicorn lib.server.query:app --host 0.0.0.0 --port 8001
"""
from dotenv import load_dotenv
load_dotenv()

import uvicorn
from lib.server.query import app

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        reload=False  # Set to True for development
    )
