import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from core.db import db
from core.security import get_current_user, require_roles
from core.utils import now_utc, iso
from models.item import ItemIn, ItemUpdateIn, BulkReorderIn
from models.settings import CategoryIn, UnitIn, BusinessProfileIn, ExpenseCategoryIn

router = APIRouter()

# ── Items ─────────────────────────────────────────────────────────────────
@router.get("/items")
async def list_items(include_inactive: bool = True, user=Depends(get_current_user)):
    q = {} if include_inactive else {"is_active": True}
    return await db.items.find(q, {"_id": 0}).sort("name", 1).to_list(1000)

@router.post("/items")
async def create_item(payload: ItemIn, user=Depends(require_roles("admin"))):
    if await db.items.find_one({"name": payload.name}):
        raise HTTPException(400, "Item with this name already exists")
    doc = {
        "id": str(uuid.uuid4()), "name": payload.name,
        "category": payload.category, "unit": payload.unit,
        "reorder_level": float(payload.reorder_level), "is_active": True,
        "created_at": iso(now_utc()), "updated_at": iso(now_utc()),
    }
    await db.items.insert_one(doc)
    doc.pop("_id", None)
    return doc

@router.patch("/items/{item_id}")
async def update_item(item_id: str, payload: ItemUpdateIn,
                      user=Depends(require_roles("admin"))):
    update = {k: v for k, v in payload.dict().items() if v is not None}
    if "name" in update:
        dup = await db.items.find_one({"name": update["name"], "id": {"$ne": item_id}})
        if dup:
            raise HTTPException(400, "Item with this name already exists")
    update["updated_at"] = iso(now_utc())
    res = await db.items.update_one({"id": item_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Item not found")
    return await db.items.find_one({"id": item_id}, {"_id": 0})

@router.post("/items/bulk-reorder")
async def bulk_reorder(payload: BulkReorderIn, user=Depends(require_roles("admin"))):
    for u in payload.updates:
        await db.items.update_one(
            {"id": u.item_id},
            {"$set": {"reorder_level": float(u.reorder_level), "updated_at": iso(now_utc())}}
        )
    return {"updated": len(payload.updates)}

# ── Categories ────────────────────────────────────────────────────────────
@router.get("/categories")
async def list_categories(include_inactive: bool = False, user=Depends(get_current_user)):
    q = {} if include_inactive else {"is_active": True}
    return await db.categories.find(q, {"_id": 0}).sort("name", 1).to_list(200)

@router.post("/categories")
async def create_category(payload: CategoryIn, user=Depends(require_roles("admin"))):
    if await db.categories.find_one({"name": payload.name}):
        raise HTTPException(400, "Category already exists")
    doc = {"id": str(uuid.uuid4()), "name": payload.name,
           "is_active": True, "created_at": iso(now_utc())}
    await db.categories.insert_one(doc)
    doc.pop("_id", None)
    return doc

@router.patch("/categories/{cat_id}")
async def update_category(cat_id: str, payload: dict, user=Depends(require_roles("admin"))):
    existing = await db.categories.find_one({"id": cat_id})
    if not existing:
        raise HTTPException(404, "Category not found")
    if not payload.get("is_active", True):
        active_items = await db.items.find_one(
            {"category": existing["name"], "is_active": True})
        if active_items:
            raise HTTPException(400, "Cannot deactivate category with active items")
    update = {k: v for k, v in payload.items() if k in ("name", "is_active") and v is not None}
    res = await db.categories.update_one({"id": cat_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Category not found")
    return await db.categories.find_one({"id": cat_id}, {"_id": 0})

# ── Units ─────────────────────────────────────────────────────────────────
@router.get("/units")
async def list_units(include_inactive: bool = False, user=Depends(get_current_user)):
    q = {} if include_inactive else {"is_active": True}
    return await db.units.find(q, {"_id": 0}).sort("name", 1).to_list(200)

@router.post("/units")
async def create_unit(payload: UnitIn, user=Depends(require_roles("admin"))):
    if await db.units.find_one({"name": payload.name}):
        raise HTTPException(400, "Unit already exists")
    doc = {"id": str(uuid.uuid4()), "name": payload.name,
           "is_active": True, "created_at": iso(now_utc())}
    await db.units.insert_one(doc)
    doc.pop("_id", None)
    return doc

@router.patch("/units/{unit_id}")
async def update_unit(unit_id: str, payload: dict, user=Depends(require_roles("admin"))):
    update = {k: v for k, v in payload.items() if k in ("name", "is_active") and v is not None}
    res = await db.units.update_one({"id": unit_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Unit not found")
    return await db.units.find_one({"id": unit_id}, {"_id": 0})

# ── Business Profile ──────────────────────────────────────────────────────
@router.get("/business-profile")
async def get_business_profile():
    """Public endpoint — needed for login page to show business name"""
    doc = await db.business_profile.find_one({"key": "main"}, {"_id": 0})
    return doc or {}

@router.patch("/business-profile")
async def update_business_profile(payload: BusinessProfileIn,
                                   user=Depends(require_roles("admin"))):
    if payload.logo_base64 and len(payload.logo_base64) > 700_000:
        raise HTTPException(400, "Logo image too large. Maximum size is 500KB.")
    update = {k: v for k, v in payload.dict().items() if v is not None}
    update["updated_at"] = iso(now_utc())
    await db.business_profile.update_one({"key": "main"}, {"$set": update}, upsert=True)
    return await db.business_profile.find_one({"key": "main"}, {"_id": 0})

# ── Expense Categories ────────────────────────────────────────────────────
@router.get("/expense-categories")
async def list_expense_categories(include_inactive: bool = False,
                                   user=Depends(get_current_user)):
    q = {} if include_inactive else {"is_active": True}
    return await db.expense_categories.find(q, {"_id": 0}).sort("name", 1).to_list(200)

@router.post("/expense-categories")
async def create_expense_category(payload: ExpenseCategoryIn,
                                   user=Depends(require_roles("admin"))):
    if await db.expense_categories.find_one({"name": payload.name}):
        raise HTTPException(400, "Category already exists")
    doc = {"id": str(uuid.uuid4()), "name": payload.name,
           "is_active": True, "created_at": iso(now_utc())}
    await db.expense_categories.insert_one(doc)
    doc.pop("_id", None)
    return doc

@router.patch("/expense-categories/{cat_id}")
async def update_expense_category(cat_id: str, payload: dict,
                                   user=Depends(require_roles("admin"))):
    update = {k: v for k, v in payload.items() if k in ("name", "is_active") and v is not None}
    res = await db.expense_categories.update_one({"id": cat_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Category not found")
    return await db.expense_categories.find_one({"id": cat_id}, {"_id": 0})
