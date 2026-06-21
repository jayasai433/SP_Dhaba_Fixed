"""
insights.py — Consumption rate + Groq-powered smart reorder advice.

Endpoints:
  GET  /consumption-rates        — consumption stats for all items
  GET  /smart-reorder            — Groq AI reorder recommendations
  POST /smart-reorder/refresh    — force refresh Groq cache (admin only)
"""

import os
import time
import uuid
import httpx
import logging
from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from services.consumption import get_consumption_rates

router = APIRouter()

# ── Injected by server.py at startup ──────────────────────────────────────────
_db: AsyncIOMotorDatabase = None

def set_db(database):
    global _db
    _db = database

# ── Groq insight cache — 1 hour TTL ───────────────────────────────────────────
_reorder_cache: dict = {"text": None, "ts": 0}
_CACHE_TTL = 60 * 60  # 1 hour


# ── Auth dependency — imported from server at runtime ─────────────────────────
# Passed in via set_auth() to avoid circular imports
_require_auth = None
_require_admin = None

def set_auth(auth_fn, admin_fn):
    global _require_auth, _require_admin
    _require_auth = auth_fn
    _require_admin = admin_fn


def get_auth():
    return Depends(_require_auth)

def get_admin():
    return Depends(_require_admin)


# ─────────────────────────────────────────────────────────────────────────────
# GET /consumption-rates
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/consumption-rates")
async def consumption_rates(user=Depends(lambda: None)):
    rates = await get_consumption_rates(_db)

    # Sort: urgent/overdue first, then by days_remaining asc
    STATUS_ORDER = {"overdue": 0, "urgent": 1, "soon": 2, "ok": 3,
                    "unknown": 4, "insufficient_data": 5}
    sorted_rates = sorted(
        rates.values(),
        key=lambda x: (
            STATUS_ORDER.get(x["status"], 9),
            x.get("est_days_remaining") or 999
        )
    )
    return {"rates": sorted_rates, "total": len(sorted_rates)}


# ─────────────────────────────────────────────────────────────────────────────
# GET /smart-reorder — Groq-powered reorder recommendations
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/smart-reorder")
async def smart_reorder(user=Depends(lambda: None)):
    global _reorder_cache

    # Return cached if fresh
    if _reorder_cache["text"] and (time.time() - _reorder_cache["ts"]) < _CACHE_TTL:
        return {"insight": _reorder_cache["text"], "cached": True}

    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        return {"insight": None, "cached": False}

    try:
        rates = await get_consumption_rates(_db)

        # Only send actionable items to Groq — urgent, soon, overdue
        actionable = [
            r for r in rates.values()
            if r["status"] in ("urgent", "soon", "overdue")
            and r["confidence"] != "insufficient"
        ]

        ok_items = [
            r for r in rates.values()
            if r["status"] == "ok" and r.get("est_days_remaining")
        ]

        if not actionable and not ok_items:
            return {"insight": "Not enough purchase history yet to generate recommendations. Keep recording purchases!", "cached": False}

        # Build context for Groq
        lines = []
        if actionable:
            lines.append("ITEMS NEEDING ATTENTION:")
            for r in actionable[:8]:  # limit to top 8
                lines.append(
                    f"- {r['item_name']}: ~{r['est_days_remaining']} days remaining "
                    f"({r['daily_rate']} {r['unit']}/day, reorder by {r['reorder_by']})"
                )

        if ok_items:
            lines.append("\nITEMS WITH SUFFICIENT STOCK:")
            for r in sorted(ok_items, key=lambda x: x.get("est_days_remaining", 999))[:5]:
                lines.append(
                    f"- {r['item_name']}: ~{r['est_days_remaining']} days remaining"
                )

        context = "\n".join(lines)

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {groq_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.1-8b-instant",
                    "max_tokens": 250,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a practical inventory advisor for SP Royal Punjabi Family Dhaba, "
                                "an Indian roadside restaurant. Give sharp, actionable reorder advice in "
                                "2-4 sentences. Be specific — name items, mention quantities, suggest timing. "
                                "Write in plain English. No markdown, no bullet points, no greetings."
                            )
                        },
                        {
                            "role": "user",
                            "content": f"Here is our current stock situation based on purchase history:\n\n{context}\n\nWhat should we do?"
                        }
                    ]
                }
            )
        resp.raise_for_status()
        insight = resp.json()["choices"][0]["message"]["content"].strip()
        _reorder_cache = {"text": insight, "ts": time.time()}
        return {"insight": insight, "cached": False}

    except Exception as e:
        logging.warning(f"Smart reorder Groq call failed: {e}")
        return {"insight": None, "cached": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# POST /smart-reorder/refresh — force cache refresh (admin only)
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/smart-reorder/refresh")
async def refresh_smart_reorder(user=Depends(lambda: None)):
    global _reorder_cache
    _reorder_cache = {"text": None, "ts": 0}
    return {"message": "Cache cleared — next request will fetch fresh insight"}
