import os
import uuid
import httpx
from datetime import datetime
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from core.db import db

async def _get_biz_name() -> str:
    """Fetch business name from DB — always current, never stale."""
    try:
        doc = await db.business_profile.find_one({"key": "main"}, {"name": 1})
        return doc.get("name", "SP Royal Dhaba") if doc else "SP Royal Dhaba"
    except Exception:
        return "SP Royal Dhaba"
from core.config import IST
from core.utils import now_utc, iso

GRAPH_VERSION = os.environ.get("WHATSAPP_GRAPH_VERSION", "v22.0")

# ── Credentials ───────────────────────────────────────────────────────────
def _wa_creds():
    return (
        os.environ.get("WHATSAPP_ACCESS_TOKEN", "").strip(),
        os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "").strip(),
    )

# ── Send to single number ─────────────────────────────────────────────────
async def _wa_send_to_number(phone: str, body: str, notif_type: str):
    token, pnid = _wa_creds()
    log_doc = {
        "id": str(uuid.uuid4()), "type": notif_type, "to": phone, "body": body,
        "status": "log_only", "error": None, "message_id": None,
        "created_at": iso(now_utc()),
    }
    if not token or not pnid:
        await db.notifications.insert_one({**log_doc})
        return
    url     = f"https://graph.facebook.com/{GRAPH_VERSION}/{pnid}/messages"
    payload = {"messaging_product": "whatsapp", "to": phone,
               "type": "text", "text": {"body": body}}
    try:
        async with httpx.AsyncClient(timeout=10) as cli:
            r = await cli.post(url, json=payload,
                               headers={"Authorization": f"Bearer {token}"})
        if r.status_code >= 400:
            log_doc["status"]  = "failed"
            log_doc["error"]   = f"HTTP {r.status_code}: {r.text[:300]}"
        else:
            log_doc["status"]     = "sent"
            log_doc["message_id"] = r.json().get("messages", [{}])[0].get("id")
    except Exception as exc:
        log_doc["status"] = "failed"
        log_doc["error"]  = str(exc)[:300]
    await db.notifications.insert_one({**log_doc})

# ── Broadcast to all active numbers ──────────────────────────────────────
async def _wa_broadcast(body: str, notif_type: str):
    nums = await db.whatsapp_numbers.find({"is_active": True}, {"_id": 0}).to_list(50)
    if not nums:
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "type": notif_type, "to": "(no active numbers)",
            "body": body, "status": "no_recipients", "error": None, "message_id": None,
            "created_at": iso(now_utc()),
        })
        return
    for n in nums:
        await _wa_send_to_number(n["phone"], body, notif_type)

# ── Purchase / stock notification triggers ────────────────────────────────
async def maybe_notify_after_purchase(item: dict, purchase_doc: dict):
    settings = await db.whatsapp_settings.find_one({"key": "main"}) or {}
    if settings.get("notify_large_purchase") and \
       purchase_doc["total_cost"] >= float(settings.get("large_purchase_threshold", 5000)):
        body = (f"💸 {biz} — Large Purchase\n"
                f"Item: {item['name']}\n"
                f"Qty: {purchase_doc['quantity']} {item['unit']}\n"
                f"Total: ₹{purchase_doc['total_cost']:,.2f}\n"
                f"By: {purchase_doc.get('created_by_name', '')}\n"
                f"— {biz} Ops Manager")
        await _wa_broadcast(body, "large_purchase")

async def check_stock_alerts_for_item(item_id: str):
    settings = await db.whatsapp_settings.find_one({"key": "main"}) or {}
    if not (settings.get("notify_out_of_stock") or settings.get("notify_low_stock")):
        return
    item = await db.items.find_one({"id": item_id})
    if not item or not item.get("is_active", True):
        return
    p_agg = await db.purchases.aggregate([
        {"$match": {"item_id": item_id}},
        {"$group": {"_id": None, "total": {"$sum": "$quantity"}}}
    ]).to_list(1)
    u_agg = await db.daily_usage.aggregate([
        {"$match": {"item_id": item_id}},
        {"$group": {"_id": None, "total": {"$sum": "$quantity_used"}}}
    ]).to_list(1)
    bought  = p_agg[0]["total"] if p_agg else 0
    used    = u_agg[0]["total"] if u_agg else 0
    left    = round(bought - used, 3)
    reorder = float(item.get("reorder_level", 0))
    if left <= 0 and settings.get("notify_out_of_stock"):
        body = (f"🔴 {biz} Alert\nItem: {item['name']}\n"
                f"Status: Out of Stock\nQty Left: 0 {item['unit']}\n"
                f"Action: Buy Today!\n— {biz} Ops Manager")
        await _wa_broadcast(body, "stock_out")
    elif 0 < left < reorder and settings.get("notify_low_stock"):
        body = (f"🟡 {biz} Alert\nItem: {item['name']}\n"
                f"Status: Low Stock\nQty Left: {left} {item['unit']} (reorder at {reorder})\n"
                f"— {biz} Ops Manager")
        await _wa_broadcast(body, "stock_low")

# ── Scheduled jobs ────────────────────────────────────────────────────────
async def job_morning_report():
    items = await db.items.find({"is_active": True}, {"_id": 0}).to_list(2000)
    p_agg = await db.purchases.aggregate([
        {"$group": {"_id": "$item_id", "total": {"$sum": "$quantity"}}}
    ]).to_list(5000)
    u_agg = await db.daily_usage.aggregate([
        {"$group": {"_id": "$item_id", "total": {"$sum": "$quantity_used"}}}
    ]).to_list(5000)
    p_map  = {x["_id"]: x["total"] for x in p_agg}
    u_map  = {x["_id"]: x["total"] for x in u_agg}
    out, low, in_s = [], [], 0
    for it in items:
        left    = p_map.get(it["id"], 0) - u_map.get(it["id"], 0)
        reorder = float(it.get("reorder_level", 0))
        if left <= 0:         out.append(it["name"])
        elif left < reorder:  low.append(it["name"])
        else:                 in_s += 1
    today_str = datetime.now(IST).strftime("%d-%b-%Y")
    biz = await _get_biz_name()
    body = (f"📦 {biz} Morning Stock Report\nDate: {today_str}\n\n"
            f"🔴 Out of Stock ({len(out)}): {', '.join(out) if out else 'None'}\n"
            f"🟡 Low Stock ({len(low)}): {', '.join(low) if low else 'None'}\n"
            f"🟢 In Stock: {in_s} items\n— {biz} Ops Manager")
    settings = await db.whatsapp_settings.find_one({"key": "main"}) or {}
    if settings.get("notify_morning_report"):
        await _wa_broadcast(body, "morning_report")

async def job_daily_report():
    today    = datetime.now(IST).strftime("%Y-%m-%d")
    sale     = await db.sales.find_one({"date": today})
    expenses = await db.expenses.find({"date": today}).to_list(500)
    exp_total = sum(e["amount"] for e in expenses)
    s_lunch   = sale["lunch_amount"]  if sale else 0
    s_dinner  = sale["dinner_amount"] if sale else 0
    s_other   = sale["other_amount"]  if sale else 0
    s_total   = sale["total_amount"]  if sale else 0
    purchases = await db.purchases.find({"date": today}).to_list(500)
    cogs      = sum(p["total_cost"] for p in purchases)
    net       = s_total - cogs - exp_total
    icon      = "✅" if net >= 0 else "❌"
    biz = await _get_biz_name()
    body = (f"💰 {biz} Daily Report\nDate: {datetime.now(IST).strftime('%d-%b-%Y')}\n\n"
            f"SALES\nLunch: ₹{s_lunch:,.2f}\nDinner: ₹{s_dinner:,.2f}\n"
            f"Other: ₹{s_other:,.2f}\nTotal: ₹{s_total:,.2f}\n\n"
            f"PURCHASES: ₹{cogs:,.2f}\nEXPENSES: ₹{exp_total:,.2f}\n"
            f"NET P&L: ₹{net:,.2f} {icon}\n— {biz} Ops Manager")
    settings = await db.whatsapp_settings.find_one({"key": "main"}) or {}
    if settings.get("notify_daily_report"):
        await _wa_broadcast(body, "daily_report")
    if net < 0 and settings.get("notify_daily_loss"):
        await _wa_broadcast(
            f"⚠️ {biz} Daily LOSS Alert\nDate: {datetime.now(IST).strftime('%d-%b-%Y')}\n"
            f"Net Loss: ₹{abs(net):,.2f}\n— {biz} Ops Manager", "daily_loss")

async def job_no_sales_reminder():
    today    = datetime.now(IST).strftime("%Y-%m-%d")
    sale     = await db.sales.find_one({"date": today})
    if sale:
        return
    settings = await db.whatsapp_settings.find_one({"key": "main"}) or {}
    if not settings.get("notify_no_sales_reminder"):
        return
    biz = await _get_biz_name()
    body = (f"⏰ {biz} Reminder\nNo sales entry recorded for "
            f"{datetime.now(IST).strftime('%d-%b-%Y')} yet.\n"
            f"Please log today's sales before closing.\n— {biz} Ops Manager")
    await _wa_broadcast(body, "no_sales_reminder")

# ── Scheduler lifecycle ───────────────────────────────────────────────────
_scheduler: Optional[AsyncIOScheduler] = None

def start_scheduler():
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone=IST)
    _scheduler.add_job(job_morning_report,    CronTrigger(hour=7,  minute=0,  timezone=IST))
    _scheduler.add_job(job_daily_report,      CronTrigger(hour=23, minute=30, timezone=IST))
    _scheduler.add_job(job_no_sales_reminder, CronTrigger(hour=21, minute=0,  timezone=IST))
    _scheduler.start()

def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
