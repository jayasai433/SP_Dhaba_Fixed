import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends

from core.db import db
from core.security import get_current_user, require_roles
from core.utils import now_utc, iso
from models.salary import StaffIn, StaffUpdateIn, SalaryIn, SalaryPayIn

router = APIRouter()

# ── Staff ─────────────────────────────────────────────────────────────────
@router.get("/staff")
async def list_staff(include_inactive: bool = True, user=Depends(get_current_user)):
    q = {} if include_inactive else {"is_active": True}
    return await db.staff.find(q, {"_id": 0}).sort("name", 1).to_list(200)

@router.post("/staff")
async def create_staff(payload: StaffIn, user=Depends(require_roles("admin"))):
    if await db.staff.find_one({"name": payload.name}):
        raise HTTPException(400, "Staff with this name already exists")
    doc = {
        "id": str(uuid.uuid4()), "name": payload.name,
        "default_salary": float(payload.default_salary),
        "phone": payload.phone or "", "is_active": True,
        "created_at": iso(now_utc()),
    }
    await db.staff.insert_one(doc)
    doc.pop("_id", None)
    return doc

@router.patch("/staff/{staff_id}")
async def update_staff(staff_id: str, payload: StaffUpdateIn,
                        user=Depends(require_roles("admin"))):
    update = {k: v for k, v in payload.dict().items() if v is not None}
    res = await db.staff.update_one({"id": staff_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Staff not found")
    return await db.staff.find_one({"id": staff_id}, {"_id": 0})

# ── Salaries ──────────────────────────────────────────────────────────────
@router.get("/salaries")
async def list_salaries(
    month: Optional[str] = None, staff_id: Optional[str] = None,
    user=Depends(require_roles("admin", "viewer"))
):
    q = {}
    if month:    q["month"]    = month
    if staff_id: q["staff_id"] = staff_id
    docs      = await db.salaries.find(q, {"_id": 0}).sort([("month", -1), ("staff_id", 1)]).to_list(2000)
    staff_map = {s["id"]: s for s in await db.staff.find({}, {"_id": 0}).to_list(500)}
    for d in docs:
        d["staff_name"] = staff_map.get(d["staff_id"], {}).get("name", "Unknown")
    return docs

@router.post("/salaries")
async def create_salary(payload: SalaryIn, user=Depends(require_roles("admin"))):
    staff = await db.staff.find_one({"id": payload.staff_id})
    if not staff:
        raise HTTPException(400, "Staff not found")
    if await db.salaries.find_one({"staff_id": payload.staff_id, "month": payload.month}):
        raise HTTPException(409, "Salary already recorded for this staff for this month")
    net = round(payload.basic_salary - payload.advance_paid, 2)
    doc = {
        "id": str(uuid.uuid4()), "staff_id": payload.staff_id, "month": payload.month,
        "basic_salary": float(payload.basic_salary),
        "advance_paid": float(payload.advance_paid),
        "net_payable": net, "paid_date": None, "notes": payload.notes or "",
        "created_by": user["id"], "created_at": iso(now_utc()),
    }
    await db.salaries.insert_one(doc)
    doc.pop("_id", None)
    doc["staff_name"] = staff["name"]
    return doc

@router.post("/salaries/{salary_id}/pay")
async def mark_salary_paid(salary_id: str, payload: SalaryPayIn,
                            user=Depends(require_roles("admin"))):
    res = await db.salaries.update_one(
        {"id": salary_id}, {"$set": {"paid_date": payload.paid_date}})
    if res.matched_count == 0:
        raise HTTPException(404, "Salary record not found")
    return await db.salaries.find_one({"id": salary_id}, {"_id": 0})
