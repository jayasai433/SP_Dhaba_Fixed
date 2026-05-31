from datetime import datetime, timezone
from collections import defaultdict
import time as _time
from fastapi import HTTPException

# ── DateTime helpers ──────────────────────────────────────────────────────
def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()

# ── Staff data isolation ──────────────────────────────────────────────────
def _can_view_all(user: dict) -> bool:
    return user["role"] in ("admin", "viewer")

# ── Login rate limiter ────────────────────────────────────────────────────
_login_attempts: dict = defaultdict(list)
_LOGIN_MAX    = 10
_LOGIN_WINDOW = 300   # 5 minutes

def _check_rate_limit(ip: str) -> None:
    now      = _time.time()
    attempts = [t for t in _login_attempts[ip] if now - t < _LOGIN_WINDOW]
    _login_attempts[ip] = attempts
    if len(attempts) >= _LOGIN_MAX:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again in 5 minutes.",
        )
    _login_attempts[ip].append(now)
