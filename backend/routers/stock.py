from fastapi import APIRouter, Depends, HTTPException

from core.security import get_current_user, require_roles
from services.stock import compute_stock, get_alerts, aggregate_dashboard_data

router = APIRouter()

@router.get("/stock")
async def get_stock(user=Depends(get_current_user)):
    try:
        return await compute_stock()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Stock data temporarily unavailable: {str(e)[:100]}")

@router.get("/alerts")
async def get_alerts_route(user=Depends(get_current_user)):
    try:
        return await get_alerts()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Alerts temporarily unavailable: {str(e)[:100]}")

@router.get("/dashboard")
async def dashboard(user=Depends(require_roles("admin", "viewer", "staff"))):
    try:
        return await aggregate_dashboard_data()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Dashboard temporarily unavailable: {str(e)[:100]}")
