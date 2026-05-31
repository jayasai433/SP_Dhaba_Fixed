from dotenv import load_dotenv
from pathlib import Path
import os
import pytz

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / ".env")

MONGO_URL       = os.environ["MONGO_URL"]
DB_NAME         = os.environ["DB_NAME"]
JWT_SECRET      = os.environ["JWT_SECRET"]
JWT_ALGO        = "HS256"
TOKEN_TTL_HOURS = 8

CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")

IST = pytz.timezone("Asia/Kolkata")

ADMIN_EMAIL    = os.environ.get("ADMIN_EMAIL",    "admin@spdhaba.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@123")
STAFF_EMAIL    = os.environ.get("STAFF_EMAIL",    "lokesh@spdhaba.com")
STAFF_PASSWORD = os.environ.get("STAFF_PASSWORD", "Staff@123")
VIEWER_EMAIL   = os.environ.get("VIEWER_EMAIL",   "display@spdhaba.com")
VIEWER_PASSWORD= os.environ.get("VIEWER_PASSWORD","View@123")
