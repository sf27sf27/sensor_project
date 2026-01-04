import os
from dotenv import load_dotenv
import subprocess
import sys

load_dotenv()

host = os.getenv("API_HOST", "127.0.0.1")
port = os.getenv("API_PORT", "8000")
debug = os.getenv("DEBUG", "False").lower() == "true"

cmd = [
    sys.executable, "-m", "uvicorn",
    "api.main:app",
    "--host", host,
    "--port", port,
]

if debug:
    cmd.append("--reload")

subprocess.run(cmd)
