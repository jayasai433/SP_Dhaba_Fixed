"""
Purchases.

Each purchase persists:
  quantity              in the chosen unit (what staff typed)
  unit                  the unit label at time of entry
  unit_conversion_factor conversion to item.base_unit at time of entry
  base_quantity         quantity * unit_conversion_factor (persisted, immutable)
  price_per_unit        price per one of the chosen unit
  total_cost            quantity * price_per_unit

Storing `base_quantity` up front lets a future stock module aggregate purely on
that single field without knowing anything about historical unit choices.
"""
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from core.db import db
from core.security import get_current_user, require_roles
from core.utils import now_utc, iso, _can_view_all
from models.transaction import PurchaseIn, VoidIn
from services.duplicate import check_duplicate_purchase
from services.void import void_entry

router = APIRouter()


@router.get("/purchases")
async def list_purchases(
    start: Optional[str] = None,
    end: Optional[str] = None,
    item_id: Optional[str] = None,
    user=Depends(get_current_user),
):
    q: dict = {}
    if start:
        q.setdefault("date", {})["$gte"] = start
    if end:
        q.setdefault("date", {})["$lte"] = end
    if item_id:
        q["item_id"] = item_id
    if not _can_view_all(user):
        q["created_by"] = user["id"]
    q["is_void"] = {"$ne": True}
    docs = await db.purchases.find(q, {"_id": 0}).sort("created_at", -1).to_list(2000)
    items = {i["id"]: i for i in await db.items.find({}, {"_id": 0}).to_list(2000)}
    for d in docs:
        it = items.get(d["item_id"], {})
        d["item_name"] = it.get("name", "(deleted item)")
        d["category"] = it.get("category", "")
    return docs


@router.post("/purchases")
async def create_purchase(payload: PurchaseIn,
                          user=Depends(require_roles("admin", "staff"))):
    item = await db.items.find_one({"id": payload.item_id})
    if not item:
        raise HTTPException(400, "Item not found")

    # Validate that the chosen unit is one the item supports; use the stored
    # conversion factor as the source of truth (defence in depth).
    unit_row = next((u for u in item.get("units", []) if u["name"].lower() == payload.unit.lower()), None)
    if not unit_row:
        raise HTTPException(400, f'"{payload.unit}" is not a valid unit for {item["name"]}')
    conversion_factor = float(unit_row["conversion_factor"])

    await check_duplicate_purchase(payload.item_id, payload.date, float(payload.quantity))

    quantity = float(payload.quantity)
    price = float(payload.price_per_unit)
    base_quantity = round(quantity * conversion_factor, 6)
    total_cost = round(quantity * price, 2)

    doc = {
        "id": str(uuid.uuid4()),
        "item_id": payload.item_id,
        "date": payload.date,
        "quantity": quantity,
        "unit": unit_row["name"],
        "unit_conversion_factor": conversion_factor,
        "base_unit": item.get("base_unit", unit_row["name"]),
        "base_quantity": base_quantity,
        "price_per_unit": price,
        "total_cost": total_cost,
        "notes": payload.notes or "",
        "created_by": user["id"],
        "created_by_name": user["name"],
        "created_at": iso(now_utc()),
        "is_void": False,
        "voided_by": None,
        "voided_at": None,
        "void_reason": None,
    }
    await db.purchases.insert_one(doc)
    doc.pop("_id", None)
    doc["item_name"] = item["name"]
    doc["category"] = item.get("category", "")
    return doc


@router.patch("/purchases/{purchase_id}/void")
async def void_purchase(purchase_id: str, payload: VoidIn,
                        user=Depends(get_current_user)):
    return await void_entry(db.purchases, purchase_id, payload.reason, user)
