from datetime import datetime, timezone, date as _date
from collections import defaultdict
import time as _time
import pytz as _pytz
from fastapi import HTTPException

_IST = _pytz.timezone("Asia/Kolkata")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def today_ist() -> _date:
    return datetime.now(_IST).date()


def _can_view_all(user: dict) -> bool:
    """All three roles get full visibility so team can operate the dhaba."""
    return user["role"] in ("admin", "viewer", "staff")


# Login rate limiter -------------------------------------------------------
# In-memory fallback used only if MongoDB is unreachable during a login.
_fallback_attempts: dict = defaultdict(list)
_LOGIN_MAX = 10
_LOGIN_WINDOW = 300
_EMAIL_MAX = 20
_EMAIL_WINDOW = 600


async def _check_rate_limit_db(ip: str, email: str) -> None:
    from core.db import db
    now_ts = _time.time()

    ip_count = await db.login_attempts.count_documents({
        "key": f"ip:{ip}",
        "ts": {"$gte": now_ts - _LOGIN_WINDOW},
    })
    if ip_count >= _LOGIN_MAX:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts from this device. Try again in 5 minutes.",
            headers={"Retry-After": "300"},
        )

    if email:
        email_count = await db.login_attempts.count_documents({
            "key": f"email:{email.lower()}",
            "ts": {"$gte": now_ts - _EMAIL_WINDOW},
        })
        if email_count >= _EMAIL_MAX:
            raise HTTPException(
                status_code=429,
                detail="Too many login attempts for this account. Try again in 10 minutes.",
                headers={"Retry-After": "600"},
            )

    expire_at = datetime.fromtimestamp(now_ts + _EMAIL_WINDOW, tz=timezone.utc)
    await db.login_attempts.insert_many([
        {"key": f"ip:{ip}",              "ts": now_ts, "expire_at": expire_at},
        {"key": f"email:{email.lower()}", "ts": now_ts, "expire_at": expire_at},
    ])


def _check_rate_limit_memory(ip: str, email: str) -> None:
    now = _time.time()
    ip_attempts = [t for t in _fallback_attempts[ip] if now - t < _LOGIN_WINDOW]
    _fallback_attempts[ip] = ip_attempts
    if len(ip_attempts) >= _LOGIN_MAX:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts from this device. Try again in 5 minutes.",
        )
    _fallback_attempts[ip].append(now)


async def check_rate_limit(ip: str, email: str = "") -> None:
    """
    Awaitable rate limiter. DB path is authoritative; memory path is a graceful
    fallback when Mongo is unreachable. Callers must await this so DB limits are
    actually enforced (this was previously fire-and-forget, letting all attempts
    through as long as the memory limiter permitted).
    """
    try:
        await _check_rate_limit_db(ip, email)
    except HTTPException:
        raise
    except Exception:
        _check_rate_limit_memory(ip, email)
