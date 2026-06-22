"""
insights.py — Consumption rate tracker + Groq smart reorder advice.
Registered in main.py under /api prefix.
"""
from __future__ import annotations
import os
import time
import logging
import httpx
from fastapi import APIRouter, Depends
from core.db import db
from core.security import get_current_user
from services.consumption import get_consumption_rates

router = APIRouter()

# ── Groq cache — 1 hour TTL ───────────────────────────────────────────────────
_reorder_cache: dict = {"text": None, "ts": 0}
_CACHE_TTL = 60 * 60  # 1 hour

STATUS_ORDER = {"overdue": 0, "urgent": 1, "soon": 2, "ok": 3,
                "unknown": 4, "insufficient_data": 5}


# ─────────────────────────────────────────────────────────────────────────────
# GET /consumption-rates
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/consumption-rates")
async def consumption_rates(user=Depends(get_current_user)):
    rates = await get_consumption_rates(db)
    sorted_rates = sorted(
        rates.values(),
        key=lambda x: (
            STATUS_ORDER.get(x["status"], 9),
            x.get("est_days_remaining") or 999
        )
    )
    return {"rates": sorted_rates, "total": len(sorted_rates)}


# ─────────────────────────────────────────────────────────────────────────────
# GET /smart-reorder — Groq-powered advice
# ─────────────────────────────────────────────────────────────────────────────
@router.get("/smart-reorder")
async def smart_reorder(user=Depends(get_current_user)):
    global _reorder_cache

    if _reorder_cache["text"] and (time.time() - _reorder_cache["ts"]) < _CACHE_TTL:
        return {"insight": _reorder_cache["text"], "cached": True}

    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        return {"insight": None, "cached": False}

    try:
        rates = await get_consumption_rates(db)

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
            return {
                "insight": "Not enough purchase history yet to generate recommendations. Keep recording purchases!",
                "cached": False
            }

        lines = []
        if actionable:
            lines.append("ITEMS NEEDING ATTENTION:")
            for r in actionable[:8]:
                lines.append(
                    f"- {r['item_name']}: ~{r['est_days_remaining']} days remaining "
                    f"({r['daily_rate']} {r['unit']}/day, reorder by {r['reorder_by']})"
                )
        if ok_items:
            lines.append("\nITEMS WITH SUFFICIENT STOCK:")
            for r in sorted(ok_items, key=lambda x: x.get("est_days_remaining") or 999)[:5]:
                lines.append(f"- {r['item_name']}: ~{r['est_days_remaining']} days remaining")

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
                            "content": f"Here is our current stock situation:\n\n{chr(10).join(lines)}\n\nWhat should we do?"
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
        return {"insight": None, "cached": False}


# ─────────────────────────────────────────────────────────────────────────────
# POST /smart-reorder/refresh — force cache clear
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/smart-reorder/refresh")
async def refresh_smart_reorder(user=Depends(get_current_user)):
    global _reorder_cache
    _reorder_cache = {"text": None, "ts": 0}
    return {"message": "Cache cleared — next request will fetch fresh insight"}
