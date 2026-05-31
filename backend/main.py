import os
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from core.config import CORS_ORIGINS
from core.db import client
from services.seed import seed
from services.whatsapp import start_scheduler, stop_scheduler

from routers.auth      import router as auth_router
from routers.items     import router as items_router
from routers.purchases import router as purchases_router
from routers.usage     import router as usage_router
from routers.sales     import router as sales_router
from routers.expenses  import router as expenses_router
from routers.stock     import router as stock_router
from routers.pnl       import router as pnl_router
from routers.salaries  import router as salaries_router
from routers.whatsapp  import router as whatsapp_router

# ── App ───────────────────────────────────────────────────────────────────
app = FastAPI(title="SP Royal Punjabi Dhaba — Operations Manager")

# ── CORS ──────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────
PREFIX = "/api"
for router in [
    auth_router, items_router, purchases_router, usage_router,
    sales_router, expenses_router, stock_router, pnl_router,
    salaries_router, whatsapp_router,
]:
    app.include_router(router, prefix=PREFIX)

# ── Lifecycle ─────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    await seed()
    if os.environ.get("ENABLE_SCHEDULER", "true").lower() == "true":
        start_scheduler()

@app.on_event("shutdown")
async def shutdown():
    stop_scheduler()
    client.close()

# ── Health check ──────────────────────────────────────────────────────────
@app.get("/api/")
async def root():
    return {"status": "ok", "app": "SP Royal Punjabi Dhaba — Operations Manager"}
