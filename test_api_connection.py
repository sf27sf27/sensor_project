#!/usr/bin/env python3
"""
Test script to verify API connectivity from the Raspberry Pi
Run this before starting read_sensors.py to ensure the API server is reachable

Usage:
    python test_api_connection.py                    # Tests localhost:8000
    API_SERVER=192.168.1.100:8000 python test_api_connection.py  # Tests custom server
"""

import os
import requests
import json
import socket
from datetime import datetime, timezone

# API configuration - can be overridden with API_SERVER environment variable
API_SERVER = os.getenv("API_SERVER", "localhost:8000")
API_BASE_URL = f"http://{API_SERVER}"
READINGS_ENDPOINT = f"{API_BASE_URL}/readings"

def test_connectivity():
    """Test basic connectivity to API server"""
    print(f"\n1. Testing connectivity to {API_BASE_URL}...")
    try:
        response = requests.get(f"{API_BASE_URL}/docs", timeout=5)
        if response.status_code == 200:
            print("   ✓ API server is reachable")
            return True
        else:
            print(f"   ✗ API server returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError as e:
        print(f"   ✗ Connection failed: {e}")
        return False
    except requests.exceptions.Timeout:
        print(f"   ✗ Request timed out (API server not responding)")
        return False
    except Exception as e:
        print(f"   ✗ Unexpected error: {e}")
        return False


def test_sample_reading():
    """Test sending a sample reading to the API"""
    print(f"\n2. Testing sample reading submission...")
    
    try:
        ts_utc = datetime.now(timezone.utc)
        ts_local = datetime.now().astimezone()
        device_id = socket.gethostname()
        
        payload = {
            "device_id": device_id,
            "ts_utc": ts_utc.isoformat(),
            "ts_local": ts_local.isoformat(),
            "payload": {
                "test": True,
                "message": "Test reading from test_api_connection.py",
                "sensor_data": {
                    "temperature": 25.5,
                    "humidity": 60.0
                }
            }
        }
        
        print(f"   Sending test reading from device: {device_id}")
        print(f"   Endpoint: {READINGS_ENDPOINT}")
        
        response = requests.post(
            READINGS_ENDPOINT,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 201:
            print("   ✓ Test reading submitted successfully")
            print(f"   Response: {response.json()}")
            return True
        else:
            print(f"   ✗ API returned status {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ✗ Request failed: {e}")
        return False
    except Exception as e:
        print(f"   ✗ Unexpected error: {e}")
        return False


def main():
    print("=" * 60)
    print("Sensor API Connection Test")
    print("=" * 60)
    print(f"API Server: {API_SERVER}")
    print(f"Device: {socket.gethostname()}")
    
    # Run tests
    connectivity_ok = test_connectivity()
    
    if not connectivity_ok:
        print("\n✗ Cannot reach API server. Troubleshooting steps:")
        print("  1. Verify the API server is running on the target machine")
        print("  2. Check that you're using the correct IP address")
        print("  3. Verify firewall settings allow connections on port 8000")
        print("  4. Test with: ping <api_server_ip>")
        return False
    
    api_ok = test_sample_reading()
    
    print("\n" + "=" * 60)
    if connectivity_ok and api_ok:
        print("✓ All tests passed! Ready to run read_sensors.py")
        print("\nTo start the sensor reader with a custom API server:")
        print(f"  export API_SERVER=<server_ip>:8000")
        print("  python read_sensors.py")
    else:
        print("✗ Some tests failed. Check the errors above.")
    print("=" * 60 + "\n")
    
    return connectivity_ok and api_ok


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
