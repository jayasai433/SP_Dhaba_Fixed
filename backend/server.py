from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import uuid
import logging
import asyncio
import bcrypt
import jwt
import httpx
import io
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

IST = pytz.timezone("Asia/Kolkata")

# ---------------- DB & App ----------------
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI(title="SP Royal Punjabi Dhaba — Operations Manager")
api = APIRouter(prefix="/api")

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGO = "HS256"
TOKEN_TTL_HOURS = 8

bearer_scheme = HTTPBearer(auto_error=False)

# ---------------- Utils ----------------
def now_utc():
    return datetime.now(timezone.utc)

def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()

def hash_password(pwd: str) -> str:
    return bcrypt.hashpw(pwd.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(pwd: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pwd.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

def create_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": now_utc() + timedelta(hours=TOKEN_TTL_HOURS),
        "iat": now_utc(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

async def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    # Prefer httpOnly cookie (XSS-safe); fall back to Bearer header for API/CLI clients
    token = request.cookies.get("sp_token")
    if not token and creds and creds.credentials:
        token = creds.credentials
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await db.users.find_one({"id": payload["sub"], "is_active": True}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def require_roles(*roles):
    async def dep(user=Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Forbidden: insufficient role")
        return user
    return dep

# ---------------- Models ----------------
class UserOut(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: Literal["admin", "staff", "viewer"]
    is_active: bool
    created_at: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class UserCreateIn(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: Literal["admin", "staff", "viewer"]

class UserUpdateIn(BaseModel):
    name: Optional[str] = None
    role: Optional[Literal["admin", "staff", "viewer"]] = None
    is_active: Optional[bool] = None

class PasswordResetIn(BaseModel):
    new_password: str

class ItemIn(BaseModel):
    name: str
    category: str
    unit: str
    reorder_level: float = Field(ge=0)

class ItemUpdateIn(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    unit: Optional[str] = None
    reorder_level: Optional[float] = Field(default=None, ge=0)
    is_active: Optional[bool] = None

class PurchaseIn(BaseModel):
    item_id: str
    date: str  # YYYY-MM-DD
    quantity: float = Field(gt=0)
    price_per_unit: float = Field(ge=0)

class UsageIn(BaseModel):
    item_id: str
    date: str
    quantity_used: float = Field(gt=0)
    notes: Optional[str] = ""

class SalesIn(BaseModel):
    date: str
    lunch_amount: float = Field(ge=0)
    dinner_amount: float = Field(ge=0)
    other_amount: float = Field(ge=0)
    notes: Optional[str] = ""

class CategoryIn(BaseModel):
    name: str

class UnitIn(BaseModel):
    name: str

class BusinessProfileIn(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    logo_base64: Optional[str] = None

class BulkReorderItem(BaseModel):
    item_id: str
    reorder_level: float

class BulkReorderIn(BaseModel):
    updates: List[BulkReorderItem]

# ---- Expense models ----
class ExpenseIn(BaseModel):
    date: str
    category: str
    description: Optional[str] = ""
    amount: float = Field(gt=0)

class ExpenseCategoryIn(BaseModel):
    name: str

# ---- Salary / Staff models ----
class StaffIn(BaseModel):
    name: str
    default_salary: float = Field(ge=0, default=0)
    phone: Optional[str] = ""

class StaffUpdateIn(BaseModel):
    name: Optional[str] = None
    default_salary: Optional[float] = Field(default=None, ge=0)
    phone: Optional[str] = None
    is_active: Optional[bool] = None

class SalaryIn(BaseModel):
    staff_id: str
    month: str  # YYYY-MM
    basic_salary: float = Field(ge=0)
    advance_paid: float = Field(ge=0, default=0)
    notes: Optional[str] = ""

class SalaryPayIn(BaseModel):
    paid_date: str  # YYYY-MM-DD

# ---- WhatsApp models ----
class WhatsAppNumberIn(BaseModel):
    name: str
    phone: str  # E.164 without +, e.g. 919876543210
    is_active: bool = True

class WhatsAppNumberUpdateIn(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None

class WhatsAppSettingsIn(BaseModel):
    notify_out_of_stock: Optional[bool] = None
    notify_low_stock: Optional[bool] = None
    notify_large_purchase: Optional[bool] = None
    large_purchase_threshold: Optional[float] = Field(default=None, ge=0)
    notify_morning_report: Optional[bool] = None
    notify_daily_report: Optional[bool] = None
    notify_no_sales_reminder: Optional[bool] = None
    notify_daily_loss: Optional[bool] = None

class WhatsAppTestIn(BaseModel):
    number_id: str

# ---------------- Seed Data ----------------
DEFAULT_CATEGORIES = [
    "Meat & Poultry", "Dairy", "Oils & Ghee", "Grains & Dal",
    "Vegetables", "Spices & Masala", "Beverages",
    "Firewood & Gas", "Packaging"
]
DEFAULT_UNITS = ["kg", "L", "dozen", "pcs", "packet", "g", "ml", "bag", "bottle"]

SEED_ITEMS = [
    ("Chicken", "Meat & Poultry", "kg", 5),
    ("Mutton", "Meat & Poultry", "kg", 3),
    ("Egg", "Meat & Poultry", "dozen", 2),
    ("Paneer", "Dairy", "kg", 2),
    ("Milk", "Dairy", "L", 10),
    ("Butter", "Dairy", "kg", 1),
    ("Desi Ghee", "Oils & Ghee", "kg", 2),
    ("Curd", "Dairy", "kg", 3),
    ("Basmati Rice", "Grains & Dal", "kg", 10),
    ("Wheat Flour Atta", "Grains & Dal", "kg", 10),
    ("Toor Dal", "Grains & Dal", "kg", 5),
    ("Chana Dal", "Grains & Dal", "kg", 5),
    ("Moong Dal", "Grains & Dal", "kg", 3),
    ("Sunflower Oil", "Oils & Ghee", "L", 5),
    ("Mustard Oil", "Oils & Ghee", "L", 3),
    ("Onion", "Vegetables", "kg", 10),
    ("Tomato", "Vegetables", "kg", 8),
    ("Potato", "Vegetables", "kg", 8),
    ("Garlic", "Vegetables", "kg", 2),
    ("Ginger", "Vegetables", "kg", 2),
    ("Green Chilli", "Vegetables", "kg", 2),
    ("Garam Masala", "Spices & Masala", "packet", 5),
    ("Red Chilli Powder", "Spices & Masala", "kg", 1),
    ("Turmeric Powder", "Spices & Masala", "kg", 1),
    ("Coriander Powder", "Spices & Masala", "kg", 1),
    ("Cumin Seeds", "Spices & Masala", "kg", 1),
    ("Salt", "Spices & Masala", "kg", 5),
    ("Tea Powder", "Beverages", "kg", 1),
    ("Sugar", "Beverages", "kg", 5),
    ("LPG Cylinder", "Firewood & Gas", "pcs", 2),
    ("Charcoal", "Firewood & Gas", "kg", 10),
    ("Disposable Plates", "Packaging", "packet", 5),
    ("Tissue Paper", "Packaging", "packet", 5),
]

async def ensure_user(email, password, name, role):
    existing = await db.users.find_one({"email": email})
    if existing:
        return
    await db.users.insert_one({
        "id": str(uuid.uuid4()),
        "name": name,
        "email": email,
        "password_hash": hash_password(password),
        "role": role,
        "is_active": True,
        "created_at": iso(now_utc()),
    })

async def _seed_indexes():
    await db.users.create_index("email", unique=True)
    await db.items.create_index([("name", 1)], unique=True)
    await db.purchases.create_index([("date", 1), ("item_id", 1)])
    await db.daily_usage.create_index([("date", 1), ("item_id", 1)])
    await db.sales.create_index("date", unique=True)
    await db.notifications.create_index([("created_at", -1)])
    await db.notifications.create_index("status")

async def _seed_users():
    # One-time cleanup of legacy seed accounts (typo'd domain)
    await db.users.delete_many({"email": {"$in": [
        "admin@sprojal.com", "lokesh@sprojal.com", "display@sprojal.com"
    ]}})
    seeds = [
        (os.environ.get("ADMIN_EMAIL", "admin@spdhaba.com"),
         os.environ.get("ADMIN_PASSWORD", "Admin@123"), "Jaya Sai", "admin"),
        (os.environ.get("STAFF_EMAIL", "lokesh@spdhaba.com"),
         os.environ.get("STAFF_PASSWORD", "Staff@123"), "Lokesh", "staff"),
        (os.environ.get("VIEWER_EMAIL", "display@spdhaba.com"),
         os.environ.get("VIEWER_PASSWORD", "View@123"), "Display", "viewer"),
    ]
    for email, pwd, name, role in seeds:
        existing = await db.users.find_one({"email": email})
        if not existing:
            await ensure_user(email, pwd, name, role)
        elif not verify_password(pwd, existing.get("password_hash", "")):
            await db.users.update_one({"email": email},
                                      {"$set": {"password_hash": hash_password(pwd)}})

async def _seed_items():
    for name, cat, unit, reorder in SEED_ITEMS:
        if not await db.items.find_one({"name": name}):
            await db.items.insert_one({
                "id": str(uuid.uuid4()), "name": name, "category": cat, "unit": unit,
                "reorder_level": float(reorder), "is_active": True,
                "created_at": iso(now_utc()), "updated_at": iso(now_utc()),
            })

async def _seed_named_list(coll, names):
    for n in names:
        if not await coll.find_one({"name": n}):
            await coll.insert_one({"id": str(uuid.uuid4()), "name": n,
                                    "is_active": True, "created_at": iso(now_utc())})

async def _seed_business_profile():
    if not await db.business_profile.find_one({"key": "main"}):
        await db.business_profile.insert_one({
            "key": "main", "name": "SP Royal Punjabi Family Dhaba",
            "address": "", "phone": "", "logo_base64": "",
            "updated_at": iso(now_utc()),
        })

async def _seed_payroll_staff():
    if not await db.staff.find_one({"name": "Lokesh"}):
        await db.staff.insert_one({
            "id": str(uuid.uuid4()), "name": "Lokesh",
            "default_salary": 0, "phone": "", "is_active": True,
            "created_at": iso(now_utc()),
        })

async def _seed_whatsapp_settings():
    if not await db.whatsapp_settings.find_one({"key": "main"}):
        await db.whatsapp_settings.insert_one({
            "key": "main",
            "notify_out_of_stock": True, "notify_low_stock": True,
            "notify_large_purchase": True, "large_purchase_threshold": 5000.0,
            "notify_morning_report": True, "notify_daily_report": True,
            "notify_no_sales_reminder": True, "notify_daily_loss": True,
            "updated_at": iso(now_utc()),
        })

async def seed():
    await _seed_indexes()
    await _seed_users()
    await _seed_items()
    await _seed_named_list(db.categories, DEFAULT_CATEGORIES)
    await _seed_named_list(db.units, DEFAULT_UNITS)
    await _seed_named_list(db.expense_categories,
                            ["Maintenance", "Utilities", "Rent", "Transport", "Equipment", "Others"])
    await _seed_business_profile()
    await _seed_payroll_staff()
    await _seed_whatsapp_settings()

@app.on_event("startup")
async def startup():
    await seed()
    if os.environ.get("ENABLE_SCHEDULER", "true").lower() == "true":
        start_scheduler()

@app.on_event("shutdown")
async def shutdown():
    stop_scheduler()
    client.close()

# ---------------- Auth ----------------
COOKIE_NAME = "sp_token"
COOKIE_MAX_AGE = TOKEN_TTL_HOURS * 3600

@api.post("/auth/login")
async def login(payload: LoginIn, response: Response):
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

@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"ok": True}

@api.get("/auth/me")
async def me(user=Depends(get_current_user)):
    return user

# ---------------- Users (admin) ----------------
@api.get("/users", response_model=List[UserOut])
async def list_users(user=Depends(require_roles("admin"))):
    docs = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(500)
    return docs

@api.post("/users", response_model=UserOut)
async def create_user(payload: UserCreateIn, user=Depends(require_roles("admin"))):
    email = payload.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already exists")
    doc = {
        "id": str(uuid.uuid4()),
        "name": payload.name,
        "email": email,
        "password_hash": hash_password(payload.password),
        "role": payload.role,
        "is_active": True,
        "created_at": iso(now_utc()),
    }
    await db.users.insert_one(doc)
    doc.pop("password_hash"); doc.pop("_id", None)
    return doc

@api.patch("/users/{user_id}", response_model=UserOut)
async def update_user(user_id: str, payload: UserUpdateIn, user=Depends(require_roles("admin"))):
    update = {k: v for k, v in payload.dict().items() if v is not None}
    if update:
        await db.users.update_one({"id": user_id}, {"$set": update})
    doc = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not doc:
        raise HTTPException(404, "User not found")
    return doc

@api.post("/users/{user_id}/reset-password")
async def reset_user_password(user_id: str, payload: PasswordResetIn,
                               user=Depends(require_roles("admin"))):
    if len(payload.new_password) < 4:
        raise HTTPException(400, "Password too short")
    res = await db.users.update_one(
        {"id": user_id},
        {"$set": {"password_hash": hash_password(payload.new_password)}}
    )
    if res.matched_count == 0:
        raise HTTPException(404, "User not found")
    return {"ok": True}

# ---------------- Items ----------------
@api.get("/items")
async def list_items(include_inactive: bool = True, user=Depends(get_current_user)):
    q = {} if include_inactive else {"is_active": True}
    docs = await db.items.find(q, {"_id": 0}).sort("name", 1).to_list(1000)
    return docs

@api.post("/items")
async def create_item(payload: ItemIn, user=Depends(require_roles("admin"))):
    if await db.items.find_one({"name": payload.name}):
        raise HTTPException(400, "Item with this name already exists")
    doc = {
        "id": str(uuid.uuid4()),
        "name": payload.name,
        "category": payload.category,
        "unit": payload.unit,
        "reorder_level": float(payload.reorder_level),
        "is_active": True,
        "created_at": iso(now_utc()),
        "updated_at": iso(now_utc()),
    }
    await db.items.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api.patch("/items/{item_id}")
async def update_item(item_id: str, payload: ItemUpdateIn,
                       user=Depends(require_roles("admin"))):
    update = {k: v for k, v in payload.dict().items() if v is not None}
    if "name" in update:
        dup = await db.items.find_one({"name": update["name"], "id": {"$ne": item_id}})
        if dup:
            raise HTTPException(400, "Item with this name already exists")
    update["updated_at"] = iso(now_utc())
    res = await db.items.update_one({"id": item_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Item not found")
    return await db.items.find_one({"id": item_id}, {"_id": 0})

# ---------------- Purchases ----------------
def _can_view_all(user):
    return user["role"] in ("admin", "viewer")

@api.get("/purchases")
async def list_purchases(start: Optional[str] = None, end: Optional[str] = None,
                          item_id: Optional[str] = None, user=Depends(get_current_user)):
    q = {}
    if start: q.setdefault("date", {})["$gte"] = start
    if end: q.setdefault("date", {})["$lte"] = end
    if item_id: q["item_id"] = item_id
    if user["role"] == "staff":
        q["created_by"] = user["id"]
    docs = await db.purchases.find(q, {"_id": 0}).sort("date", -1).to_list(2000)
    # enrich with item info
    items = {i["id"]: i for i in await db.items.find({}, {"_id": 0}).to_list(2000)}
    for d in docs:
        it = items.get(d["item_id"], {})
        d["item_name"] = it.get("name", "Unknown")
        d["category"] = it.get("category", "")
        d["unit"] = it.get("unit", "")
    return docs

@api.post("/purchases")
async def create_purchase(payload: PurchaseIn, user=Depends(require_roles("admin", "staff"))):
    item = await db.items.find_one({"id": payload.item_id})
    if not item:
        raise HTTPException(400, "Item not found")
    doc = {
        "id": str(uuid.uuid4()),
        "item_id": payload.item_id,
        "date": payload.date,
        "quantity": float(payload.quantity),
        "price_per_unit": float(payload.price_per_unit),
        "total_cost": round(float(payload.quantity) * float(payload.price_per_unit), 2),
        "created_by": user["id"],
        "created_by_name": user["name"],
        "created_at": iso(now_utc()),
    }
    await db.purchases.insert_one(doc)
    doc.pop("_id", None)
    asyncio.create_task(_maybe_notify_after_purchase(item, doc))
    asyncio.create_task(_check_stock_alerts_for_item(payload.item_id))
    return doc
@api.get("/usage")
async def list_usage(start: Optional[str] = None, end: Optional[str] = None,
                      item_id: Optional[str] = None, user=Depends(get_current_user)):
    q = {}
    if start: q.setdefault("date", {})["$gte"] = start
    if end: q.setdefault("date", {})["$lte"] = end
    if item_id: q["item_id"] = item_id
    if user["role"] == "staff":
        q["created_by"] = user["id"]
    docs = await db.daily_usage.find(q, {"_id": 0}).sort("date", -1).to_list(2000)
    items = {i["id"]: i for i in await db.items.find({}, {"_id": 0}).to_list(2000)}
    for d in docs:
        it = items.get(d["item_id"], {})
        d["item_name"] = it.get("name", "Unknown")
        d["category"] = it.get("category", "")
        d["unit"] = it.get("unit", "")
    return docs

@api.post("/usage")
async def create_usage(payload: UsageIn, user=Depends(require_roles("admin", "staff"))):
    item = await db.items.find_one({"id": payload.item_id})
    if not item:
        raise HTTPException(400, "Item not found")
    doc = {
        "id": str(uuid.uuid4()),
        "item_id": payload.item_id,
        "date": payload.date,
        "quantity_used": float(payload.quantity_used),
        "notes": payload.notes or "",
        "created_by": user["id"],
        "created_by_name": user["name"],
        "created_at": iso(now_utc()),
    }
    await db.daily_usage.insert_one(doc)
    doc.pop("_id", None)
    asyncio.create_task(_check_stock_alerts_for_item(payload.item_id))
    return doc

# ---------------- Sales ----------------
@api.get("/sales")
async def list_sales(start: Optional[str] = None, end: Optional[str] = None,
                      user=Depends(get_current_user)):
    q = {}
    if start: q.setdefault("date", {})["$gte"] = start
    if end: q.setdefault("date", {})["$lte"] = end
    if user["role"] == "staff":
        q["created_by"] = user["id"]
    docs = await db.sales.find(q, {"_id": 0}).sort("date", -1).to_list(2000)
    return docs

@api.post("/sales")
async def create_sales(payload: SalesIn, user=Depends(require_roles("admin", "staff"))):
    existing = await db.sales.find_one({"date": payload.date})
    if existing:
        raise HTTPException(409, "Sales already recorded for this date")
    total = round(payload.lunch_amount + payload.dinner_amount + payload.other_amount, 2)
    doc = {
        "id": str(uuid.uuid4()),
        "date": payload.date,
        "lunch_amount": float(payload.lunch_amount),
        "dinner_amount": float(payload.dinner_amount),
        "other_amount": float(payload.other_amount),
        "total_amount": total,
        "notes": payload.notes or "",
        "created_by": user["id"],
        "created_by_name": user["name"],
        "created_at": iso(now_utc()),
    }
    await db.sales.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api.get("/sales/check/{date}")
async def check_sales(date: str, user=Depends(get_current_user)):
    exists = await db.sales.find_one({"date": date}, {"_id": 0})
    return {"exists": exists is not None, "entry": exists}

# ---------------- Stock View ----------------
@api.get("/stock")
async def get_stock(user=Depends(get_current_user)):
    items = await db.items.find({}, {"_id": 0}).to_list(2000)
    # aggregate purchases
    p_agg = await db.purchases.aggregate([
        {"$group": {"_id": "$item_id", "total": {"$sum": "$quantity"}}}
    ]).to_list(5000)
    u_agg = await db.daily_usage.aggregate([
        {"$group": {"_id": "$item_id", "total": {"$sum": "$quantity_used"}}}
    ]).to_list(5000)
    p_map = {x["_id"]: x["total"] for x in p_agg}
    u_map = {x["_id"]: x["total"] for x in u_agg}
    out = []
    for it in items:
        bought = float(p_map.get(it["id"], 0))
        used = float(u_map.get(it["id"], 0))
        left = round(bought - used, 3)
        reorder = float(it.get("reorder_level", 0))
        if left <= 0:
            stat = "out"
        elif left < reorder:
            stat = "low"
        else:
            stat = "in"
        out.append({
            "item_id": it["id"], "name": it["name"], "category": it["category"],
            "unit": it["unit"], "reorder_level": reorder,
            "total_bought": round(bought, 3), "total_used": round(used, 3),
            "qty_left": left, "status": stat, "is_active": it.get("is_active", True),
        })
    return out

@api.get("/alerts")
async def get_alerts(user=Depends(get_current_user)):
    stock = await get_stock(user)
    alerts = [s for s in stock if s["status"] in ("low", "out") and s["is_active"]]
    alerts.sort(key=lambda x: (0 if x["status"] == "out" else 1, x["name"]))
    return alerts

# ---------------- Dashboard ----------------
@api.get("/dashboard")
async def dashboard(user=Depends(require_roles("admin", "viewer"))):
    purchases = await db.purchases.find({}, {"_id": 0}).to_list(5000)
    sales = await db.sales.find({}, {"_id": 0}).to_list(5000)
    expenses_docs = await db.expenses.find({}, {"_id": 0}).to_list(5000)
    salary_docs = await db.salaries.find({}, {"_id": 0}).to_list(5000)
    items = {i["id"]: i for i in await db.items.find({}, {"_id": 0}).to_list(2000)}

    total_spent = round(sum(p["total_cost"] for p in purchases), 2)
    total_sales = round(sum(s["total_amount"] for s in sales), 2)
    total_expenses = round(sum(e["amount"] for e in expenses_docs), 2)
    total_salaries = round(sum(s.get("net_payable", 0) for s in salary_docs if s.get("paid_date")), 2)
    profit = round(total_sales - total_spent - total_expenses - total_salaries, 2)

    today = datetime.now(IST).strftime("%Y-%m-%d")
    today_sales = next((s for s in sales if s["date"] == today), None)
    today_sales_amount = today_sales["total_amount"] if today_sales else 0.0
    today_purchases_amount = sum(p["total_cost"] for p in purchases if p["date"] == today)
    today_expenses_amount = sum(e["amount"] for e in expenses_docs if e["date"] == today)
    today_pnl = round(today_sales_amount - today_purchases_amount - today_expenses_amount, 2)

    # category-wise spend
    cat_spend = {}
    for p in purchases:
        it = items.get(p["item_id"], {})
        cat = it.get("category", "Other")
        cat_spend[cat] = cat_spend.get(cat, 0) + p["total_cost"]
    cat_spend_list = sorted(
        [{"category": k, "amount": round(v, 2)} for k, v in cat_spend.items()],
        key=lambda x: -x["amount"]
    )

    # expense category breakdown
    exp_cat = {}
    for e in expenses_docs:
        exp_cat[e["category"]] = exp_cat.get(e["category"], 0) + e["amount"]
    exp_cat_list = sorted(
        [{"category": k, "amount": round(v, 2)} for k, v in exp_cat.items()],
        key=lambda x: -x["amount"]
    )

    # daily sales trend (last 30 days)
    end_dt = datetime.now(IST).date()
    start_dt = end_dt - timedelta(days=29)
    sales_by_date = {s["date"]: s["total_amount"] for s in sales}
    trend = []
    for i in range(30):
        d = (start_dt + timedelta(days=i)).isoformat()
        trend.append({"date": d, "amount": float(sales_by_date.get(d, 0))})

    # top 5 items by cost
    item_cost = {}
    for p in purchases:
        item_cost[p["item_id"]] = item_cost.get(p["item_id"], 0) + p["total_cost"]
    top_items = sorted(item_cost.items(), key=lambda x: -x[1])[:5]
    top_items_list = [
        {"name": items.get(iid, {}).get("name", "Unknown"), "amount": round(amt, 2)}
        for iid, amt in top_items
    ]

    # stock health
    stock = await get_stock(user)
    health = {"in": 0, "low": 0, "out": 0}
    for s in stock:
        if s["is_active"]:
            health[s["status"]] += 1
    alerts = [s for s in stock if s["status"] in ("low", "out") and s["is_active"]]

    return {
        "total_spent": total_spent,
        "total_sales": total_sales,
        "total_expenses": total_expenses,
        "total_salaries": total_salaries,
        "profit": profit,
        "today_sales": today_sales_amount,
        "today_purchases": round(today_purchases_amount, 2),
        "today_expenses": round(today_expenses_amount, 2),
        "today_pnl": today_pnl,
        "low_stock_count": health["low"],
        "out_of_stock_count": health["out"],
        "category_spend": cat_spend_list,
        "expense_category_spend": exp_cat_list,
        "sales_trend": trend,
        "top_items": top_items_list,
        "stock_health": health,
        "alerts_count": len(alerts),
    }

# ---------------- Categories & Units ----------------
@api.get("/categories")
async def list_categories(include_inactive: bool = False, user=Depends(get_current_user)):
    q = {} if include_inactive else {"is_active": True}
    docs = await db.categories.find(q, {"_id": 0}).sort("name", 1).to_list(200)
    return docs

@api.post("/categories")
async def create_category(payload: CategoryIn, user=Depends(require_roles("admin"))):
    if await db.categories.find_one({"name": payload.name}):
        raise HTTPException(400, "Category already exists")
    doc = {"id": str(uuid.uuid4()), "name": payload.name, "is_active": True,
           "created_at": iso(now_utc())}
    await db.categories.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api.patch("/categories/{cat_id}")
async def update_category(cat_id: str, payload: dict, user=Depends(require_roles("admin"))):
    update = {k: v for k, v in payload.items() if k in ("name", "is_active") and v is not None}
    if "is_active" in update and update["is_active"] == False:
        # ensure no active items use this category
        cat = await db.categories.find_one({"id": cat_id})
        if cat:
            count = await db.items.count_documents({"category": cat["name"], "is_active": True})
            if count > 0:
                raise HTTPException(400, f"Cannot deactivate: {count} active items use this category")
    res = await db.categories.update_one({"id": cat_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Category not found")
    return await db.categories.find_one({"id": cat_id}, {"_id": 0})

@api.get("/units")
async def list_units(include_inactive: bool = False, user=Depends(get_current_user)):
    q = {} if include_inactive else {"is_active": True}
    docs = await db.units.find(q, {"_id": 0}).sort("name", 1).to_list(200)
    return docs

@api.post("/units")
async def create_unit(payload: UnitIn, user=Depends(require_roles("admin"))):
    if await db.units.find_one({"name": payload.name}):
        raise HTTPException(400, "Unit already exists")
    doc = {"id": str(uuid.uuid4()), "name": payload.name, "is_active": True,
           "created_at": iso(now_utc())}
    await db.units.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api.patch("/units/{unit_id}")
async def update_unit(unit_id: str, payload: dict, user=Depends(require_roles("admin"))):
    update = {k: v for k, v in payload.items() if k in ("name", "is_active") and v is not None}
    res = await db.units.update_one({"id": unit_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Unit not found")
    return await db.units.find_one({"id": unit_id}, {"_id": 0})

# ---------------- Business Profile ----------------
@api.get("/business-profile")
async def get_business_profile(user=Depends(get_current_user)):
    doc = await db.business_profile.find_one({"key": "main"}, {"_id": 0})
    return doc or {}

@api.patch("/business-profile")
async def update_business_profile(payload: BusinessProfileIn,
                                   user=Depends(require_roles("admin"))):
    update = {k: v for k, v in payload.dict().items() if v is not None}
    update["updated_at"] = iso(now_utc())
    await db.business_profile.update_one({"key": "main"}, {"$set": update}, upsert=True)
    doc = await db.business_profile.find_one({"key": "main"}, {"_id": 0})
    return doc

# ---------------- Bulk reorder ----------------
@api.post("/items/bulk-reorder")
async def bulk_reorder(payload: BulkReorderIn, user=Depends(require_roles("admin"))):
    for u in payload.updates:
        await db.items.update_one(
            {"id": u.item_id},
            {"$set": {"reorder_level": float(u.reorder_level),
                       "updated_at": iso(now_utc())}}
        )
    return {"updated": len(payload.updates)}

# ---------------- Expenses ----------------
@api.get("/expenses")
async def list_expenses(start: Optional[str] = None, end: Optional[str] = None,
                         category: Optional[str] = None, user=Depends(get_current_user)):
    q = {}
    if start: q.setdefault("date", {})["$gte"] = start
    if end: q.setdefault("date", {})["$lte"] = end
    if category: q["category"] = category
    if user["role"] == "staff":
        q["created_by"] = user["id"]
    docs = await db.expenses.find(q, {"_id": 0}).sort("date", -1).to_list(2000)
    return docs

@api.post("/expenses")
async def create_expense(payload: ExpenseIn, user=Depends(require_roles("admin", "staff"))):
    cat = await db.expense_categories.find_one({"name": payload.category, "is_active": True})
    if not cat:
        raise HTTPException(400, "Invalid or inactive expense category")
    doc = {
        "id": str(uuid.uuid4()),
        "date": payload.date,
        "category": payload.category,
        "description": payload.description or "",
        "amount": float(payload.amount),
        "created_by": user["id"],
        "created_by_name": user["name"],
        "created_at": iso(now_utc()),
    }
    await db.expenses.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api.get("/expense-categories")
async def list_expense_categories(include_inactive: bool = False, user=Depends(get_current_user)):
    q = {} if include_inactive else {"is_active": True}
    docs = await db.expense_categories.find(q, {"_id": 0}).sort("name", 1).to_list(200)
    return docs

@api.post("/expense-categories")
async def create_expense_category(payload: ExpenseCategoryIn, user=Depends(require_roles("admin"))):
    if await db.expense_categories.find_one({"name": payload.name}):
        raise HTTPException(400, "Category already exists")
    doc = {"id": str(uuid.uuid4()), "name": payload.name, "is_active": True,
           "created_at": iso(now_utc())}
    await db.expense_categories.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api.patch("/expense-categories/{cat_id}")
async def update_expense_category(cat_id: str, payload: dict, user=Depends(require_roles("admin"))):
    update = {k: v for k, v in payload.items() if k in ("name", "is_active") and v is not None}
    res = await db.expense_categories.update_one({"id": cat_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Category not found")
    return await db.expense_categories.find_one({"id": cat_id}, {"_id": 0})

# ---------------- Staff (payroll) ----------------
@api.get("/staff")
async def list_staff(include_inactive: bool = True, user=Depends(get_current_user)):
    q = {} if include_inactive else {"is_active": True}
    docs = await db.staff.find(q, {"_id": 0}).sort("name", 1).to_list(200)
    return docs

@api.post("/staff")
async def create_staff(payload: StaffIn, user=Depends(require_roles("admin"))):
    if await db.staff.find_one({"name": payload.name}):
        raise HTTPException(400, "Staff with this name already exists")
    doc = {
        "id": str(uuid.uuid4()),
        "name": payload.name,
        "default_salary": float(payload.default_salary),
        "phone": payload.phone or "",
        "is_active": True,
        "created_at": iso(now_utc()),
    }
    await db.staff.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api.patch("/staff/{staff_id}")
async def update_staff(staff_id: str, payload: StaffUpdateIn, user=Depends(require_roles("admin"))):
    update = {k: v for k, v in payload.dict().items() if v is not None}
    res = await db.staff.update_one({"id": staff_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Staff not found")
    return await db.staff.find_one({"id": staff_id}, {"_id": 0})

# ---------------- Salaries ----------------
@api.get("/salaries")
async def list_salaries(month: Optional[str] = None, staff_id: Optional[str] = None,
                         user=Depends(require_roles("admin", "viewer"))):
    q = {}
    if month: q["month"] = month
    if staff_id: q["staff_id"] = staff_id
    docs = await db.salaries.find(q, {"_id": 0}).sort([("month", -1), ("staff_id", 1)]).to_list(2000)
    staff_map = {s["id"]: s for s in await db.staff.find({}, {"_id": 0}).to_list(500)}
    for d in docs:
        d["staff_name"] = staff_map.get(d["staff_id"], {}).get("name", "Unknown")
    return docs

@api.post("/salaries")
async def create_salary(payload: SalaryIn, user=Depends(require_roles("admin"))):
    staff = await db.staff.find_one({"id": payload.staff_id})
    if not staff:
        raise HTTPException(400, "Staff not found")
    existing = await db.salaries.find_one({"staff_id": payload.staff_id, "month": payload.month})
    if existing:
        raise HTTPException(409, "Salary already recorded for this staff for this month")
    net = round(payload.basic_salary - payload.advance_paid, 2)
    doc = {
        "id": str(uuid.uuid4()),
        "staff_id": payload.staff_id,
        "month": payload.month,
        "basic_salary": float(payload.basic_salary),
        "advance_paid": float(payload.advance_paid),
        "net_payable": net,
        "paid_date": None,
        "notes": payload.notes or "",
        "created_by": user["id"],
        "created_at": iso(now_utc()),
    }
    await db.salaries.insert_one(doc)
    doc.pop("_id", None)
    doc["staff_name"] = staff["name"]
    return doc

@api.post("/salaries/{salary_id}/pay")
async def mark_salary_paid(salary_id: str, payload: SalaryPayIn, user=Depends(require_roles("admin"))):
    res = await db.salaries.update_one({"id": salary_id}, {"$set": {"paid_date": payload.paid_date}})
    if res.matched_count == 0:
        raise HTTPException(404, "Salary record not found")
    return await db.salaries.find_one({"id": salary_id}, {"_id": 0})

# ---------------- P&L ----------------
def _date_range_for_period(period: str):
    today = datetime.now(IST).date()
    if period == "today":
        return today.isoformat(), today.isoformat()
    if period == "week":
        start = today - timedelta(days=6)
        return start.isoformat(), today.isoformat()
    if period == "month":
        start = today.replace(day=1)
        return start.isoformat(), today.isoformat()
    if period == "all":
        return None, None
    return today.isoformat(), today.isoformat()

async def _compute_pnl(start: Optional[str], end: Optional[str]):
    def in_range(d):
        if start and d < start: return False
        if end and d > end: return False
        return True
    purchases = await db.purchases.find({}, {"_id": 0}).to_list(5000)
    sales = await db.sales.find({}, {"_id": 0}).to_list(5000)
    expenses_docs = await db.expenses.find({}, {"_id": 0}).to_list(5000)
    salaries = await db.salaries.find({}, {"_id": 0}).to_list(2000)
    rev = round(sum(s["total_amount"] for s in sales if in_range(s["date"])), 2)
    cogs = round(sum(p["total_cost"] for p in purchases if in_range(p["date"])), 2)
    exp = round(sum(e["amount"] for e in expenses_docs if in_range(e["date"])), 2)
    sal = round(sum(s.get("net_payable", 0) for s in salaries if s.get("paid_date") and in_range(s["paid_date"])), 2)
    net = round(rev - cogs - exp - sal, 2)
    return {"start": start, "end": end, "revenue": rev, "cogs": cogs, "expenses": exp,
            "salaries": sal, "net_profit": net}

@api.get("/pnl")
async def get_pnl(period: str = "today", start: Optional[str] = None,
                  end: Optional[str] = None, user=Depends(require_roles("admin", "viewer"))):
    if start or end:
        return await _compute_pnl(start, end)
    s, e = _date_range_for_period(period)
    return await _compute_pnl(s, e)

@api.get("/pnl/trend")
async def pnl_trend(days: int = 30, user=Depends(require_roles("admin", "viewer"))):
    end_dt = datetime.now(IST).date()
    start_dt = end_dt - timedelta(days=days - 1)
    purchases = await db.purchases.find({}, {"_id": 0}).to_list(5000)
    sales = await db.sales.find({}, {"_id": 0}).to_list(5000)
    expenses_docs = await db.expenses.find({}, {"_id": 0}).to_list(5000)
    salaries = await db.salaries.find({}, {"_id": 0}).to_list(2000)
    trend = []
    for i in range(days):
        d = (start_dt + timedelta(days=i)).isoformat()
        rev = sum(s["total_amount"] for s in sales if s["date"] == d)
        cogs = sum(p["total_cost"] for p in purchases if p["date"] == d)
        exp = sum(e["amount"] for e in expenses_docs if e["date"] == d)
        sal = sum(s.get("net_payable", 0) for s in salaries if s.get("paid_date") == d)
        trend.append({"date": d, "net": round(rev - cogs - exp - sal, 2),
                      "revenue": round(rev, 2), "cogs": round(cogs, 2),
                      "expenses": round(exp, 2), "salaries": round(sal, 2)})
    return trend

@api.get("/pnl/export")
async def export_pnl_pdf(period: str = "month", user=Depends(require_roles("admin", "viewer"))):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.units import cm

    s, e = _date_range_for_period(period)
    pnl = await _compute_pnl(s, e)
    biz = await db.business_profile.find_one({"key": "main"}, {"_id": 0}) or {}

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    h_style = ParagraphStyle('h', parent=styles['Heading1'], textColor=colors.HexColor("#E65C00"))
    elements = []
    elements.append(Paragraph(biz.get("name", "SP Royal Punjabi Family Dhaba"), h_style))
    elements.append(Paragraph(f"Profit & Loss Statement — {period.title()}", styles['Heading2']))
    elements.append(Paragraph(f"Period: {pnl.get('start') or 'All time'} to {pnl.get('end') or 'today'}", styles['Normal']))
    elements.append(Spacer(1, 0.5*cm))

    data = [
        ["Item", "Amount (INR)"],
        ["Revenue (Sales)", f"₹{pnl['revenue']:,.2f}"],
        ["Cost of Goods (Purchases)", f"-₹{pnl['cogs']:,.2f}"],
        ["Operating Expenses", f"-₹{pnl['expenses']:,.2f}"],
        ["Salaries Paid", f"-₹{pnl['salaries']:,.2f}"],
        ["Net Profit / (Loss)", f"₹{pnl['net_profit']:,.2f}"],
    ]
    t = Table(data, colWidths=[10*cm, 6*cm])
    is_profit = pnl["net_profit"] >= 0
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E65C00")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, -1), (-1, -1),
         colors.HexColor("#E8F5E9") if is_profit else colors.HexColor("#FFEBEE")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (-1, -1), 12),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph(
        f"<i>Generated on {datetime.now(IST).strftime('%d-%b-%Y %H:%M IST')}</i>", styles['Normal']))
    doc.build(elements)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="pnl-{period}-{datetime.now(IST).strftime("%Y%m%d")}.pdf"'})

# ---------------- WhatsApp ----------------
GRAPH_VERSION = os.environ.get("WHATSAPP_GRAPH_VERSION", "v22.0")

def _wa_creds():
    return (os.environ.get("WHATSAPP_ACCESS_TOKEN", "").strip(),
            os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "").strip())

async def _wa_send_to_number(phone: str, body: str, notif_type: str):
    token, pnid = _wa_creds()
    log_doc = {
        "id": str(uuid.uuid4()),
        "type": notif_type,
        "to": phone,
        "body": body,
        "status": "log_only",
        "error": None,
        "message_id": None,
        "created_at": iso(now_utc()),
    }
    if not token or not pnid:
        await db.notifications.insert_one({**log_doc})
        return
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{pnid}/messages"
    payload = {"messaging_product": "whatsapp", "to": phone,
               "type": "text", "text": {"body": body}}
    try:
        async with httpx.AsyncClient(timeout=10) as cli:
            r = await cli.post(url, json=payload,
                                headers={"Authorization": f"Bearer {token}"})
        if r.status_code >= 400:
            log_doc["status"] = "failed"
            log_doc["error"] = f"HTTP {r.status_code}: {r.text[:300]}"
        else:
            data = r.json()
            log_doc["status"] = "sent"
            log_doc["message_id"] = data.get("messages", [{}])[0].get("id")
    except Exception as exc:
        log_doc["status"] = "failed"
        log_doc["error"] = str(exc)[:300]
    await db.notifications.insert_one({**log_doc})

async def _wa_broadcast(body: str, notif_type: str):
    nums = await db.whatsapp_numbers.find({"is_active": True}, {"_id": 0}).to_list(50)
    if not nums:
        # still log so admins know it tried
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()), "type": notif_type, "to": "(no active numbers)",
            "body": body, "status": "no_recipients", "error": None, "message_id": None,
            "created_at": iso(now_utc()),
        })
        return
    for n in nums:
        await _wa_send_to_number(n["phone"], body, notif_type)

@api.get("/whatsapp/numbers")
async def list_wa_numbers(user=Depends(require_roles("admin"))):
    return await db.whatsapp_numbers.find({}, {"_id": 0}).sort("name", 1).to_list(100)

@api.post("/whatsapp/numbers")
async def create_wa_number(payload: WhatsAppNumberIn, user=Depends(require_roles("admin"))):
    if await db.whatsapp_numbers.find_one({"phone": payload.phone}):
        raise HTTPException(400, "Phone number already added")
    doc = {"id": str(uuid.uuid4()), "name": payload.name, "phone": payload.phone,
           "is_active": payload.is_active, "created_at": iso(now_utc())}
    await db.whatsapp_numbers.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api.patch("/whatsapp/numbers/{nid}")
async def update_wa_number(nid: str, payload: WhatsAppNumberUpdateIn, user=Depends(require_roles("admin"))):
    update = {k: v for k, v in payload.dict().items() if v is not None}
    res = await db.whatsapp_numbers.update_one({"id": nid}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Number not found")
    return await db.whatsapp_numbers.find_one({"id": nid}, {"_id": 0})

@api.delete("/whatsapp/numbers/{nid}")
async def delete_wa_number(nid: str, user=Depends(require_roles("admin"))):
    res = await db.whatsapp_numbers.delete_one({"id": nid})
    if res.deleted_count == 0:
        raise HTTPException(404, "Number not found")
    return {"ok": True}

@api.post("/whatsapp/test")
async def test_wa_number(payload: WhatsAppTestIn, user=Depends(require_roles("admin"))):
    n = await db.whatsapp_numbers.find_one({"id": payload.number_id})
    if not n:
        raise HTTPException(404, "Number not found")
    body = (f"✅ SP Royal Dhaba — Test Message\n"
            f"Sent to: {n['name']} ({n['phone']})\n"
            f"Time: {datetime.now(IST).strftime('%d-%b-%Y %H:%M IST')}\n"
            f"— SP Royal Ops Manager")
    await _wa_send_to_number(n["phone"], body, "test")
    last = await db.notifications.find_one({"to": n["phone"], "type": "test"},
                                            {"_id": 0}, sort=[("created_at", -1)])
    return {"ok": True, "status": last.get("status") if last else "unknown",
            "log_only": not all(_wa_creds())}

@api.get("/whatsapp/settings")
async def get_wa_settings(user=Depends(require_roles("admin"))):
    doc = await db.whatsapp_settings.find_one({"key": "main"}, {"_id": 0})
    return doc or {}

@api.patch("/whatsapp/settings")
async def update_wa_settings(payload: WhatsAppSettingsIn, user=Depends(require_roles("admin"))):
    update = {k: v for k, v in payload.dict().items() if v is not None}
    update["updated_at"] = iso(now_utc())
    await db.whatsapp_settings.update_one({"key": "main"}, {"$set": update}, upsert=True)
    return await db.whatsapp_settings.find_one({"key": "main"}, {"_id": 0})

@api.get("/whatsapp/log")
async def list_wa_log(limit: int = 100, user=Depends(require_roles("admin"))):
    docs = await db.notifications.find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return docs

@api.post("/whatsapp/retry/{notif_id}")
async def retry_wa_notification(notif_id: str, user=Depends(require_roles("admin"))):
    n = await db.notifications.find_one({"id": notif_id})
    if not n:
        raise HTTPException(404, "Notification not found")
    await _wa_send_to_number(n["to"], n["body"], n["type"] + "_retry")
    return {"ok": True}

# ---------------- Notification triggers (called from purchase create) ----------------
async def _maybe_notify_after_purchase(item, purchase_doc):
    settings = await db.whatsapp_settings.find_one({"key": "main"}) or {}
    if settings.get("notify_large_purchase") and \
       purchase_doc["total_cost"] >= float(settings.get("large_purchase_threshold", 5000)):
        body = (f"💸 SP Royal Dhaba — Large Purchase\n"
                f"Item: {item['name']}\n"
                f"Qty: {purchase_doc['quantity']} {item['unit']}\n"
                f"Total: ₹{purchase_doc['total_cost']:,.2f}\n"
                f"By: {purchase_doc.get('created_by_name', '')}\n"
                f"— SP Royal Ops Manager")
        await _wa_broadcast(body, "large_purchase")

async def _check_stock_alerts_for_item(item_id):
    settings = await db.whatsapp_settings.find_one({"key": "main"}) or {}
    if not (settings.get("notify_out_of_stock") or settings.get("notify_low_stock")):
        return
    item = await db.items.find_one({"id": item_id})
    if not item or not item.get("is_active", True):
        return
    p_agg = await db.purchases.aggregate([
        {"$match": {"item_id": item_id}},
        {"$group": {"_id": None, "total": {"$sum": "$quantity"}}}
    ]).to_list(1)
    u_agg = await db.daily_usage.aggregate([
        {"$match": {"item_id": item_id}},
        {"$group": {"_id": None, "total": {"$sum": "$quantity_used"}}}
    ]).to_list(1)
    bought = p_agg[0]["total"] if p_agg else 0
    used = u_agg[0]["total"] if u_agg else 0
    left = round(bought - used, 3)
    reorder = float(item.get("reorder_level", 0))
    if left <= 0 and settings.get("notify_out_of_stock"):
        body = (f"🔴 SP Royal Dhaba Alert\n"
                f"Item: {item['name']}\n"
                f"Status: Out of Stock\n"
                f"Qty Left: 0 {item['unit']}\n"
                f"Action: Buy Today!\n"
                f"— SP Royal Ops Manager")
        await _wa_broadcast(body, "stock_out")
    elif 0 < left < reorder and settings.get("notify_low_stock"):
        body = (f"🟡 SP Royal Dhaba Alert\n"
                f"Item: {item['name']}\n"
                f"Status: Low Stock\n"
                f"Qty Left: {left} {item['unit']} (reorder at {reorder})\n"
                f"— SP Royal Ops Manager")
        await _wa_broadcast(body, "stock_low")

# ---------------- Scheduler jobs ----------------
async def job_morning_report():
    items = await db.items.find({"is_active": True}, {"_id": 0}).to_list(2000)
    p_agg = await db.purchases.aggregate([{"$group": {"_id": "$item_id", "total": {"$sum": "$quantity"}}}]).to_list(5000)
    u_agg = await db.daily_usage.aggregate([{"$group": {"_id": "$item_id", "total": {"$sum": "$quantity_used"}}}]).to_list(5000)
    p_map = {x["_id"]: x["total"] for x in p_agg}
    u_map = {x["_id"]: x["total"] for x in u_agg}
    out, low, in_s = [], [], 0
    for it in items:
        left = (p_map.get(it["id"], 0)) - (u_map.get(it["id"], 0))
        reorder = float(it.get("reorder_level", 0))
        if left <= 0: out.append(it["name"])
        elif left < reorder: low.append(it["name"])
        else: in_s += 1
    today_str = datetime.now(IST).strftime("%d-%b-%Y")
    body = (f"📦 SP Royal Morning Stock Report\nDate: {today_str}\n\n"
            f"🔴 Out of Stock ({len(out)}): {', '.join(out) if out else 'None'}\n"
            f"🟡 Low Stock ({len(low)}): {', '.join(low) if low else 'None'}\n"
            f"🟢 In Stock: {in_s} items\n— SP Royal Ops Manager")
    settings = await db.whatsapp_settings.find_one({"key": "main"}) or {}
    if settings.get("notify_morning_report"):
        await _wa_broadcast(body, "morning_report")

async def job_daily_report():
    today = datetime.now(IST).strftime("%Y-%m-%d")
    sale = await db.sales.find_one({"date": today})
    expenses = await db.expenses.find({"date": today}).to_list(500)
    exp_total = sum(e["amount"] for e in expenses)
    s_lunch = sale["lunch_amount"] if sale else 0
    s_dinner = sale["dinner_amount"] if sale else 0
    s_other = sale["other_amount"] if sale else 0
    s_total = sale["total_amount"] if sale else 0
    purchases = await db.purchases.find({"date": today}).to_list(500)
    cogs = sum(p["total_cost"] for p in purchases)
    net = s_total - cogs - exp_total
    icon = "✅" if net >= 0 else "❌"
    body = (f"💰 SP Royal Daily Report\nDate: {datetime.now(IST).strftime('%d-%b-%Y')}\n\n"
            f"SALES\nLunch: ₹{s_lunch:,.2f}\nDinner: ₹{s_dinner:,.2f}\n"
            f"Other: ₹{s_other:,.2f}\nTotal: ₹{s_total:,.2f}\n\n"
            f"PURCHASES: ₹{cogs:,.2f}\nEXPENSES: ₹{exp_total:,.2f}\n"
            f"NET P&L: ₹{net:,.2f} {icon}\n— SP Royal Ops Manager")
    settings = await db.whatsapp_settings.find_one({"key": "main"}) or {}
    if settings.get("notify_daily_report"):
        await _wa_broadcast(body, "daily_report")
    if net < 0 and settings.get("notify_daily_loss"):
        await _wa_broadcast(
            f"⚠️ SP Royal Daily LOSS Alert\nDate: {datetime.now(IST).strftime('%d-%b-%Y')}\n"
            f"Net Loss: ₹{abs(net):,.2f}\n— SP Royal Ops Manager", "daily_loss")

async def job_no_sales_reminder():
    today = datetime.now(IST).strftime("%Y-%m-%d")
    sale = await db.sales.find_one({"date": today})
    if sale:
        return
    settings = await db.whatsapp_settings.find_one({"key": "main"}) or {}
    if not settings.get("notify_no_sales_reminder"):
        return
    body = (f"⏰ SP Royal Reminder\nNo sales entry recorded for {datetime.now(IST).strftime('%d-%b-%Y')} yet.\n"
            f"Please log today's sales before closing.\n— SP Royal Ops Manager")
    await _wa_broadcast(body, "no_sales_reminder")

_scheduler: Optional[AsyncIOScheduler] = None

def start_scheduler():
    global _scheduler
    if _scheduler:
        return
    _scheduler = AsyncIOScheduler(timezone=IST)
    _scheduler.add_job(job_morning_report, CronTrigger(hour=8, minute=0, timezone=IST),
                        id="morning_report", replace_existing=True)
    _scheduler.add_job(job_daily_report, CronTrigger(hour=22, minute=0, timezone=IST),
                        id="daily_report", replace_existing=True)
    _scheduler.add_job(job_no_sales_reminder, CronTrigger(hour=23, minute=0, timezone=IST),
                        id="no_sales_reminder", replace_existing=True)
    _scheduler.start()
    logging.getLogger(__name__).info("APScheduler started — jobs: morning(8am), daily(10pm), no-sales(11pm) IST")

def stop_scheduler():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None

@api.post("/whatsapp/run-job/{job_name}")
async def run_job(job_name: str, user=Depends(require_roles("admin"))):
    jobs = {"morning_report": job_morning_report, "daily_report": job_daily_report,
            "no_sales_reminder": job_no_sales_reminder}
    if job_name not in jobs:
        raise HTTPException(400, "Unknown job")
    await jobs[job_name]()
    return {"ok": True, "job": job_name}

# ---------------- Health ----------------
@api.get("/")
async def root():
    return {"app": "SP Royal Punjabi Dhaba — Operations Manager", "status": "ok"}

# ---------------- Mount ----------------
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
