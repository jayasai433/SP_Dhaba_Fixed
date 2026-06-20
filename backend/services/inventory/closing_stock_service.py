"""
Closing Stock Service — Business Logic Layer.

Architecture:
  - Repository Pattern: all DB access through this service, not from router
  - Single Responsibility: computes consumed/variance, does NOT handle HTTP
  - Open for extension: add WastageCalculator, ForecastService in future

Usage:
  from services.inventory.closing_stock_service import ClosingStockService
  svc = ClosingStockService()
  result = await svc.record(payload, user)
  summary = await svc.get_summary(date_str)
"""

import uuid
from datetime import date, timedelta
from typing import List, Optional

from core.db import db
from core.utils import now_utc, iso, today_ist
from models.closing_stock import ClosingStockIn, ClosingStockOut, DailyStockSummary

# Wastage threshold — flag if actual consumption exceeds recorded usage by >10%
WASTAGE_THRESHOLD_PCT = 10.0


class ClosingStockService:
    """
    Manages daily physical stock counts and computes:
      - consumed   = opening + purchased - closing
      - variance   = consumed - manual_usage (discrepancy indicator)
      - wastage    = flagged when variance exceeds threshold

    Future extensions (don't modify this class, extend it):
      - DishMappingService: expected_consumption from menu items sold
      - ForecastService:    predicted_consumption from 30-day average
      - AlertService:       WhatsApp alert when wastage_flag=True
    """

    # ── Public API ─────────────────────────────────────────────────────────

    async def record(self, payload: ClosingStockIn, user: dict) -> ClosingStockOut:
        """
        Record end-of-day physical stock count for one item.
        Computes all derived fields server-side.
        Upserts (one record per item per date).
        """
        item = await self._get_item(payload.item_id)
        opening     = await self._get_opening_qty(payload.item_id, payload.date)
        purchased   = await self._get_purchased_today(payload.item_id, payload.date)
        manual_usage = await self._get_manual_usage(payload.item_id, payload.date)

        consumed     = round(opening + purchased - payload.closing_qty, 3)
        variance     = round(consumed - manual_usage, 3)
        variance_pct = round((variance / consumed * 100) if consumed > 0 else 0, 1)
        wastage_flag = variance_pct > WASTAGE_THRESHOLD_PCT

        record = {
            "id":              f"cs-{uuid.uuid4().hex[:12]}",
            "date":            payload.date,
            "item_id":         payload.item_id,
            "item_name":       item["name"],
            "unit":            item["unit"],
            "closing_qty":     payload.closing_qty,
            "opening_qty":     opening,
            "purchased_today": purchased,
            "consumed":        consumed,
            "manual_usage":    manual_usage,
            "variance":        variance,
            "variance_pct":    variance_pct,
            "wastage_flag":    wastage_flag,
            "notes":           payload.notes or "",
            "recorded_by":     user["name"],
            "recorded_at":     iso(now_utc()),
        }

        # Upsert — one record per item per date
        await db.closing_stock.update_one(
            {"item_id": payload.item_id, "date": payload.date},
            {"$set": record},
            upsert=True,
        )
        return ClosingStockOut(**record)

    async def get_by_date(self, date_str: str) -> List[ClosingStockOut]:
        """Get all closing stock entries for a given date."""
        docs = await db.closing_stock.find(
            {"date": date_str}, {"_id": 0}
        ).to_list(2000)
        return [ClosingStockOut(**d) for d in docs]

    async def get_summary(self, date_str: str) -> DailyStockSummary:
        """
        Aggregate summary for dashboard.
        Extensible: add forecast_accuracy when ForecastService is ready.
        """
        import asyncio
        entries, total_items = await asyncio.gather(
            self.get_by_date(date_str),
            db.items.count_documents({"is_active": True}),
        )

        high_variance = [
            {"item": e.item_name, "variance_pct": e.variance_pct,
             "variance": e.variance, "unit": e.unit}
            for e in entries if e.wastage_flag
        ]

        # Estimate wastage cost (consumed × avg price)
        wastage_cost = await self._estimate_wastage_cost(entries)

        return DailyStockSummary(
            date=date_str,
            total_items=total_items,
            items_counted=len(entries),
            total_consumed=round(sum(e.consumed for e in entries), 3),
            total_variance=round(sum(e.variance for e in entries), 3),
            high_variance_items=high_variance,
            wastage_cost_est=wastage_cost,
        )

    async def get_wastage_trend(self, days: int = 30) -> List[dict]:
        """
        Wastage trend over N days — for analytics dashboard.
        Returns: [{date, wastage_cost_est, items_flagged}]
        Future: add forecast_loss when ML model is integrated.
        """
        end_dt   = today_ist()
        start_dt = end_dt - timedelta(days=days - 1)

        pipeline = [
            {"$match": {
                "date": {"$gte": start_dt.isoformat(), "$lte": end_dt.isoformat()}
            }},
            {"$group": {
                "_id": "$date",
                "items_flagged": {"$sum": {"$cond": ["$wastage_flag", 1, 0]}},
                "total_variance": {"$sum": "$variance"},
                "total_consumed": {"$sum": "$consumed"},
            }},
            {"$sort": {"_id": 1}},
        ]

        results = await db.closing_stock.aggregate(pipeline).to_list(days)
        return [
            {
                "date": r["_id"],
                "items_flagged": r["items_flagged"],
                "total_variance": round(r["total_variance"], 3),
                "total_consumed": round(r["total_consumed"], 3),
                "variance_pct": round(
                    r["total_variance"] / r["total_consumed"] * 100
                    if r["total_consumed"] > 0 else 0, 1
                ),
            }
            for r in results
        ]

    # ── Private helpers (Repository layer) ────────────────────────────────

    async def _get_item(self, item_id: str) -> dict:
        """Fetch item metadata. Raises 404 if not found."""
        from fastapi import HTTPException
        item = await db.items.find_one({"id": item_id}, {"_id": 0})
        if not item:
            raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
        return item

    async def _get_opening_qty(self, item_id: str, date_str: str) -> float:
        """
        Opening stock = previous day's closing stock.
        If no previous record, falls back to computed stock (purchases - usage).
        This graceful fallback means the feature works from day 1,
        even without historical closing stock data.
        """
        prev_date = (date.fromisoformat(date_str) - timedelta(days=1)).isoformat()

        # Try previous closing stock record first
        prev = await db.closing_stock.find_one(
            {"item_id": item_id, "date": prev_date}, {"closing_qty": 1}
        )
        if prev:
            return prev["closing_qty"]

        # Fallback: compute from purchases - usage (existing logic)
        return await self._compute_stock_from_history(item_id, prev_date)

    async def _compute_stock_from_history(self, item_id: str, up_to_date: str) -> float:
        """
        Fallback stock computation using existing purchase-usage logic.
        Wraps the existing UsageBasedStrategy without modifying it.
        """
        import asyncio
        pur_agg, use_agg = await asyncio.gather(
            db.purchases.aggregate([
                {"$match": {
                    "item_id": item_id, "is_void": {"$ne": True},
                    "date": {"$lte": up_to_date}
                }},
                {"$group": {"_id": None, "total": {"$sum": "$quantity"}}}
            ]).to_list(1),
            db.daily_usage.aggregate([
                {"$match": {
                    "item_id": item_id, "is_void": {"$ne": True},
                    "date": {"$lte": up_to_date}
                }},
                {"$group": {"_id": None, "total": {"$sum": "$quantity_used"}}}
            ]).to_list(1),
        )
        purchased = pur_agg[0]["total"] if pur_agg else 0
        used      = use_agg[0]["total"] if use_agg else 0
        return round(max(0, purchased - used), 3)

    async def _get_purchased_today(self, item_id: str, date_str: str) -> float:
        """Today's purchases for this item."""
        agg = await db.purchases.aggregate([
            {"$match": {
                "item_id": item_id, "is_void": {"$ne": True}, "date": date_str
            }},
            {"$group": {"_id": None, "total": {"$sum": "$quantity"}}}
        ]).to_list(1)
        return round(agg[0]["total"] if agg else 0, 3)

    async def _get_manual_usage(self, item_id: str, date_str: str) -> float:
        """Today's manual usage from DailyUsage for cross-checking."""
        agg = await db.daily_usage.aggregate([
            {"$match": {
                "item_id": item_id, "is_void": {"$ne": True}, "date": date_str
            }},
            {"$group": {"_id": None, "total": {"$sum": "$quantity_used"}}}
        ]).to_list(1)
        return round(agg[0]["total"] if agg else 0, 3)

    async def _estimate_wastage_cost(self, entries: list) -> float:
        """
        Estimate ₹ wastage = variance × avg_price_per_unit.
        Uses most recent purchase price as proxy.
        Future: use weighted average cost (WAC) for accuracy.
        """
        total_cost = 0.0
        for entry in entries:
            if entry.variance <= 0:
                continue
            last_purchase = await db.purchases.find_one(
                {"item_id": entry.item_id, "is_void": {"$ne": True}},
                sort=[("date", -1)],
                projection={"price_per_unit": 1},
            )
            if last_purchase:
                total_cost += entry.variance * last_purchase.get("price_per_unit", 0)
        return round(total_cost, 2)
