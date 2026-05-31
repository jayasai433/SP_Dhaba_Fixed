import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from core.db import db
from core.security import get_current_user, require_roles
from core.utils import now_utc, iso
from models.transaction import ExpenseIn, VoidIn
from services.duplicate import check_duplicate_expense
from services.void import void_entry

router = APIRouter()

@router.get("/expenses")
async def list_expenses(
    start: Optional[str] = None, end: Optional[str] = None,
    category: Optional[str] = None, user=Depends(get_current_user)
):
    q = {}
    if start:    q.setdefault("date", {})["$gte"] = start
    if end:      q.setdefault("date", {})["$lte"] = end
    if category: q["category"] = category
    if user["role"] == "staff":
        q["created_by"] = user["id"]
    q["is_void"] = {"$ne": True}
    return await db.expenses.find(q, {"_id": 0}).sort("created_at", -1).to_list(2000)

@router.post("/expenses")
async def create_expense(payload: ExpenseIn, user=Depends(require_roles("admin", "staff"))):
    cat = await db.expense_categories.find_one({"name": payload.category, "is_active": True})
    if not cat:
        raise HTTPException(400, "Invalid or inactive expense category")
    await check_duplicate_expense(payload.date, payload.category, float(payload.amount))
    doc = {
        "id": str(uuid.uuid4()), "date": payload.date,
        "category": payload.category, "description": payload.description or "",
        "amount": float(payload.amount),
        "created_by": user["id"], "created_by_name": user["name"],
        "created_at": iso(now_utc()),
        "is_void": False, "voided_by": None, "voided_at": None, "void_reason": None,
    }
    await db.expenses.insert_one(doc)
    doc.pop("_id", None)
    return doc

@router.patch("/expenses/{expense_id}/void")
async def void_expense(expense_id: str, payload: VoidIn, user=Depends(get_current_user)):
    return await void_entry(db.expenses, expense_id, payload.reason, user)
