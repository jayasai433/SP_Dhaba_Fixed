"""
ConsumptionAnalytics — Statistical analysis of consumption patterns.

Single Responsibility: ONLY computes statistics. No alerts, no recommendations.

Extensible:
  - Add forecast_next_7_days() when Petpooja data is available
  - Add seasonal_adjustment() for weekend vs weekday patterns
  - Add dish_level_analytics() when recipe mapping is built
"""

import asyncio
import math
from datetime import date, timedelta
from typing import Dict, List, Optional

from core.db import db


class ItemStats:
    """
    Value object holding computed statistics for one item.
    Immutable by convention — computed once, read many times.
    """
    def __init__(
        self,
        item_id: str,
        item_name: str,
        unit: str,
        daily_consumptions: List[float],   # last N days of actual consumption
        closing_quantities: List[dict],    # [{date, qty}] for trend + idle detection
        last_purchase_price: float,
    ):
        self.item_id      = item_id
        self.item_name    = item_name
        self.unit         = unit
        self.last_price   = last_purchase_price
        self._consumptions = [c for c in daily_consumptions if c > 0]  # exclude zero days
        self._closings     = closing_quantities

    # ── Statistical properties ─────────────────────────────────────────

    @property
    def avg_daily_usage(self) -> float:
        if not self._consumptions:
            return 0.0
        return round(sum(self._consumptions) / len(self._consumptions), 3)

    @property
    def std_deviation(self) -> float:
        """Standard deviation of daily consumption — measures consistency."""
        if len(self._consumptions) < 2:
            return 0.0
        mean = self.avg_daily_usage
        variance = sum((x - mean) ** 2 for x in self._consumptions) / len(self._consumptions)
        return round(math.sqrt(variance), 3)

    @property
    def trend(self) -> str:
        """
        Compare last 7 days vs previous 7 days.
        Returns: 'up', 'down', 'stable'
        """
        if len(self._consumptions) < 7:
            return "stable"
        recent = self._consumptions[-7:]
        previous = self._consumptions[-14:-7] if len(self._consumptions) >= 14 else self._consumptions[:7]
        recent_avg = sum(recent) / len(recent)
        prev_avg = sum(previous) / len(previous)
        if prev_avg == 0:
            return "stable"
        change_pct = (recent_avg - prev_avg) / prev_avg * 100
        if change_pct > 10:
            return "up"
        if change_pct < -10:
            return "down"
        return "stable"

    @property
    def days_idle(self) -> int:
        """
        How many consecutive days has closing qty been unchanged?
        Indicates item sitting unused → expiry risk.
        """
        if len(self._closings) < 2:
            return 0
        count = 0
        sorted_closings = sorted(self._closings, key=lambda x: x["date"], reverse=True)
        ref_qty = sorted_closings[0]["qty"]
        for entry in sorted_closings[1:]:
            if abs(entry["qty"] - ref_qty) < 0.01:  # tolerance for float
                count += 1
            else:
                break
        return count

    @property
    def current_closing_qty(self) -> float:
        if not self._closings:
            return 0.0
        latest = max(self._closings, key=lambda x: x["date"])
        return latest["qty"]

    def to_dict(self) -> dict:
        return {
            "item_id":           self.item_id,
            "item_name":         self.item_name,
            "unit":              self.unit,
            "avg_daily_usage":   self.avg_daily_usage,
            "std_deviation":     self.std_deviation,
            "trend":             self.trend,
            "days_idle":         self.days_idle,
            "current_closing_qty": self.current_closing_qty,
            "last_price":        self.last_price,
            "data_points":       len(self._consumptions),
        }


class ConsumptionAnalytics:
    """
    Computes consumption statistics for all active items.

    Uses closing_stock collection as source of truth.
    Falls back gracefully when data is insufficient (< 7 days).

    Future extensions (don't modify — extend):
      - inject a ForecastStrategy for ML-based predictions
      - inject a SeasonalityAdjuster for weekend/holiday patterns
    """

    def __init__(self, lookback_days: int = 30):
        self.lookback_days = lookback_days

    async def compute_all(self) -> Dict[str, ItemStats]:
        """
        Compute stats for all active items in parallel.
        Returns: dict of item_id → ItemStats
        """
        items = await db.items.find(
            {"is_active": True}, {"_id": 0}
        ).to_list(2000)

        if not items:
            return {}

        # Fetch all closing stock data for the lookback period in one query
        start_date = (date.today() - timedelta(days=self.lookback_days)).isoformat()
        closing_docs = await db.closing_stock.find(
            {"date": {"$gte": start_date}},
            {"_id": 0, "item_id": 1, "date": 1, "consumed": 1, "closing_qty": 1}
        ).to_list(10000)

        # Group by item_id for O(1) lookup
        consumption_by_item: Dict[str, List[float]] = {}
        closings_by_item: Dict[str, List[dict]] = {}
        for doc in closing_docs:
            iid = doc["item_id"]
            consumption_by_item.setdefault(iid, []).append(doc["consumed"])
            closings_by_item.setdefault(iid, []).append(
                {"date": doc["date"], "qty": doc["closing_qty"]}
            )

        # Fetch last purchase prices in parallel
        price_tasks = [
            db.purchases.find_one(
                {"item_id": it["id"], "is_void": {"$ne": True}},
                sort=[("date", -1)],
                projection={"price_per_unit": 1}
            )
            for it in items
        ]
        prices = await asyncio.gather(*price_tasks)
        price_map = {
            it["id"]: (p.get("price_per_unit", 0) if p else 0)
            for it, p in zip(items, prices)
        }

        # Build ItemStats for each item
        stats = {}
        for item in items:
            iid = item["id"]
            stats[iid] = ItemStats(
                item_id=iid,
                item_name=item["name"],
                unit=item["unit"],
                daily_consumptions=consumption_by_item.get(iid, []),
                closing_quantities=closings_by_item.get(iid, []),
                last_purchase_price=price_map.get(iid, 0),
            )

        return stats

    async def compute_for_item(self, item_id: str) -> Optional[ItemStats]:
        """Compute stats for a single item — used in detail views."""
        all_stats = await self.compute_all()
        return all_stats.get(item_id)
