"""
consumption.py — Purchase-frequency based consumption rate tracker.

Algorithm:
  1. Fetch last N purchases of an item (rolling 30-day window)
  2. Calculate gap in days between consecutive purchases
  3. Use weighted average (recent gaps weighted more)
  4. Estimate daily consumption = last_quantity / avg_gap
  5. Estimate days remaining = last_quantity / daily_rate
  6. Predict reorder date = last_purchase_date + avg_gap

Why weighted average?
  Simple average treats a 3-month-old purchase the same as yesterday's.
  Weighted average gives 2x weight to recent purchases — more accurate
  for businesses with changing consumption patterns.

Minimum 2 purchases required — returns None if insufficient data.
"""

from datetime import date, timedelta
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase


def _weighted_avg_gap(gaps: list[float]) -> float:
    """
    Weighted average of gaps — recent gaps (end of list) weighted more.
    Weight = position index + 1 (so last gap has highest weight).
    """
    if not gaps:
        return 0.0
    weights = list(range(1, len(gaps) + 1))
    return sum(g * w for g, w in zip(gaps, weights)) / sum(weights)


def _confidence(n: int) -> str:
    """
    Confidence level based on number of data points.
    Industry standard: need at least 5 for reliable stats.
    """
    if n >= 10: return "high"
    if n >= 5:  return "medium"
    if n >= 2:  return "low"
    return "insufficient"


async def get_consumption_rates(
    db: AsyncIOMotorDatabase,
    item_ids: Optional[list[str]] = None
) -> dict[str, dict]:
    """
    Calculate consumption rates for all active items (or a subset).
    Returns a dict keyed by item_id.

    Each value:
    {
        "item_id": str,
        "item_name": str,
        "unit": str,
        "daily_rate": float,          # units consumed per day
        "avg_gap_days": float,        # avg days between purchases
        "last_purchase_date": str,    # YYYY-MM-DD
        "last_quantity": float,       # qty in last purchase
        "days_since_last": int,       # days since last purchase
        "est_days_remaining": float,  # estimated days of stock left
        "reorder_by": str,            # estimated reorder date YYYY-MM-DD
        "status": str,                # "ok" | "soon" | "urgent" | "overdue"
        "confidence": str,            # "high" | "medium" | "low" | "insufficient"
        "data_points": int,           # number of purchases used
    }
    """
    # Build item lookup
    item_filter = {"is_active": True}
    if item_ids:
        item_filter["id"] = {"$in": item_ids}

    items = await db.items.find(item_filter, {"_id": 0}).to_list(500)
    item_map = {i["id"]: i for i in items}

    results = {}
    today = date.today()

    for item_id, item in item_map.items():
        # Fetch last 30 purchases sorted oldest→newest
        purchases = await db.purchases.find(
            {"item_id": item_id, "is_void": {"$ne": True}},
            {"_id": 0, "date": 1, "quantity": 1}
        ).sort("date", 1).limit(30).to_list(30)

        n = len(purchases)
        confidence = _confidence(n)

        if n < 2:
            results[item_id] = {
                "item_id":           item_id,
                "item_name":         item["name"],
                "unit":              item.get("unit", ""),
                "confidence":        confidence,
                "data_points":       n,
                "daily_rate":        None,
                "avg_gap_days":      None,
                "last_purchase_date": purchases[-1]["date"] if n == 1 else None,
                "last_quantity":     purchases[-1]["quantity"] if n == 1 else None,
                "days_since_last":   None,
                "est_days_remaining": None,
                "reorder_by":        None,
                "status":            "insufficient_data",
            }
            continue

        # Calculate gaps between consecutive purchases
        gaps = []
        for i in range(1, n):
            d1 = date.fromisoformat(purchases[i - 1]["date"])
            d2 = date.fromisoformat(purchases[i]["date"])
            gap = (d2 - d1).days
            if gap > 0:  # skip same-day purchases
                gaps.append(float(gap))

        if not gaps:
            continue

        avg_gap     = _weighted_avg_gap(gaps)
        last_p      = purchases[-1]
        last_date   = date.fromisoformat(last_p["date"])
        last_qty    = float(last_p["quantity"])
        days_since  = (today - last_date).days

        # Daily consumption rate = last quantity / average gap
        daily_rate  = round(last_qty / avg_gap, 3) if avg_gap > 0 else 0.0

        # Estimated days remaining = last_qty - (days_since × daily_rate)
        consumed_since = daily_rate * days_since
        est_remaining  = round(max(last_qty - consumed_since, 0) / daily_rate, 1) if daily_rate > 0 else None

        # Reorder date = last purchase + avg gap
        reorder_date = last_date + timedelta(days=round(avg_gap))
        reorder_str  = reorder_date.isoformat()

        # Status based on days remaining
        if est_remaining is None:
            status = "unknown"
        elif est_remaining <= 0:
            status = "overdue"    # should have reordered already
        elif est_remaining <= 1:
            status = "urgent"     # reorder today
        elif est_remaining <= 3:
            status = "soon"       # reorder in next 3 days
        else:
            status = "ok"

        results[item_id] = {
            "item_id":            item_id,
            "item_name":          item["name"],
            "unit":               item.get("unit", ""),
            "confidence":         confidence,
            "data_points":        n,
            "daily_rate":         daily_rate,
            "avg_gap_days":       round(avg_gap, 1),
            "last_purchase_date": last_p["date"],
            "last_quantity":      last_qty,
            "days_since_last":    days_since,
            "est_days_remaining": est_remaining,
            "reorder_by":         reorder_str,
            "status":             status,
        }

    return results
