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
_LOGIN_MAX    = 5      # 5 attempts per window
_LOGIN_WINDOW = 300    # 5 minute window
_login_email_attempts: dict = {}  # Also track by email

def _check_rate_limit(ip: str, email: str = "") -> None:
    """
    Dual rate limiting: by IP and by email.
    IP limit: prevents brute force from one machine.
    Email limit: prevents distributed brute force targeting one account.
    """
    now = _time.time()

    # IP-based check
    ip_attempts = [t for t in _login_attempts[ip] if now - t < _LOGIN_WINDOW]
    _login_attempts[ip] = ip_attempts
    if len(ip_attempts) >= _LOGIN_MAX:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts from this device. Try again in 5 minutes.",
        )
    _login_attempts[ip].append(now)

    # Email-based check (protects against distributed attacks targeting one account)
    if email:
        email_key = email.lower()
        email_attempts = [t for t in _login_email_attempts.get(email_key, []) if now - t < _LOGIN_WINDOW * 2]
        _login_email_attempts[email_key] = email_attempts
        if len(email_attempts) >= _LOGIN_MAX * 2:  # 10 attempts per 10 min per email
            raise HTTPException(
                status_code=429,
                detail="Too many login attempts for this account. Try again in 10 minutes.",
                headers={"Retry-After": "600"},
            )
        _login_email_attempts[email_key].append(now)
