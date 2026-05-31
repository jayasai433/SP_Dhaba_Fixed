from fastapi import APIRouter, Depends

from core.security import get_current_user, require_roles
from services.stock import compute_stock, get_alerts, aggregate_dashboard_data

router = APIRouter()

@router.get("/stock")
async def get_stock(user=Depends(get_current_user)):
    return await compute_stock()

@router.get("/alerts")
async def get_alerts_route(user=Depends(get_current_user)):
    return await get_alerts()

@router.get("/dashboard")
async def dashboard(user=Depends(require_roles("admin", "viewer"))):
    return await aggregate_dashboard_data()
