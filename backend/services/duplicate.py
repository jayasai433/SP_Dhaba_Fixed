from datetime import timedelta
from fastapi import HTTPException
from core.db import db
from core.utils import now_utc, iso

_WINDOW_SECONDS = 10

async def check_duplicate_purchase(item_id: str, date: str, quantity: float) -> None:
    window_start = iso(now_utc() - timedelta(seconds=_WINDOW_SECONDS))
    dup = await db.purchases.find_one({
        "item_id":    item_id,
        "date":       date,
        "quantity":   quantity,
        "is_void":    False,
        "created_at": {"$gte": window_start},
    })
    if dup:
        raise HTTPException(
            409,
            "Duplicate entry detected — same item and quantity logged within the last 10 seconds.",
        )

async def check_duplicate_usage(item_id: str, date: str, quantity_used: float) -> None:
    window_start = iso(now_utc() - timedelta(seconds=_WINDOW_SECONDS))
    dup = await db.daily_usage.find_one({
        "item_id":       item_id,
        "date":          date,
        "quantity_used": quantity_used,
        "is_void":       False,
        "created_at":    {"$gte": window_start},
    })
    if dup:
        raise HTTPException(
            409,
            "Duplicate entry detected — same item and quantity logged within the last 10 seconds.",
        )

async def check_duplicate_expense(date: str, category: str, amount: float) -> None:
    window_start = iso(now_utc() - timedelta(seconds=_WINDOW_SECONDS))
    dup = await db.expenses.find_one({
        "date":       date,
        "category":   category,
        "amount":     amount,
        "is_void":    False,
        "created_at": {"$gte": window_start},
    })
    if dup:
        raise HTTPException(
            409,
            "Duplicate entry detected — same category and amount logged within the last 10 seconds.",
        )
