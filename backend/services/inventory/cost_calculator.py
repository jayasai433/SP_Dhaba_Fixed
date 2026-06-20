"""
IngredientCostCalculator — Computes daily ingredient cost from closing stock data.

Single Responsibility: ONLY calculates costs. No alerts, no recommendations.

Formula:
  daily_cost = sum(consumed_today × last_purchase_price) for all items

Extensible:
  - Replace last_purchase_price with weighted_average_cost for FIFO accuracy
  - Add recipe_cost when dish mapping is available
  - Add cost_per_cover when customer count is tracked
"""

from datetime import date, timedelta
from typing import List, Dict
from dataclasses import dataclass

from core.db import db
from core.utils import today_ist


@dataclass
class ItemCost:
    """Cost breakdown for one item on one day."""
    item_id:      str
    item_name:    str
    unit:         str
    consumed:     float
    price_per_unit: float
    total_cost:   float
    vs_yesterday: float   # % change vs yesterday (0 if no data)
    vs_7day_avg:  float   # % change vs 7-day average (0 if no data)

    def to_dict(self) -> dict:
        return {
            "item_id":        self.item_id,
            "item_name":      self.item_name,
            "unit":           self.unit,
            "consumed":       self.consumed,
            "price_per_unit": self.price_per_unit,
            "total_cost":     self.total_cost,
            "vs_yesterday":   self.vs_yesterday,
            "vs_7day_avg":    self.vs_7day_avg,
        }


@dataclass
class DailyCostSummary:
    """Aggregate cost summary for one day."""
    date:             str
    total_cost:       float
    items:            List[ItemCost]
    vs_yesterday:     float     # % change in total cost vs yesterday
    vs_7day_avg:      float     # % change vs 7-day average
    highest_cost_item: str      # item that cost the most today
    potential_savings: float    # estimated savings if wastage was zero

    def to_dict(self) -> dict:
        return {
            "date":               self.date,
            "total_cost":         self.total_cost,
            "items":              [i.to_dict() for i in self.items],
            "vs_yesterday":       self.vs_yesterday,
            "vs_7day_avg":        self.vs_7day_avg,
            "highest_cost_item":  self.highest_cost_item,
            "potential_savings":  self.potential_savings,
        }


class IngredientCostCalculator:
    """
    Calculates daily ingredient cost from closing stock consumption data.

    Requires closing stock to be recorded for the date.
    Falls back gracefully to empty summary if no data.

    Future: inject a PricingStrategy to switch between:
      - LastPurchasePrice (current — simple)
      - WeightedAverageCost (accurate — needs purchase history)
      - StandardCost (for budgeting)
    """

    async def calculate_for_date(self, date_str: str) -> DailyCostSummary:
        """
        Calculate ingredient costs for a specific date.
        Uses last purchase price for each item as proxy for cost.
        """
        # Get all closing stock entries for this date
        closing_docs = await db.closing_stock.find(
            {"date": date_str},
            {"_id": 0}
        ).to_list(2000)

        if not closing_docs:
            return DailyCostSummary(
                date=date_str, total_cost=0, items=[],
                vs_yesterday=0, vs_7day_avg=0,
                highest_cost_item="No data",
                potential_savings=0,
            )

        # Get last purchase prices for all items in one query
        item_ids = [d["item_id"] for d in closing_docs]
        price_map = await self._get_last_prices(item_ids)

        # Compute yesterday and 7-day avg costs for comparison
        yesterday = (
            date.fromisoformat(date_str) - timedelta(days=1)
        ).isoformat()
        yesterday_total = await self._get_total_cost_for_date(yesterday, price_map)
        seven_day_avg   = await self._get_avg_cost_last_n_days(date_str, 7, price_map)

        # Build item costs
        item_costs: List[ItemCost] = []
        for doc in closing_docs:
            if doc.get("consumed", 0) <= 0:
                continue

            price   = price_map.get(doc["item_id"], 0)
            cost    = round(doc["consumed"] * price, 2)

            item_costs.append(ItemCost(
                item_id=doc["item_id"],
                item_name=doc["item_name"],
                unit=doc["unit"],
                consumed=doc["consumed"],
                price_per_unit=price,
                total_cost=cost,
                vs_yesterday=0,  # item-level comparison added in future
                vs_7day_avg=0,
            ))

        item_costs.sort(key=lambda x: x.total_cost, reverse=True)
        total_cost  = round(sum(i.total_cost for i in item_costs), 2)

        # Wastage cost = variance (unaccounted consumption) × price
        wastage_cost = round(sum(
            max(0, doc.get("variance", 0)) * price_map.get(doc["item_id"], 0)
            for doc in closing_docs
        ), 2)

        vs_yesterday = self._pct_change(yesterday_total, total_cost)
        vs_7day_avg  = self._pct_change(seven_day_avg, total_cost)

        return DailyCostSummary(
            date=date_str,
            total_cost=total_cost,
            items=item_costs,
            vs_yesterday=vs_yesterday,
            vs_7day_avg=vs_7day_avg,
            highest_cost_item=item_costs[0].item_name if item_costs else "None",
            potential_savings=wastage_cost,
        )

    async def get_cost_trend(self, days: int = 30) -> List[dict]:
        """
        Daily ingredient cost over N days — for trend chart.
        Returns: [{date, total_cost, potential_savings}]
        """
        end_dt   = today_ist()
        start_dt = end_dt - timedelta(days=days - 1)

        pipeline = [
            {"$match": {"date": {"$gte": start_dt.isoformat()}}},
            {"$lookup": {
                "from": "purchases",
                "localField": "item_id",
                "foreignField": "item_id",
                "as": "purchases"
            }},
            {"$group": {
                "_id": "$date",
                "total_consumed_cost": {"$sum": {
                    "$multiply": [
                        "$consumed",
                        {"$ifNull": [{"$arrayElemAt": ["$purchases.price_per_unit", -1]}, 0]}
                    ]
                }},
                "total_wastage_cost": {"$sum": {
                    "$multiply": [
                        {"$max": ["$variance", 0]},
                        {"$ifNull": [{"$arrayElemAt": ["$purchases.price_per_unit", -1]}, 0]}
                    ]
                }},
            }},
            {"$sort": {"_id": 1}},
        ]

        # Simpler version without $lookup for now
        # Get all closing stock docs and compute in Python
        docs = await db.closing_stock.find(
            {"date": {"$gte": start_dt.isoformat(), "$lte": end_dt.isoformat()}},
            {"_id": 0, "date": 1, "item_id": 1, "consumed": 1, "variance": 1}
        ).to_list(10000)

        # Get all relevant prices
        item_ids = list({d["item_id"] for d in docs})
        price_map = await self._get_last_prices(item_ids)

        # Group by date
        by_date: Dict[str, dict] = {}
        for doc in docs:
            d = doc["date"]
            price = price_map.get(doc["item_id"], 0)
            if d not in by_date:
                by_date[d] = {"total_cost": 0, "wastage_cost": 0}
            by_date[d]["total_cost"] += doc.get("consumed", 0) * price
            by_date[d]["wastage_cost"] += max(0, doc.get("variance", 0)) * price

        return [
            {
                "date": d,
                "total_cost": round(v["total_cost"], 2),
                "potential_savings": round(v["wastage_cost"], 2),
            }
            for d, v in sorted(by_date.items())
        ]

    # ── Private helpers ────────────────────────────────────────────────────

    async def _get_last_prices(self, item_ids: List[str]) -> Dict[str, float]:
        """Fetch last purchase price for each item. O(n) with single aggregation."""
        if not item_ids:
            return {}
        result = await db.purchases.aggregate([
            {"$match": {"item_id": {"$in": item_ids}, "is_void": {"$ne": True}}},
            {"$sort": {"date": -1}},
            {"$group": {"_id": "$item_id", "price": {"$first": "$price_per_unit"}}},
        ]).to_list(len(item_ids))
        return {r["_id"]: r["price"] for r in result}

    async def _get_total_cost_for_date(
        self, date_str: str, price_map: Dict[str, float]
    ) -> float:
        docs = await db.closing_stock.find(
            {"date": date_str}, {"_id": 0, "item_id": 1, "consumed": 1}
        ).to_list(2000)
        return round(
            sum(d["consumed"] * price_map.get(d["item_id"], 0) for d in docs), 2
        )

    async def _get_avg_cost_last_n_days(
        self, before_date: str, n: int, price_map: Dict[str, float]
    ) -> float:
        end = date.fromisoformat(before_date) - timedelta(days=1)
        start = end - timedelta(days=n - 1)
        docs = await db.closing_stock.find(
            {"date": {"$gte": start.isoformat(), "$lte": end.isoformat()}},
            {"_id": 0, "item_id": 1, "consumed": 1, "date": 1}
        ).to_list(10000)
        if not docs:
            return 0.0
        # Group by date and compute daily totals
        by_date: Dict[str, float] = {}
        for doc in docs:
            d = doc["date"]
            by_date[d] = by_date.get(d, 0) + doc["consumed"] * price_map.get(doc["item_id"], 0)
        return round(sum(by_date.values()) / len(by_date), 2) if by_date else 0.0

    @staticmethod
    def _pct_change(old: float, new: float) -> float:
        if old == 0:
            return 0.0
        return round((new - old) / old * 100, 1)
