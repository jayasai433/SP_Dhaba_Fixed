from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import uuid
import logging
import bcrypt
import jwt
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Literal
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, ConfigDict

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

async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGO])
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

async def seed():
    # Indexes
    await db.users.create_index("email", unique=True)
    await db.items.create_index([("name", 1)], unique=True)
    await db.purchases.create_index([("date", 1), ("item_id", 1)])
    await db.daily_usage.create_index([("date", 1), ("item_id", 1)])
    await db.sales.create_index("date", unique=True)

    # Users (idempotent — update password if env-changed)
    seeds = [
        (os.environ.get("ADMIN_EMAIL", "admin@sprojal.com"),
         os.environ.get("ADMIN_PASSWORD", "Admin@123"), "Jaya Sai", "admin"),
        (os.environ.get("STAFF_EMAIL", "lokesh@sprojal.com"),
         os.environ.get("STAFF_PASSWORD", "Staff@123"), "Lokesh", "staff"),
        (os.environ.get("VIEWER_EMAIL", "display@sprojal.com"),
         os.environ.get("VIEWER_PASSWORD", "View@123"), "Display", "viewer"),
    ]
    for email, pwd, name, role in seeds:
        existing = await db.users.find_one({"email": email})
        if not existing:
            await ensure_user(email, pwd, name, role)
        elif not verify_password(pwd, existing.get("password_hash", "")):
            await db.users.update_one({"email": email},
                                      {"$set": {"password_hash": hash_password(pwd)}})

    # Items
    for name, cat, unit, reorder in SEED_ITEMS:
        existing = await db.items.find_one({"name": name})
        if not existing:
            await db.items.insert_one({
                "id": str(uuid.uuid4()),
                "name": name,
                "category": cat,
                "unit": unit,
                "reorder_level": float(reorder),
                "is_active": True,
                "created_at": iso(now_utc()),
                "updated_at": iso(now_utc()),
            })

    # Categories
    for c in DEFAULT_CATEGORIES:
        if not await db.categories.find_one({"name": c}):
            await db.categories.insert_one({
                "id": str(uuid.uuid4()), "name": c, "is_active": True,
                "created_at": iso(now_utc()),
            })

    # Units
    for u in DEFAULT_UNITS:
        if not await db.units.find_one({"name": u}):
            await db.units.insert_one({
                "id": str(uuid.uuid4()), "name": u, "is_active": True,
                "created_at": iso(now_utc()),
            })

    # Business Profile
    if not await db.business_profile.find_one({"key": "main"}):
        await db.business_profile.insert_one({
            "key": "main",
            "name": "SP Royal Punjabi Family Dhaba",
            "address": "",
            "phone": "",
            "logo_base64": "",
            "updated_at": iso(now_utc()),
        })

@app.on_event("startup")
async def startup():
    await seed()

@app.on_event("shutdown")
async def shutdown():
    client.close()

# ---------------- Auth ----------------
@api.post("/auth/login")
async def login(payload: LoginIn):
    user = await db.users.find_one({"email": payload.email.lower()})
    if not user or not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_token(user["id"], user["email"], user["role"])
    return {
        "token": token,
        "user": {
            "id": user["id"], "name": user["name"], "email": user["email"],
            "role": user["role"], "is_active": user["is_active"],
            "created_at": user["created_at"],
        }
    }

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
    return doc

# ---------------- Usage ----------------
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
    items = {i["id"]: i for i in await db.items.find({}, {"_id": 0}).to_list(2000)}

    total_spent = round(sum(p["total_cost"] for p in purchases), 2)
    total_sales = round(sum(s["total_amount"] for s in sales), 2)
    profit = round(total_sales - total_spent, 2)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_sales = next((s for s in sales if s["date"] == today), None)
    today_sales_amount = today_sales["total_amount"] if today_sales else 0.0

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

    # daily sales trend (last 30 days)
    end_dt = datetime.now(timezone.utc).date()
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
        "profit": profit,
        "today_sales": today_sales_amount,
        "low_stock_count": health["low"],
        "out_of_stock_count": health["out"],
        "category_spend": cat_spend_list,
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
    if "is_active" in update and update["is_active"] is False:
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
