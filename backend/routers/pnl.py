from typing import Optional
from fastapi import APIRouter, Depends, HTTPException

from core.security import require_roles
from services.pnl import compute_pnl, compute_pnl_trend, export_pnl_pdf, _date_range_for_period

router = APIRouter()

@router.get("/pnl")
async def get_pnl(
    period: str = "today", start: Optional[str] = None, end: Optional[str] = None,
    user=Depends(require_roles("admin", "viewer", "staff"))
):
    try:
        if start or end:
            return await compute_pnl(start, end)
        s, e = _date_range_for_period(period)
        return await compute_pnl(s, e)
    except Exception as ex:
        raise HTTPException(status_code=503, detail=f"P&L data temporarily unavailable: {str(ex)[:100]}")

@router.get("/pnl/trend")
async def pnl_trend(days: int = 30, user=Depends(require_roles("admin", "viewer", "staff"))):
    try:
        return await compute_pnl_trend(days)
    except Exception as ex:
        raise HTTPException(status_code=503, detail=f"P&L trend temporarily unavailable: {str(ex)[:100]}")

@router.get("/pnl/export")
async def export_pnl(period: str = "month", user=Depends(require_roles("admin", "viewer"))):
    try:
        return await export_pnl_pdf(period)
    except Exception as ex:
        raise HTTPException(status_code=503, detail=f"PDF export failed: {str(ex)[:100]}")
