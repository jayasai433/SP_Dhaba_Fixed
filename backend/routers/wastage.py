"""
Wastage & Supplier routers.

Wastage:
  GET  /api/wastage              — list (optional date range / item filter)
  POST /api/wastage              — create entry (admin, staff)
  GET  /api/wastage/summary      — total qty & ₹ for today / week / month

Suppliers:
  GET    /api/suppliers          — list (admin, viewer)
  POST   /api/suppliers          — create (admin)
  PATCH  /api/suppliers/{id}     — update (admin)
  DELETE /api/suppliers/{id}     — soft-delete (admin)

  POST /api/purchases already accepts supplier_id (added as optional field).
"""
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException

from core.db import db
from core.security import get_current_user, require_roles
from core.utils import now_utc, iso, today_ist
from models.wastage import WastageIn, SupplierIn, SupplierUpdateIn, WASTAGE_REASONS

router = APIRouter()


# ── Wastage ───────────────────────────────────────────────────────────────
@router.get("/wastage")
async def list_wastage(
    start: Optional[str] = None,
    end:   Optional[str] = None,
    item_id: Optional[str] = None,
    user=Depends(get_current_user),
):
    q: dict = {}
    if start: q.setdefault("date", {})["$gte"] = start
    if end:   q.setdefault("date", {})["$lte"] = end
    if item_id: q["item_id"] = item_id
    docs = await db.wastage.find(q, {"_id": 0}).sort("created_at", -1).to_list(2000)
    # enrich with item name
    items = {i["id"]: i for i in await db.items.find({}, {"_id": 0}).to_list(2000)}
    for d in docs:
        it = items.get(d["item_id"], {})
        d["item_name"] = it.get("name", "Unknown")
        d["unit"]      = it.get("unit", "")
    return docs


@router.post("/wastage")
async def create_wastage(payload: WastageIn,
                         user=Depends(require_roles("admin", "staff"))):
    item = await db.items.find_one({"id": payload.item_id})
    if not item:
        raise HTTPException(400, "Item not found")
    # Best-effort cost estimation: last purchase price × quantity
    last = await db.purchases.find_one(
        {"item_id": payload.item_id, "is_void": {"$ne": True}},
        sort=[("date", -1)],
        projection={"price_per_unit": 1},
    )
    cost_estimate = round(payload.quantity * (last.get("price_per_unit", 0) if last else 0), 2)
    doc = {
        "id":         str(uuid.uuid4()),
        "item_id":    payload.item_id,
        "date":       payload.date,
        "quantity":   float(payload.quantity),
        "reason":     payload.reason,
        "notes":      payload.notes or "",
        "cost_estimate": cost_estimate,
        "created_by": user["id"],
        "created_by_name": user["name"],
        "created_at": iso(now_utc()),
    }
    await db.wastage.insert_one(doc)
    doc.pop("_id", None)
    doc["item_name"] = item["name"]
    doc["unit"]      = item["unit"]
    return doc


@router.get("/wastage/summary")
async def wastage_summary(user=Depends(get_current_user)):
    """Aggregate wastage totals — today / week / month / all-time."""
    today = today_ist().isoformat()
    week_start  = (today_ist().toordinal() - 6)
    from datetime import date as _date
    week_start_s  = _date.fromordinal(week_start).isoformat()
    month_start_s = today_ist().replace(day=1).isoformat()

    async def _agg(date_match):
        match = {}
        if date_match:
            match["date"] = date_match
        agg = await db.wastage.aggregate([
            {"$match": match},
            {"$group": {"_id": None,
                        "qty":   {"$sum": "$quantity"},
                        "cost":  {"$sum": "$cost_estimate"},
                        "count": {"$sum": 1}}},
        ]).to_list(1)
        return {"qty":   round(agg[0]["qty"], 3)    if agg else 0,
                "cost":  round(agg[0]["cost"], 2)   if agg else 0,
                "count": agg[0]["count"]            if agg else 0}

    today_t = await _agg({"$eq": today})
    week_t  = await _agg({"$gte": week_start_s,  "$lte": today})
    month_t = await _agg({"$gte": month_start_s, "$lte": today})
    all_t   = await _agg(None)
    return {"today": today_t, "week": week_t, "month": month_t, "all_time": all_t}


@router.get("/wastage/reasons")
async def wastage_reasons(user=Depends(get_current_user)):
    """Standard wastage reasons — used by the dropdown on the wastage form."""
    return WASTAGE_REASONS


# ── Suppliers ─────────────────────────────────────────────────────────────
@router.get("/suppliers")
async def list_suppliers(include_inactive: bool = False,
                         user=Depends(get_current_user)):
    q = {} if include_inactive else {"is_active": True}
    return await db.suppliers.find(q, {"_id": 0}).sort("name", 1).to_list(500)


@router.post("/suppliers")
async def create_supplier(payload: SupplierIn,
                          user=Depends(require_roles("admin"))):
    if await db.suppliers.find_one({"name": payload.name, "is_active": True}):
        raise HTTPException(400, "Supplier with this name already exists")
    doc = {
        "id":         str(uuid.uuid4()),
        "name":       payload.name,
        "phone":      payload.phone or "",
        "address":    payload.address or "",
        "items":      payload.items or "",
        "notes":      payload.notes or "",
        "is_active":  True,
        "created_at": iso(now_utc()),
        "updated_at": iso(now_utc()),
    }
    await db.suppliers.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.patch("/suppliers/{supplier_id}")
async def update_supplier(supplier_id: str, payload: SupplierUpdateIn,
                          user=Depends(require_roles("admin"))):
    update = {k: v for k, v in payload.dict().items() if v is not None}
    if "name" in update:
        dup = await db.suppliers.find_one(
            {"name": update["name"], "id": {"$ne": supplier_id}, "is_active": True})
        if dup:
            raise HTTPException(400, "Supplier with this name already exists")
    update["updated_at"] = iso(now_utc())
    res = await db.suppliers.update_one({"id": supplier_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Supplier not found")
    return await db.suppliers.find_one({"id": supplier_id}, {"_id": 0})


@router.delete("/suppliers/{supplier_id}")
async def delete_supplier(supplier_id: str,
                          user=Depends(require_roles("admin"))):
    """Soft-delete — keeps history intact for any purchases linked to this supplier."""
    res = await db.suppliers.update_one(
        {"id": supplier_id},
        {"$set": {"is_active": False, "updated_at": iso(now_utc())}}
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Supplier not found")
    return {"deleted": True}
