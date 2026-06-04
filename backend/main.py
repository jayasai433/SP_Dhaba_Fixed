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

# ── Security Headers ──────────────────────────────────────────────────────
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# ── CORS ──────────────────────────────────────────────────────────────────
# CORS: credentials require specific origins (not "*")
_cors_origins = CORS_ORIGINS if CORS_ORIGINS != ["*"] else ["*"]
_allow_creds  = CORS_ORIGINS != ["*"]  # credentials only work with specific origins

app.add_middleware(
    CORSMiddleware,
    allow_credentials=_allow_creds,
    allow_origins=_cors_origins,
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
    import logging, asyncio
    logger = logging.getLogger("startup")
    # Retry seed up to 3 times with backoff — handles transient Atlas connection issues
    for attempt in range(1, 4):
        try:
            logger.info(f"Seeding database (attempt {attempt}/3)...")
            await seed()
            logger.info("Database seeded successfully.")
            break
        except Exception as e:
            logger.error(f"Seed attempt {attempt} failed: {e}")
            if attempt < 3:
                await asyncio.sleep(5 * attempt)  # 5s, 10s backoff
            else:
                logger.error("All seed attempts failed. App will start but may have missing data.")
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

@app.get("/api/health")
async def health():
    """Deep health check — verifies DB connectivity"""
    try:
        from core.db import client
        await client.admin.command("ping")
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=f"DB unavailable: {str(e)[:100]}")
