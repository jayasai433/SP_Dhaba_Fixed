from dotenv import load_dotenv
from pathlib import Path
import os
import pytz

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / ".env")

def _require(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise RuntimeError(
            f"Missing required environment variable: {key}\n"
            f"Add it to Railway Variables or your .env file."
        )
    return val

MONGO_URL       = _require("MONGO_URL")
DB_NAME         = _require("DB_NAME")
JWT_SECRET      = _require("JWT_SECRET")
JWT_ALGO        = "HS256"
TOKEN_TTL_HOURS = 8

CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")

IST = pytz.timezone("Asia/Kolkata")

ENVIRONMENT    = os.environ.get("ENVIRONMENT", "production").lower()
IS_STAGING     = ENVIRONMENT == "staging"

ADMIN_EMAIL    = os.environ.get("ADMIN_EMAIL",    "admin@spdhaba.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@123")
STAFF_EMAIL    = os.environ.get("STAFF_EMAIL",    "lokesh@spdhaba.com")
STAFF_PASSWORD = os.environ.get("STAFF_PASSWORD", "Staff@123")
VIEWER_EMAIL   = os.environ.get("VIEWER_EMAIL",   "display@spdhaba.com")
VIEWER_PASSWORD= os.environ.get("VIEWER_PASSWORD","View@123")
