import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from core.config import MONGO_URL, DB_NAME

client = AsyncIOMotorClient(
    MONGO_URL,
    tls=True,
    tlsCAFile=certifi.where(),
    serverSelectionTimeoutMS=30000,
    connectTimeoutMS=30000,
)
db = client[DB_NAME]
