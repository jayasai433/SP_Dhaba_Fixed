"""
PurchaseRecommender — Suggests what to order tomorrow based on usage patterns.

Single Responsibility: ONLY recommends purchase quantities. No alerts, no cost calc.

Formula:
  recommended = (avg_daily_usage × lead_time_days) - current_closing_qty
  where lead_time_days = how many days ahead you want to stock for

Extensible:
  - Plug in Petpooja sales forecast → use predicted sales instead of avg
  - Plug in seasonal factors → order more on weekends
  - Plug in supplier MOQ (minimum order quantity) constraints
"""

from typing import List, Dict
from dataclasses import dataclass

from services.inventory.analytics import ItemStats


@dataclass
class RecommendedOrder:
    """Value object — one purchase recommendation per item."""
    item_id:          str
    item_name:        str
    unit:             str
    current_stock:    float
    avg_daily_usage:  float
    recommended_qty:  float    # how much to order
    days_stock_after: float    # days of stock after ordering
    estimated_cost:   float    # approx ₹ cost of order
    urgency:          str      # 'high', 'medium', 'low'
    reason:           str      # human-readable explanation

    def to_dict(self) -> dict:
        return {
            "item_id":          self.item_id,
            "item_name":        self.item_name,
            "unit":             self.unit,
            "current_stock":    self.current_stock,
            "avg_daily_usage":  self.avg_daily_usage,
            "recommended_qty":  self.recommended_qty,
            "days_stock_after": self.days_stock_after,
            "estimated_cost":   self.estimated_cost,
            "urgency":          self.urgency,
            "reason":           self.reason,
        }


class PurchaseRecommender:
    """
    Recommends purchase quantities for tomorrow's shopping.

    target_days: how many days of stock to maintain (default: 3)
    min_data_points: minimum history needed before making recommendations
    """

    def __init__(self, target_days: int = 3, min_data_points: int = 5):
        self.target_days      = target_days
        self.min_data_points  = min_data_points

    def recommend_all(
        self,
        stats_map: Dict[str, ItemStats],
    ) -> List[RecommendedOrder]:
        """
        Generate purchase recommendations for all items.
        Only recommends items with sufficient history and below target stock.
        """
        recommendations = []

        for item_id, stats in stats_map.items():
            rec = self._recommend_item(stats)
            if rec:
                recommendations.append(rec)

        # Sort by urgency: high first
        urgency_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda r: urgency_order.get(r.urgency, 3))
        return recommendations

    def _recommend_item(self, stats: ItemStats) -> RecommendedOrder | None:
        """Generate recommendation for a single item."""

        # Need minimum history to make reliable recommendations
        if stats.data_points < self.min_data_points:
            return None
        if stats.avg_daily_usage == 0:
            return None

        target_stock  = round(stats.avg_daily_usage * self.target_days, 3)
        current       = stats.current_closing_qty
        days_left     = round(current / stats.avg_daily_usage, 1)

        # Only recommend if below target
        if current >= target_stock:
            return None

        recommended = round(target_stock - current, 3)
        if recommended <= 0:
            return None

        estimated_cost = round(recommended * stats.last_price, 2)
        days_after     = round((current + recommended) / stats.avg_daily_usage, 1)

        # Urgency based on days of stock remaining
        if days_left < 1:
            urgency = "high"
            reason = (
                f"Only {days_left} day of stock left. "
                f"Risk of running out mid-service."
            )
        elif days_left < 2:
            urgency = "medium"
            reason = (
                f"{days_left} days of stock remaining at current usage rate of "
                f"{stats.avg_daily_usage} {stats.unit}/day."
            )
        else:
            urgency = "low"
            reason = (
                f"Stock below {self.target_days}-day target. "
                f"Order when convenient."
            )

        return RecommendedOrder(
            item_id=stats.item_id,
            item_name=stats.item_name,
            unit=stats.unit,
            current_stock=current,
            avg_daily_usage=stats.avg_daily_usage,
            recommended_qty=recommended,
            days_stock_after=days_after,
            estimated_cost=estimated_cost,
            urgency=urgency,
            reason=reason,
        )
