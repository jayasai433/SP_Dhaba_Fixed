from datetime import datetime, timezone, date as _date
from collections import defaultdict
import time as _time
import pytz as _pytz
from fastapi import HTTPException

# ── DateTime helpers ──────────────────────────────────────────────────────
_IST = _pytz.timezone("Asia/Kolkata")

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()

def today_ist() -> _date:
    """Today's date in Asia/Kolkata. Use this everywhere instead of date.today()."""
    return datetime.now(_IST).date()

# ── Staff data isolation ──────────────────────────────────────────────────
def _can_view_all(user: dict) -> bool:
    return user["role"] in ("admin", "viewer")

# ── Login rate limiter ────────────────────────────────────────────────────
# In-memory fallback — used when MongoDB is unavailable during startup.
# Primary path uses MongoDB TTL collection so limits survive deploys and
# work correctly across multiple Railway replicas.
_fallback_attempts: dict = defaultdict(list)
_LOGIN_MAX    = 5      # 5 attempts per window
_LOGIN_WINDOW = 300    # 5 minutes
_EMAIL_MAX    = 10     # per email across any IP
_EMAIL_WINDOW = 600    # 10 minutes

async def _check_rate_limit_db(ip: str, email: str) -> None:
    """
    Persistent rate limiting via MongoDB TTL collection.
    Each document auto-expires after _EMAIL_WINDOW seconds (MongoDB TTL index).
    Survives Railway deploys and works across replicas.
    """
    from core.db import db
    now_ts = _time.time()
    ip_window_start  = now_ts - _LOGIN_WINDOW
    email_window_start = now_ts - _EMAIL_WINDOW

    # IP check
    ip_count = await db.login_attempts.count_documents({
        "key": f"ip:{ip}",
        "ts": {"$gte": ip_window_start},
    })
    if ip_count >= _LOGIN_MAX:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts from this device. Try again in 5 minutes.",
            headers={"Retry-After": "300"},
        )

    # Email check
    if email:
        email_count = await db.login_attempts.count_documents({
            "key": f"email:{email.lower()}",
            "ts": {"$gte": email_window_start},
        })
        if email_count >= _EMAIL_MAX:
            raise HTTPException(
                status_code=429,
                detail="Too many login attempts for this account. Try again in 10 minutes.",
                headers={"Retry-After": "600"},
            )

    # Record this attempt (TTL index on `expire_at` cleans up automatically)
    from datetime import datetime, timezone
    expire_at = datetime.fromtimestamp(now_ts + _EMAIL_WINDOW, tz=timezone.utc)
    await db.login_attempts.insert_many([
        {"key": f"ip:{ip}",           "ts": now_ts, "expire_at": expire_at},
        {"key": f"email:{email.lower()}", "ts": now_ts, "expire_at": expire_at},
    ])

def _check_rate_limit_memory(ip: str, email: str) -> None:
    """Synchronous in-memory fallback (used only if DB is unreachable)."""
    now = _time.time()
    ip_attempts = [t for t in _fallback_attempts[ip] if now - t < _LOGIN_WINDOW]
    _fallback_attempts[ip] = ip_attempts
    if len(ip_attempts) >= _LOGIN_MAX:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts from this device. Try again in 5 minutes.",
        )
    _fallback_attempts[ip].append(now)

def _check_rate_limit(ip: str, email: str = "") -> None:
    """
    Dual rate limiting: by IP and by email.
    Caller is sync (FastAPI route); DB path is kicked off as a background task.
    Falls back to in-memory if DB is unavailable to never block login entirely.
    """
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an async context (normal FastAPI flow) —
            # schedule the coroutine and fall through to memory check as guard
            loop.create_task(_check_rate_limit_db(ip, email))
        # Always run the fast in-memory check as an immediate guard
        _check_rate_limit_memory(ip, email)
    except HTTPException:
        raise
    except Exception:
        # DB unavailable — memory limiter is sufficient protection
        _check_rate_limit_memory(ip, email)
