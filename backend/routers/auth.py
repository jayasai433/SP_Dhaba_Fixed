import uuid
from typing import List
from fastapi import APIRouter, HTTPException, Depends, Request, Response

from core.db import db
from core.security import (
    get_current_user, require_roles,
    hash_password, verify_password, create_token,
)
from core.utils import now_utc, iso, _check_rate_limit
from core.config import TOKEN_TTL_HOURS
from models.user import UserOut, LoginIn, UserCreateIn, UserUpdateIn, PasswordResetIn

router = APIRouter()

COOKIE_NAME    = "sp_token"
COOKIE_MAX_AGE = TOKEN_TTL_HOURS * 3600

# ── Auth ──────────────────────────────────────────────────────────────────
@router.post("/auth/login")
async def login(payload: LoginIn, response: Response, request: Request):
    _check_rate_limit(
        request.client.host if request.client else "unknown",
        payload.email  # dual rate limiting by IP + email
    )
    user = await db.users.find_one({"email": payload.email.lower()})
    if not user or not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_token(user["id"], user["email"], user["role"])
    response.set_cookie(
        key=COOKIE_NAME, value=token, max_age=COOKIE_MAX_AGE,
        httponly=True, secure=True, samesite="lax", path="/",
    )
    return {
        "token": token,  # kept for curl/tests; browser uses httpOnly cookie
        "user": {
            "id": user["id"], "name": user["name"], "email": user["email"],
            "role": user["role"], "is_active": user["is_active"],
            "created_at": user["created_at"],
        }
    }

@router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"ok": True}

@router.get("/auth/me")
async def me(user=Depends(get_current_user)):
    return user

# ── Users (admin only) ────────────────────────────────────────────────────
@router.get("/users", response_model=List[UserOut])
async def list_users(user=Depends(require_roles("admin"))):
    return await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(500)

@router.post("/users", response_model=UserOut)
async def create_user(payload: UserCreateIn, user=Depends(require_roles("admin"))):
    email = payload.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already exists")
    doc = {
        "id": str(uuid.uuid4()), "name": payload.name, "email": email,
        "password_hash": hash_password(payload.password),
        "role": payload.role, "is_active": True, "created_at": iso(now_utc()),
    }
    await db.users.insert_one(doc)
    doc.pop("password_hash"); doc.pop("_id", None)
    return doc

@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: str, payload: UserUpdateIn,
                      user=Depends(require_roles("admin"))):
    # Explicitly whitelist updatable fields — prevent mass assignment
    allowed = {"name": payload.name, "role": payload.role, "is_active": payload.is_active}
    update  = {k: v for k, v in allowed.items() if v is not None}
    if update:
        await db.users.update_one({"id": user_id}, {"$set": update})
    doc = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not doc:
        raise HTTPException(404, "User not found")
    return doc

@router.post("/users/{user_id}/reset-password")
async def reset_user_password(user_id: str, payload: PasswordResetIn,
                               user=Depends(require_roles("admin"))):
    if len(payload.new_password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if not any(c.isupper() for c in payload.new_password) or \
       not any(c.isdigit() for c in payload.new_password):
        raise HTTPException(400, "Password must contain at least one uppercase letter and one number")
    res = await db.users.update_one(
        {"id": user_id},
        {"$set": {"password_hash": hash_password(payload.new_password)}}
    )
    if res.matched_count == 0:
        raise HTTPException(404, "User not found")
    return {"ok": True}
