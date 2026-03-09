import os
import logging
from dotenv import load_dotenv

# Setup logging to see what's happening
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("startup_test")

print("1. Loading .env")
load_dotenv()

print("2. Importing api")
try:
    from pydggsapi.api import app
    print("3. API imported successfully")
except Exception as e:
    print(f"FAILED to import API: {e}")
    import traceback
    traceback.print_exc()

print("4. Attempting to access collections")
try:
    from pydggsapi.routers.dggs_api import collections
    print(f"Collections loaded: {list(collections.keys())}")
except Exception as e:
    print(f"FAILED to load collections: {e}")
    import traceback
    traceback.print_exc()
