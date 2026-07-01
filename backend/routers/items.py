"""
Item Master + Categories + Business Profile + Expense Categories.

Each item now supports multiple valid units with a conversion factor to a base
unit, so Sales/Purchases entry can pick eggs by piece, dozen, or tray. The
base_quantity persisted on each transaction lets a future stock module do all
math in a single canonical unit.
"""
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from core.db import db
from core.security import get_current_user, require_roles
from core.utils import now_utc, iso
from models.item import ItemIn, ItemUpdateIn
from models.settings import CategoryIn, ExpenseCategoryIn, BusinessProfileIn

router = APIRouter()


# Items --------------------------------------------------------------------
@router.get("/items")
async def list_items(
    include_inactive: bool = False,
    q: Optional[str] = None,
    user=Depends(get_current_user),
):
    """
    List items. Optional `q` does a case-insensitive prefix/contains match on name
    so the front-end can search on the fly from within the Sales/Purchases form.
    """
    query: dict = {} if include_inactive else {"is_active": True}
    if q:
        # simple contains, case-insensitive. Cheap on the 20-500 item scale we expect.
        import re as _re
        query["name"] = {"$regex": _re.escape(q), "$options": "i"}
    return await db.items.find(query, {"_id": 0}).sort("name", 1).to_list(1000)


@router.post("/items")
async def create_item(payload: ItemIn, user=Depends(require_roles("admin", "staff"))):
    """
    Create an item. Staff can create too so a new item can be added from within
    the Sales/Purchases form without leaving the flow.
    """
    existing = await db.items.find_one({"name": payload.name})
    if existing:
        raise HTTPException(400, "An item with this name already exists")
    now = iso(now_utc())
    doc = {
        "id": str(uuid.uuid4()),
        "name": payload.name,
        "category": payload.category or "",
        "base_unit": payload.base_unit,
        "default_price": float(payload.default_price or 0),
        "units": [u.model_dump() for u in payload.units],
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    await db.items.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.patch("/items/{item_id}")
async def update_item(item_id: str, payload: ItemUpdateIn,
                      user=Depends(require_roles("admin", "staff"))):
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "units" in update:
        update["units"] = [u for u in update["units"]]  # already dict via model_dump
    if "name" in update:
        dup = await db.items.find_one({"name": update["name"], "id": {"$ne": item_id}})
        if dup:
            raise HTTPException(400, "An item with this name already exists")
    update["updated_at"] = iso(now_utc())
    res = await db.items.update_one({"id": item_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Item not found")
    return await db.items.find_one({"id": item_id}, {"_id": 0})


@router.delete("/items/{item_id}")
async def delete_item(item_id: str, user=Depends(require_roles("admin"))):
    """Soft delete. Keeps history intact for existing purchases referencing this item."""
    res = await db.items.update_one(
        {"id": item_id},
        {"$set": {"is_active": False, "updated_at": iso(now_utc())}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Item not found")
    return {"deleted": True}


# Purchase Categories ------------------------------------------------------
@router.get("/categories")
async def list_categories(include_inactive: bool = False,
                          user=Depends(get_current_user)):
    q = {} if include_inactive else {"is_active": True}
    return await db.categories.find(q, {"_id": 0}).sort("name", 1).to_list(200)


@router.post("/categories")
async def create_category(payload: CategoryIn, user=Depends(require_roles("admin", "staff"))):
    if await db.categories.find_one({"name": payload.name}):
        raise HTTPException(400, "Category already exists")
    doc = {"id": str(uuid.uuid4()), "name": payload.name,
           "is_active": True, "created_at": iso(now_utc())}
    await db.categories.insert_one(doc)
    doc.pop("_id", None)
    return doc


# Expense Categories -------------------------------------------------------
@router.get("/expense-categories")
async def list_expense_categories(include_inactive: bool = False,
                                   user=Depends(get_current_user)):
    q = {} if include_inactive else {"is_active": True}
    return await db.expense_categories.find(q, {"_id": 0}).sort("name", 1).to_list(200)


@router.post("/expense-categories")
async def create_expense_category(payload: ExpenseCategoryIn,
                                   user=Depends(require_roles("admin", "staff"))):
    if await db.expense_categories.find_one({"name": payload.name}):
        raise HTTPException(400, "Category already exists")
    doc = {"id": str(uuid.uuid4()), "name": payload.name,
           "is_active": True, "created_at": iso(now_utc())}
    await db.expense_categories.insert_one(doc)
    doc.pop("_id", None)
    return doc


# Business Profile (public read, admin write) -----------------------------
@router.get("/business-profile")
async def get_business_profile():
    doc = await db.business_profile.find_one({"key": "main"}, {"_id": 0})
    return doc or {}


@router.patch("/business-profile")
async def update_business_profile(payload: BusinessProfileIn,
                                   user=Depends(require_roles("admin"))):
    if payload.logo_base64 and len(payload.logo_base64) > 700_000:
        raise HTTPException(400, "Logo image too large. Maximum size is 500KB.")
    update = {k: v for k, v in payload.model_dump().items() if v is not None}
    update["updated_at"] = iso(now_utc())
    await db.business_profile.update_one({"key": "main"}, {"$set": update}, upsert=True)
    return await db.business_profile.find_one({"key": "main"}, {"_id": 0})
