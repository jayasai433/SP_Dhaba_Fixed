"""
Duplicate-entry guard. Blocks re-submissions of the exact same purchase/expense
within a short window, protecting against double-taps and network retries.

Purely a UX safeguard. Not a business rule.
"""
from datetime import timedelta
from fastapi import HTTPException
from core.db import db
from core.utils import now_utc, iso

_WINDOW_SECONDS = 10


async def check_duplicate_purchase(item_id: str, date: str, quantity: float) -> None:
    window_start = iso(now_utc() - timedelta(seconds=_WINDOW_SECONDS))
    dup = await db.purchases.find_one({
        "item_id": item_id,
        "date": date,
        "quantity": quantity,
        "is_void": False,
        "created_at": {"$gte": window_start},
    })
    if dup:
        raise HTTPException(
            409,
            "Duplicate detected. Same item and quantity was logged in the last few seconds.",
        )


async def check_duplicate_expense(date: str, category: str, amount: float) -> None:
    window_start = iso(now_utc() - timedelta(seconds=_WINDOW_SECONDS))
    dup = await db.expenses.find_one({
        "date": date,
        "category": category,
        "amount": amount,
        "is_void": False,
        "created_at": {"$gte": window_start},
    })
    if dup:
        raise HTTPException(
            409,
            "Duplicate detected. Same category and amount was logged in the last few seconds.",
        )
