import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
EVENTS_FILE = DATA_DIR / "events.json"
SCRIPT_FILE = DATA_DIR / "script.json"
STATIC_DIR = ROOT / "static"
VIDEOS_DIR = STATIC_DIR / "videos"
SQL_DIR = ROOT / "sql"

NIMBLE_API_KEY = os.getenv("NIMBLE_API_KEY", "")
RAWTREE_API_KEY = os.getenv("RAWTREE_API_KEY", "")
RAWTREE_API_URL = os.getenv("RAWTREE_API_URL", "https://api.rawtree.com").rstrip("/")
RAWTREE_DATABASE = os.getenv("RAWTREE_DATABASE", "default")
RAWTREE_TABLE = os.getenv("RAWTREE_TABLE", "local_events")
BFL_API_KEY = os.getenv("BFL_API_KEY", "")
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() == "true"

NEIGHBORHOOD = os.getenv("NEIGHBORHOOD", "Hayes Valley, San Francisco")
DAYS_AHEAD = 7
AGENT_EFFORT = "medium"
BFL_API_URL = "https://api.bfl.ai/v1"

STORE_QUERIES = [
    f"boutiques in {NEIGHBORHOOD}",
    f"bookstores in {NEIGHBORHOOD}",
    f"coffee shops in {NEIGHBORHOOD}",
]

# One Nimble agent run per topic, run in parallel.
EVENT_TOPICS = [
    "sales, sample sales and store promotions",
    "store openings, product launches and pop-up shops",
    "workshops, classes, book readings and author events",
    "live music, DJ nights and performances",
    "food and drink events, tastings and markets",
    "community events, art walks and neighborhood gatherings",
]

CATEGORIES = ["sale", "launch", "workshop", "popup", "music", "food", "community", "other"]

for d in (RAW_DIR, VIDEOS_DIR):
    d.mkdir(parents=True, exist_ok=True)
