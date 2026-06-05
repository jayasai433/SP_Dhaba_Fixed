"""
Closing Stock Router — HTTP layer only.

Thin by design: no business logic here.
All logic lives in ClosingStockService (testable, reusable).

Routes:
  POST /closing-stock           — record physical count for one item
  GET  /closing-stock/{date}    — get all entries for a date
  GET  /closing-stock/{date}/summary — aggregate summary
  GET  /closing-stock/trend     — wastage trend over N days
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from core.security import get_current_user, require_roles
from models.closing_stock import ClosingStockIn, ClosingStockOut, DailyStockSummary
from services.inventory.closing_stock_service import ClosingStockService

router = APIRouter()

# Single instance — stateless service, safe to share
_service = ClosingStockService()


@router.post("/closing-stock", response_model=ClosingStockOut)
async def record_closing_stock(
    payload: ClosingStockIn,
    user=Depends(require_roles("admin", "staff")),
):
    """
    Record end-of-day physical shelf count for one item.
    Admin and staff can record. Viewer is read-only.
    Upserts — safe to re-submit if count was wrong.
    """
    return await _service.record(payload, user)


@router.get("/closing-stock/{date_str}", response_model=list)
async def get_closing_stock(
    date_str: str,
    user=Depends(get_current_user),
):
    """Get all physical counts recorded for a specific date."""
    return await _service.get_by_date(date_str)


@router.get("/closing-stock/{date_str}/summary", response_model=DailyStockSummary)
async def get_closing_stock_summary(
    date_str: str,
    user=Depends(require_roles("admin", "viewer")),
):
    """
    Aggregate wastage summary for a date.
    Includes: items counted, total consumed, variance, estimated wastage cost.
    Admin and viewer can access (for dashboard).
    """
    return await _service.get_summary(date_str)


@router.get("/closing-stock-trend")
async def get_wastage_trend(
    days: int = Query(default=30, ge=7, le=365),
    user=Depends(require_roles("admin", "viewer")),
):
    """
    Wastage trend over the last N days (7-365).
    Used in P&L and inventory analytics dashboard.
    """
    return await _service.get_wastage_trend(days)
