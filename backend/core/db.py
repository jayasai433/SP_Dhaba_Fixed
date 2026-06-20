import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from core.config import MONGO_URL, DB_NAME

# TLS auto-detect: SRV URIs (Atlas) and explicit ?tls=true need TLS;
# plain mongodb://localhost on dev does not.
_needs_tls = MONGO_URL.startswith("mongodb+srv://") or "tls=true" in MONGO_URL.lower()

_kwargs = {"serverSelectionTimeoutMS": 30000, "connectTimeoutMS": 30000}
if _needs_tls:
    _kwargs["tls"]       = True
    _kwargs["tlsCAFile"] = certifi.where()

client = AsyncIOMotorClient(MONGO_URL, **_kwargs)
db = client[DB_NAME]
