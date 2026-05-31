from fastapi import APIRouter, HTTPException, Depends

from core.db import db
from core.security import require_roles
from core.utils import now_utc, iso
from models.whatsapp import (
    WhatsAppNumberIn, WhatsAppNumberUpdateIn,
    WhatsAppSettingsIn, WhatsAppTestIn,
)
from services.whatsapp import (
    _wa_send_to_number, _wa_broadcast, _wa_creds,
    job_morning_report, job_daily_report, job_no_sales_reminder,
)
from datetime import datetime
from core.config import IST
import uuid

router = APIRouter()

@router.get("/whatsapp/numbers")
async def list_wa_numbers(user=Depends(require_roles("admin"))):
    return await db.whatsapp_numbers.find({}, {"_id": 0}).sort("name", 1).to_list(100)

@router.post("/whatsapp/numbers")
async def create_wa_number(payload: WhatsAppNumberIn, user=Depends(require_roles("admin"))):
    if await db.whatsapp_numbers.find_one({"phone": payload.phone}):
        raise HTTPException(400, "Phone number already added")
    doc = {"id": str(uuid.uuid4()), "name": payload.name, "phone": payload.phone,
           "is_active": payload.is_active, "created_at": iso(now_utc())}
    await db.whatsapp_numbers.insert_one(doc)
    doc.pop("_id", None)
    return doc

@router.patch("/whatsapp/numbers/{nid}")
async def update_wa_number(nid: str, payload: WhatsAppNumberUpdateIn,
                            user=Depends(require_roles("admin"))):
    update = {k: v for k, v in payload.dict().items() if v is not None}
    res = await db.whatsapp_numbers.update_one({"id": nid}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Number not found")
    return await db.whatsapp_numbers.find_one({"id": nid}, {"_id": 0})

@router.delete("/whatsapp/numbers/{nid}")
async def delete_wa_number(nid: str, user=Depends(require_roles("admin"))):
    res = await db.whatsapp_numbers.delete_one({"id": nid})
    if res.deleted_count == 0:
        raise HTTPException(404, "Number not found")
    return {"ok": True}

@router.post("/whatsapp/test")
async def test_wa_number(payload: WhatsAppTestIn, user=Depends(require_roles("admin"))):
    n = await db.whatsapp_numbers.find_one({"id": payload.number_id})
    if not n:
        raise HTTPException(404, "Number not found")
    body = (f"✅ SP Royal Dhaba — Test Message\n"
            f"Sent to: {n['name']} ({n['phone']})\n"
            f"Time: {datetime.now(IST).strftime('%d-%b-%Y %H:%M IST')}\n"
            f"— SP Royal Ops Manager")
    await _wa_send_to_number(n["phone"], body, "test")
    last = await db.notifications.find_one(
        {"to": n["phone"], "type": "test"}, {"_id": 0}, sort=[("created_at", -1)])
    return {"ok": True, "status": last.get("status") if last else "unknown",
            "log_only": not all(_wa_creds())}

@router.get("/whatsapp/settings")
async def get_wa_settings(user=Depends(require_roles("admin"))):
    return await db.whatsapp_settings.find_one({"key": "main"}, {"_id": 0}) or {}

@router.patch("/whatsapp/settings")
async def update_wa_settings(payload: WhatsAppSettingsIn, user=Depends(require_roles("admin"))):
    update = {k: v for k, v in payload.dict().items() if v is not None}
    update["updated_at"] = iso(now_utc())
    await db.whatsapp_settings.update_one({"key": "main"}, {"$set": update}, upsert=True)
    return await db.whatsapp_settings.find_one({"key": "main"}, {"_id": 0})

@router.get("/whatsapp/log")
async def list_wa_log(limit: int = 100, user=Depends(require_roles("admin"))):
    return await db.notifications.find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)

@router.post("/whatsapp/retry/{notif_id}")
async def retry_wa_notification(notif_id: str, user=Depends(require_roles("admin"))):
    n = await db.notifications.find_one({"id": notif_id})
    if not n:
        raise HTTPException(404, "Notification not found")
    await _wa_send_to_number(n["to"], n["body"], n["type"] + "_retry")
    return {"ok": True}

@router.post("/whatsapp/run-job/{job_name}")
async def run_job(job_name: str, user=Depends(require_roles("admin"))):
    jobs = {
        "morning_report":    job_morning_report,
        "daily_report":      job_daily_report,
        "no_sales_reminder": job_no_sales_reminder,
    }
    if job_name not in jobs:
        raise HTTPException(404, f"Job '{job_name}' not found")
    await jobs[job_name]()
    return {"ok": True, "job": job_name}
