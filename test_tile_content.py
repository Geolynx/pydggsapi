import os
import json
from dotenv import load_dotenv
from fastapi.testclient import TestClient

load_dotenv()
os.environ["PYTHONPATH"] = "."
from pydggsapi.api import app
client = TestClient(app)

# Zoom 5 should map to zone_level 3 for IGEO7
# x=18, y=9 is approx Europe
url = "/tiles-api/aet_trend_duckdb/5/18/9"
print(f"Testing {url}")
response = client.get(url)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    print(f"Received {len(response.content)} bytes")
    if len(response.content) > 100:
        print("Tile seems to have real content!")
    else:
        # 25-100 bytes usually means empty but valid MVT structure
        print("Tile is valid but might be empty.")
