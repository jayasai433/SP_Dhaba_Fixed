import os
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from core.config import CORS_ORIGINS
from core.db import client
from services.seed import seed

from routers.auth      import router as auth_router
from routers.items     import router as items_router
from routers.purchases import router as purchases_router
from routers.sales     import router as sales_router
from routers.expenses  import router as expenses_router

app = FastAPI(title="SP Royal Punjabi Dhaba. Operations Manager")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

# CORS. Set CORS_ORIGINS on Railway to a comma-separated list containing your
# custom domain, e.g. "https://ops.yourdomain.com,https://your-app.up.railway.app"
# to unlock credentialed requests. Falls back to a permissive default for local
# development, in which case cookies are disabled (browsers reject credentials
# combined with wildcard origin).
_origins = [o.strip() for o in CORS_ORIGINS if o.strip()]
_allow_creds = _origins != ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_credentials=_allow_creds,
    allow_origins=_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

PREFIX = "/api"
for r in (auth_router, items_router, purchases_router, sales_router, expenses_router):
    app.include_router(r, prefix=PREFIX)


@app.on_event("startup")
async def _startup():
    import logging
    import asyncio
    logger = logging.getLogger("startup")
    for attempt in range(1, 4):
        try:
            logger.info(f"Seeding database (attempt {attempt}/3)...")
            await seed()
            logger.info("Database seed OK.")
            break
        except Exception as e:
            logger.error(f"Seed attempt {attempt} failed: {e}")
            if attempt < 3:
                await asyncio.sleep(5 * attempt)


@app.on_event("shutdown")
async def _shutdown():
    client.close()


@app.get("/api/")
async def root():
    return {"status": "ok", "app": "SP Royal Punjabi Dhaba. Operations Manager"}


@app.get("/api/health")
async def health():
    from core.config import ENVIRONMENT, DB_NAME
    try:
        await client.admin.command("ping")
        return {"status": "ok", "db": "connected",
                "db_name": DB_NAME, "environment": ENVIRONMENT}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=f"DB unavailable: {str(e)[:100]}")
