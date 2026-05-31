from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
from core.db import db
from core.utils import now_utc, iso

async def void_entry(collection, entry_id: str, reason: str, user: dict) -> dict:
    """
    Shared void logic.
    - Admin: can void any entry, any time.
    - Staff: only their own entries, only within 24 hours.
    - Viewer: forbidden.
    """
    if user["role"] == "viewer":
        raise HTTPException(status_code=403, detail="Forbidden: insufficient role")

    doc = await collection.find_one({"id": entry_id})
    if not doc:
        raise HTTPException(404, "Entry not found")
    if doc.get("is_void"):
        raise HTTPException(409, "Already voided")

    if user["role"] == "staff":
        if doc["created_by"] != user["id"]:
            raise HTTPException(403, "Staff can only void their own entries")
        created = datetime.fromisoformat(doc["created_at"].replace("Z", "+00:00"))
        if (datetime.now(timezone.utc) - created).total_seconds() > 86400:
            raise HTTPException(403, "Staff can only void entries made today")

    if not reason.strip():
        raise HTTPException(400, "Void reason is required")

    await collection.update_one({"id": entry_id}, {"$set": {
        "is_void":    True,
        "voided_by":  user["name"],
        "voided_at":  iso(now_utc()),
        "void_reason": reason.strip(),
    }})
    return {"voided": True}
