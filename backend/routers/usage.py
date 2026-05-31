import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from core.db import db
from core.security import get_current_user, require_roles
from core.utils import now_utc, iso, _can_view_all
from models.transaction import UsageIn, VoidIn
from services.duplicate import check_duplicate_usage
from services.void import void_entry

router = APIRouter()

@router.get("/usage")
async def list_usage(
    start: Optional[str] = None, end: Optional[str] = None,
    item_id: Optional[str] = None, user=Depends(get_current_user)
):
    q = {}
    if start:   q.setdefault("date", {})["$gte"] = start
    if end:     q.setdefault("date", {})["$lte"] = end
    if item_id: q["item_id"] = item_id
    if not _can_view_all(user):
        q["created_by"] = user["id"]
    q["is_void"] = {"$ne": True}
    docs  = await db.daily_usage.find(q, {"_id": 0}).sort("created_at", -1).to_list(2000)
    items = {i["id"]: i for i in await db.items.find({}, {"_id": 0}).to_list(2000)}
    for d in docs:
        it = items.get(d["item_id"], {})
        d["item_name"] = it.get("name", "Unknown")
        d["unit"]       = it.get("unit", "")
    return docs

@router.post("/usage")
async def create_usage(payload: UsageIn, user=Depends(require_roles("admin", "staff"))):
    item = await db.items.find_one({"id": payload.item_id})
    if not item:
        raise HTTPException(400, "Item not found")
    await check_duplicate_usage(payload.item_id, payload.date, float(payload.quantity_used))
    doc = {
        "id": str(uuid.uuid4()), "item_id": payload.item_id, "date": payload.date,
        "quantity_used": float(payload.quantity_used), "notes": payload.notes or "",
        "created_by": user["id"], "created_by_name": user["name"],
        "created_at": iso(now_utc()),
        "is_void": False, "voided_by": None, "voided_at": None, "void_reason": None,
    }
    await db.daily_usage.insert_one(doc)
    doc.pop("_id", None)
    return doc

@router.patch("/usage/{usage_id}/void")
async def void_usage(usage_id: str, payload: VoidIn, user=Depends(get_current_user)):
    return await void_entry(db.daily_usage, usage_id, payload.reason, user)
