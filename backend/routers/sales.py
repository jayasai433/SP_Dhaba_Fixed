import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from core.db import db
from core.security import get_current_user, require_roles
from core.utils import now_utc, iso, _can_view_all
from models.transaction import SalesIn

router = APIRouter()

@router.get("/sales")
async def list_sales(
    start: Optional[str] = None, end: Optional[str] = None,
    user=Depends(get_current_user)
):
    q = {}
    if start: q.setdefault("date", {})["$gte"] = start
    if end:   q.setdefault("date", {})["$lte"] = end
    if not _can_view_all(user):
        q["created_by"] = user["id"]
    return await db.sales.find(q, {"_id": 0}).sort("date", -1).to_list(2000)

@router.post("/sales")
async def create_sales(payload: SalesIn, user=Depends(require_roles("admin", "staff"))):
    existing = await db.sales.find_one({"date": payload.date})
    if existing:
        raise HTTPException(409, "Sales already recorded for this date")
    total = round(payload.lunch_amount + payload.dinner_amount + payload.other_amount, 2)
    doc = {
        "id": str(uuid.uuid4()), "date": payload.date,
        "lunch_amount": float(payload.lunch_amount),
        "dinner_amount": float(payload.dinner_amount),
        "other_amount": float(payload.other_amount),
        "total_amount": total, "notes": payload.notes or "",
        "created_by": user["id"], "created_by_name": user["name"],
        "created_at": iso(now_utc()),
    }
    await db.sales.insert_one(doc)
    doc.pop("_id", None)
    return doc

@router.get("/sales/check/{date}")
async def check_sales(date: str, user=Depends(get_current_user)):
    entry = await db.sales.find_one({"date": date}, {"_id": 0})
    return {"exists": entry is not None, "entry": entry}
