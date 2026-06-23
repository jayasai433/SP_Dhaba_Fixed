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
_consumption_cache: dict = {"data": None, "ts": 0}
_CONSUMPTION_CACHE_TTL = 60  # 60 seconds — fast enough for real-time, slow enough to not hammer DB

@router.get("/consumption-rates")
async def consumption_rates(user=Depends(get_current_user)):
    global _consumption_cache
    if _consumption_cache["data"] and (time.time() - _consumption_cache["ts"]) < _CONSUMPTION_CACHE_TTL:
        return _consumption_cache["data"]
    rates = await get_consumption_rates(db)
    sorted_rates = sorted(
        rates.values(),
        key=lambda x: (
            STATUS_ORDER.get(x["status"], 9),
            x.get("est_days_remaining") or 999
        )
    )
    result = {"rates": sorted_rates, "total": len(sorted_rates)}
    _consumption_cache = {"data": result, "ts": time.time()}
    return result


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
            # Let Groq write a warm welcome/reminder even with no stock data
            try:
                async with httpx.AsyncClient(timeout=8) as client:
                    resp = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                        json={
                            "model": "llama-3.1-8b-instant",
                            "max_tokens": 100,
                            "messages": [
                                {
                                    "role": "system",
                                    "content": (
                                        "You are a warm, encouraging business advisor for SP Royal Punjabi Family Dhaba. "
                                        "Write one friendly sentence reminding the team to start recording purchases "
                                        "so you can track stock and suggest reorders. Keep it warm and motivating. "
                                        "No markdown, no bullet points."
                                    )
                                },
                                {"role": "user", "content": "No purchase history recorded yet. Write a warm reminder."}
                            ]
                        }
                    )
                resp.raise_for_status()
                msg = resp.json()["choices"][0]["message"]["content"].strip()
                return {"insight": msg, "cached": False}
            except Exception:
                return {"insight": "Start recording your daily purchases — once you have data, I'll give you smart reorder advice tailored to SP Dhaba's consumption patterns.", "cached": False}

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
        logging.error(f"Smart reorder Groq call failed: {type(e).__name__}: {e}")
        return {"insight": None, "cached": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# POST /smart-reorder/refresh — force cache clear
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/smart-reorder/refresh")
async def refresh_smart_reorder(user=Depends(get_current_user)):
    global _reorder_cache
    _reorder_cache = {"text": None, "ts": 0}
    return {"message": "Cache cleared — next request will fetch fresh insight"}

# ─────────────────────────────────────────────────────────────────────────────
# GET /daily-digest — Groq morning briefing, cached until midnight IST
# ─────────────────────────────────────────────────────────────────────────────
import pytz as _pytz
from datetime import datetime as _dt

_digest_cache: dict = {"text": None, "date": None}

@router.get("/daily-digest")
async def daily_digest(user=Depends(get_current_user)):
    global _digest_cache

    ist      = _pytz.timezone("Asia/Kolkata")
    today    = _dt.now(ist).strftime("%Y-%m-%d")

    # Return cached if same day
    if _digest_cache["text"] and _digest_cache["date"] == today:
        return {"insight": _digest_cache["text"], "cached": True, "date": today}

    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        return {"insight": None, "cached": False}

    try:
        from services.pnl import compute_pnl, _date_range_for_period

        # Fetch today, yesterday, this week, this month in parallel
        import asyncio
        from datetime import timedelta
        yesterday = (_dt.now(ist).date() - timedelta(days=1)).isoformat()

        today_pnl, week_pnl, month_pnl, yesterday_pnl = await asyncio.gather(
            compute_pnl(today, today),
            compute_pnl(*_date_range_for_period("week")),
            compute_pnl(*_date_range_for_period("month")),
            compute_pnl(yesterday, yesterday),
        )

        # Get consumption/stock context for Groq
        from services.consumption import get_consumption_rates
        rates = await get_consumption_rates(db)
        urgent_items = [
            r for r in rates.values()
            if r["status"] in ("urgent", "overdue", "soon")
            and r.get("daily_rate")
        ]
        
        # Check if today has any entries
        no_sales_today     = today_pnl["revenue"] == 0
        no_purchases_today = today_pnl["cogs"] == 0
        no_data_at_all     = yesterday_pnl["revenue"] == 0 and week_pnl["revenue"] == 0

        stock_lines = ""
        if urgent_items:
            stock_lines = "\nSTOCK ALERTS:\n" + "\n".join(
                f"- {r['item_name']}: ~{r.get('est_remaining', 0)} {r['unit']} left "
                f"({r['status'].upper()})"
                for r in urgent_items[:5]
            )

        missing_lines = ""
        if no_sales_today:
            missing_lines += "\n- Today's SALES have not been entered yet"
        if no_purchases_today:
            missing_lines += "\n- Today's PURCHASES have not been entered yet"
        if missing_lines:
            missing_lines = "\nMISSING TODAY:" + missing_lines

        context = f"""
SP Royal Punjabi Family Dhaba — Morning Business Briefing
Date: {today}

YESTERDAY ({yesterday}):
- Sales: Rs.{yesterday_pnl['revenue']:,.0f}
- Purchases: Rs.{yesterday_pnl['cogs']:,.0f}
- Expenses: Rs.{yesterday_pnl['expenses']:,.0f}
- Net Profit: Rs.{yesterday_pnl['net_profit']:,.0f}
- Margin: {yesterday_pnl['margin_pct']}%

THIS WEEK:
- Sales: Rs.{week_pnl['revenue']:,.0f}
- Purchases: Rs.{week_pnl['cogs']:,.0f}
- Net Profit: Rs.{week_pnl['net_profit']:,.0f}
- Margin: {week_pnl['margin_pct']}%

THIS MONTH:
- Sales: Rs.{month_pnl['revenue']:,.0f}
- Purchases: Rs.{month_pnl['cogs']:,.0f}
- Net Profit: Rs.{month_pnl['net_profit']:,.0f}
- Margin: {month_pnl['margin_pct']}%
{stock_lines}
{missing_lines}
"""

        # If absolutely no data — let Groq write a warm welcome
        if no_data_at_all:
            try:
                async with httpx.AsyncClient(timeout=8) as client:
                    resp = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                        json={
                            "model": "llama-3.1-8b-instant",
                            "max_tokens": 120,
                            "messages": [
                                {
                                    "role": "system",
                                    "content": (
                                        "You are a warm business advisor for SP Royal Punjabi Family Dhaba, "
                                        "an Indian roadside restaurant. Write a short 2-sentence welcome message "
                                        "encouraging the team to start recording daily sales and purchases. "
                                        "Be warm, motivating, and specific to a dhaba. No markdown."
                                    )
                                },
                                {"role": "user", "content": "New dhaba app, no data recorded yet. Write a warm welcome."}
                            ]
                        }
                    )
                resp.raise_for_status()
                msg = resp.json()["choices"][0]["message"]["content"].strip()
                _digest_cache = {"text": msg, "date": today}
                return {"insight": msg, "cached": False, "date": today}
            except Exception:
                return {"insight": "Welcome to SP Dhaba Operations Manager! Start by recording today\'s sales and purchases — I\'ll give you daily business insights as your data grows.", "cached": False, "date": today}

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {groq_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "llama-3.1-8b-instant",
                    "max_tokens": 200,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a sharp business advisor for SP Royal Punjabi Family Dhaba, "
                                "an Indian roadside restaurant. Give a 2-3 sentence morning briefing. "
                                "If sales or purchases are missing for today, kindly remind Lokesh to enter them. "
                                "If stock items are urgent/overdue, flag them clearly. "
                                "Comment on profit margin and suggest one specific action. "
                                "Be warm but direct. Plain English only. No markdown, no bullet points."
                            )
                        },
                        {"role": "user", "content": context}
                    ]
                }
            )
        resp.raise_for_status()
        insight = resp.json()["choices"][0]["message"]["content"].strip()
        _digest_cache = {"text": insight, "date": today}
        return {"insight": insight, "cached": False, "date": today}

    except Exception as e:
        logging.error(f"Daily digest Groq call failed: {type(e).__name__}: {e}")
        return {"insight": None, "cached": False, "error": str(e)}

