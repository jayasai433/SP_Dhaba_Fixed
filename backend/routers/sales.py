import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from core.db import db
from core.security import get_current_user, require_roles
from core.utils import now_utc, iso
from models.transaction import SalesIn

router = APIRouter()


@router.get("/sales")
async def list_sales(
    start: Optional[str] = None,
    end: Optional[str] = None,
    user=Depends(get_current_user),
):
    q: dict = {}
    if start:
        q.setdefault("date", {})["$gte"] = start
    if end:
        q.setdefault("date", {})["$lte"] = end
    if user["role"] == "staff":
        q["created_by"] = user["id"]
    return await db.sales.find(q, {"_id": 0}).sort("date", -1).to_list(2000)


@router.post("/sales")
async def create_sales(payload: SalesIn,
                       user=Depends(require_roles("admin", "staff"))):
    existing = await db.sales.find_one({"date": payload.date})
    if existing:
        raise HTTPException(409, "Sales already recorded for this date")
    total = round(payload.lunch_amount + payload.dinner_amount + payload.other_amount, 2)
    doc = {
        "id": str(uuid.uuid4()),
        "date": payload.date,
        "lunch_amount": float(payload.lunch_amount),
        "dinner_amount": float(payload.dinner_amount),
        "other_amount": float(payload.other_amount),
        "total_amount": total,
        "notes": payload.notes or "",
        "created_by": user["id"],
        "created_by_name": user["name"],
        "created_at": iso(now_utc()),
    }
    await db.sales.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/sales/check/{date}")
async def check_sales(date: str, user=Depends(get_current_user)):
    entry = await db.sales.find_one({"date": date}, {"_id": 0})
    return {"exists": entry is not None, "entry": entry}


@router.patch("/sales/{sale_id}")
async def update_sales(sale_id: str, payload: SalesIn,
                       user=Depends(require_roles("admin"))):
    """Admin correction path. Staff must contact admin to fix a saved entry."""
    existing = await db.sales.find_one({"id": sale_id})
    if not existing:
        raise HTTPException(404, "Sales entry not found")
    total = round(payload.lunch_amount + payload.dinner_amount + payload.other_amount, 2)
    update = {
        "lunch_amount": float(payload.lunch_amount),
        "dinner_amount": float(payload.dinner_amount),
        "other_amount": float(payload.other_amount),
        "total_amount": total,
        "notes": payload.notes or "",
        "updated_by": user["name"],
        "updated_at": iso(now_utc()),
    }
    await db.sales.update_one({"id": sale_id}, {"$set": update})
    return await db.sales.find_one({"id": sale_id}, {"_id": 0})
