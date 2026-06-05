"""
Inventory Insights Router — HTTP layer only.

Thin by design: orchestrates services, no business logic here.
All logic lives in the respective service classes.

Routes:
  GET /inventory/insights          — full dashboard (alerts + recommendations + costs)
  GET /inventory/alerts            — anomaly alerts only
  GET /inventory/recommendations   — purchase recommendations only
  GET /inventory/cost/{date}       — ingredient cost for a date
  GET /inventory/cost-trend        — cost trend over N days
"""

from datetime import date as _date
from fastapi import APIRouter, Depends, Query

from core.security import get_current_user, require_roles
from services.inventory.analytics import ConsumptionAnalytics
from services.inventory.alerts import AlertEngine
from services.inventory.recommender import PurchaseRecommender
from services.inventory.cost_calculator import IngredientCostCalculator
from core.config import IST
from datetime import datetime

router = APIRouter()

# Service instances — stateless, safe to share across requests
_analytics    = ConsumptionAnalytics(lookback_days=30)
_alert_engine = AlertEngine()
_recommender  = PurchaseRecommender(target_days=3)
_cost_calc    = IngredientCostCalculator()


async def _get_today_consumptions() -> dict:
    """Helper: get today's actual consumption from closing stock."""
    from core.db import db
    today = datetime.now(IST).strftime("%Y-%m-%d")
    docs = await db.closing_stock.find(
        {"date": today}, {"_id": 0, "item_id": 1, "consumed": 1}
    ).to_list(2000)
    return {d["item_id"]: d["consumed"] for d in docs}


@router.get("/inventory/insights")
async def get_inventory_insights(
    user=Depends(require_roles("admin", "viewer")),
):
    """
    Full inventory intelligence dashboard.
    Combines alerts + recommendations + today's cost in one call.
    Admin and viewer can access (read-only data).
    """
    import asyncio

    # Run analytics and today's cost in parallel
    stats_map, today_consumptions, today_cost = await asyncio.gather(
        _analytics.compute_all(),
        _get_today_consumptions(),
        _cost_calc.calculate_for_date(datetime.now(IST).strftime("%Y-%m-%d")),
    )

    # These are CPU-bound (no await needed)
    alerts          = _alert_engine.evaluate_all(stats_map, today_consumptions)
    recommendations = _recommender.recommend_all(stats_map)

    return {
        "alerts":          [a.to_dict() for a in alerts],
        "recommendations": [r.to_dict() for r in recommendations],
        "today_cost":      today_cost.to_dict(),
        "summary": {
            "total_alerts":     len(alerts),
            "critical_alerts":  sum(1 for a in alerts if a.severity == "critical"),
            "total_recommendations": len(recommendations),
            "high_urgency_orders":   sum(1 for r in recommendations if r.urgency == "high"),
        },
    }


@router.get("/inventory/alerts")
async def get_inventory_alerts(
    user=Depends(require_roles("admin", "staff", "viewer")),
):
    """
    Anomaly alerts only.
    Staff can see alerts (so Lokesh knows what to watch during the day).
    """
    import asyncio
    stats_map, today_consumptions = await asyncio.gather(
        _analytics.compute_all(),
        _get_today_consumptions(),
    )
    alerts = _alert_engine.evaluate_all(stats_map, today_consumptions)
    return [a.to_dict() for a in alerts]


@router.get("/inventory/recommendations")
async def get_purchase_recommendations(
    user=Depends(require_roles("admin")),
):
    """
    Purchase recommendations — admin only (financial decisions).
    """
    stats_map = await _analytics.compute_all()
    recommendations = _recommender.recommend_all(stats_map)
    return [r.to_dict() for r in recommendations]


@router.get("/inventory/cost/{date_str}")
async def get_ingredient_cost(
    date_str: str,
    user=Depends(require_roles("admin", "viewer")),
):
    """Ingredient cost breakdown for a specific date."""
    summary = await _cost_calc.calculate_for_date(date_str)
    return summary.to_dict()


@router.get("/inventory/cost-trend")
async def get_cost_trend(
    days: int = Query(default=30, ge=7, le=90),
    user=Depends(require_roles("admin", "viewer")),
):
    """Ingredient cost trend over N days — for analytics chart."""
    return await _cost_calc.get_cost_trend(days)
