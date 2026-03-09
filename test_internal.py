import os
import json
from dotenv import load_dotenv
from fastapi.testclient import TestClient

print("1. Loading environment")
load_dotenv()
os.environ["PYTHONPATH"] = "."

print("2. Importing app")
from pydggsapi.api import app

client = TestClient(app)

print("3. Testing /collections")
try:
    response = client.get("/dggs-api/v1-pre/collections")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"ERROR during request: {e}")
    import traceback
    traceback.print_exc()

print("4. Testing /tiles-api/aet_trend_duckdb/5/18/9")
try:
    # This might trigger dggrid
    response = client.get("/tiles-api/aet_trend_duckdb/5/18/9")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print(f"Received {len(response.content)} bytes")
except Exception as e:
    print(f"ERROR during tiles request: {e}")
    import traceback
    traceback.print_exc()
