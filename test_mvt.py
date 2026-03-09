import requests
import sys

def test_tile():
    url = "http://localhost:8000/tiles-api/aet_trend_duckdb/5/18/9"
    print(f"Requesting tile: {url}")
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            print(f"Success! Received {len(r.content)} bytes.")
            # Basic check for MVT header
            if len(r.content) > 0:
                print("Protobuf data received.")
        elif r.status_code == 204:
            print("No data for this tile (expected for some areas).")
        else:
            print(f"Error: {r.status_code}")
            print(r.text)
    except Exception as e:
        print(f"Failed to connect: {e}")

if __name__ == "__main__":
    test_tile()
