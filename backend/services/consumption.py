"""
consumption.py — Purchase-frequency based consumption rate tracker.

Correct Algorithm:
  When you buy item X on Day 7 after buying it on Day 1:
  - The qty you bought on Day 1 lasted 6 days
  - Daily consumption = Day1_qty / 6 days
  - After buying on Day 7 (new qty), estimate remaining:
    remaining = Day7_qty - (days_since_Day7 × daily_rate)

  Why previous qty, not current?
  Because the gap between purchases tells us how fast the PREVIOUS
  batch was consumed. The current batch is what we just bought.

  Weighted average: recent consumption rates weighted more than old.
  Minimum 2 purchases required.
"""
from __future__ import annotations
from datetime import date, timedelta
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase


def _weighted_avg(values: list, weights: list) -> float:
    """Weighted average — higher weight = more influence."""
    if not values:
        return 0.0
    total_weight = sum(weights)
    if total_weight == 0:
        return sum(values) / len(values)
    return sum(v * w for v, w in zip(values, weights)) / total_weight


def _confidence(n: int) -> str:
    if n >= 10: return "high"
    if n >= 5:  return "medium"
    if n >= 2:  return "low"
    return "insufficient"


async def get_consumption_rates(
    db: AsyncIOMotorDatabase,
    item_ids: Optional[list] = None
) -> dict:
    """
    Calculate consumption rates for all active items.
    Returns dict keyed by item_id.
    """
    item_filter = {"is_active": True}
    if item_ids:
        item_filter["id"] = {"$in": item_ids}

    items = await db.items.find(item_filter, {"_id": 0}).to_list(500)
    item_map = {i["id"]: i for i in items}

    results = {}
    today = date.today()

    for item_id, item in item_map.items():
        # Fetch purchases sorted oldest → newest
        purchases = await db.purchases.find(
            {"item_id": item_id, "is_void": {"$ne": True}},
            {"_id": 0, "date": 1, "quantity": 1}
        ).sort("date", 1).limit(30).to_list(30)

        n = len(purchases)
        confidence = _confidence(n)

        if n < 2:
            results[item_id] = {
                "item_id":            item_id,
                "item_name":          item["name"],
                "unit":               item.get("unit", ""),
                "confidence":         confidence,
                "data_points":        n,
                "daily_rate":         None,
                "avg_gap_days":       None,
                "last_purchase_date": purchases[-1]["date"] if n == 1 else None,
                "last_quantity":      purchases[-1]["quantity"] if n == 1 else None,
                "days_since_last":    None,
                "est_days_remaining": None,
                "reorder_by":         None,
                "status":             "insufficient_data",
            }
            continue

        # ── Calculate consumption rates between consecutive purchases ──────────
        # Rate = previous_qty / gap_days (how fast previous batch was consumed)
        daily_rates = []
        gaps        = []

        for i in range(1, n):
            prev = purchases[i - 1]
            curr = purchases[i]

            d_prev = date.fromisoformat(prev["date"])
            d_curr = date.fromisoformat(curr["date"])
            gap    = (d_curr - d_prev).days

            if gap <= 0:
                continue  # same day purchases — skip

            # Previous batch qty consumed over gap days
            rate = float(prev["quantity"]) / gap
            daily_rates.append(rate)
            gaps.append(gap)

        if not daily_rates:
            continue

        # Weighted average — recent rates weighted more (index = weight)
        weights     = list(range(1, len(daily_rates) + 1))
        avg_rate    = _weighted_avg(daily_rates, weights)
        avg_gap     = _weighted_avg(gaps, weights)

        last_p          = purchases[-1]
        last_date       = date.fromisoformat(last_p["date"])
        last_qty        = float(last_p["quantity"])
        days_since      = (today - last_date).days

        # Estimated remaining = last_qty - (days_since × avg_rate)
        consumed_since  = avg_rate * days_since
        est_remaining   = round(max(last_qty - consumed_since, 0), 2)

        # Days until stock runs out
        days_left = round(est_remaining / avg_rate, 1) if avg_rate > 0 else None

        # Reorder date = last purchase date + avg gap between purchases
        reorder_date = last_date + timedelta(days=round(avg_gap))
        reorder_str  = reorder_date.isoformat()

        # Status
        if days_left is None:
            status = "unknown"
        elif est_remaining <= 0:
            status = "overdue"
        elif days_left <= 1:
            status = "urgent"
        elif days_left <= 3:
            status = "soon"
        else:
            status = "ok"

        results[item_id] = {
            "item_id":            item_id,
            "item_name":          item["name"],
            "unit":               item.get("unit", ""),
            "confidence":         confidence,
            "data_points":        n,
            "daily_rate":         round(avg_rate, 3),
            "avg_gap_days":       round(avg_gap, 1),
            "last_purchase_date": last_p["date"],
            "last_quantity":      last_qty,
            "days_since_last":    days_since,
            "est_remaining":      est_remaining,
            "est_days_remaining": days_left,
            "reorder_by":         reorder_str,
            "status":             status,
        }

    return results
