import os
import uuid
from core.db import db, client
from core.utils import now_utc, iso
from core.security import hash_password
from core.config import (
    ADMIN_EMAIL, ADMIN_PASSWORD,
    STAFF_EMAIL, STAFF_PASSWORD,
    VIEWER_EMAIL, VIEWER_PASSWORD,
)

# ── Default seed data ─────────────────────────────────────────────────────
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

# ── Seed functions ────────────────────────────────────────────────────────
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
    import asyncio
    # Run all index creation in parallel for faster startup
    await asyncio.gather(
        db.users.create_index("email", unique=True),
        db.items.create_index([("name", 1)], unique=True),
        # Purchases: fast lookup by date (P&L, dashboard) and item (stock calc)
        db.purchases.create_index([("date", 1)]),
        db.purchases.create_index([("item_id", 1)]),
        db.purchases.create_index([("is_void", 1), ("date", 1)]),
        # Usage: same pattern as purchases
        db.daily_usage.create_index([("date", 1)]),
        db.daily_usage.create_index([("item_id", 1)]),
        db.daily_usage.create_index([("is_void", 1), ("date", 1)]),
        # Sales: unique per day + fast date lookup
        db.sales.create_index("date", unique=True),
        # Expenses: fast lookup by date and void status
        db.expenses.create_index([("is_void", 1), ("date", 1)]),
        db.expenses.create_index([("date", 1)]),
        # Salaries: fast lookup by paid_date for P&L
        db.salaries.create_index([("paid_date", 1)]),
        db.salaries.create_index([("staff_id", 1), ("month", 1)], unique=True),
        # Closing stock: one entry per item per date + wastage queries
        db.closing_stock.create_index([("item_id", 1), ("date", 1)], unique=True),
        db.closing_stock.create_index([("date", -1)]),
        db.closing_stock.create_index([("wastage_flag", 1), ("date", -1)]),
        # Duplicate-check window: purchases.created_at, usage.created_at, expenses.created_at
        db.purchases.create_index([("created_at", -1)]),
        db.daily_usage.create_index([("created_at", -1)]),
        db.expenses.create_index([("created_at", -1)]),
        # Sales date range queries
        db.sales.create_index([("date", 1)]),
        # Compound for P&L trend aggregation
        db.purchases.create_index([("is_void", 1), ("date", 1), ("total_cost", 1)]),
        db.expenses.create_index([("is_void", 1), ("date", 1), ("amount", 1)]),
        db.salaries.create_index([("paid_date", 1), ("net_payable", 1)]),
        # Rate limiter — TTL index auto-expires documents after window
        db.login_attempts.create_index([("expire_at", 1)], expireAfterSeconds=0),
        db.login_attempts.create_index([("key", 1), ("ts", -1)]),
        # Notifications
        db.notifications.create_index([("created_at", -1)]),
        db.notifications.create_index("status"),
    )

async def _seed_users():
    # Remove old email addresses from previous version
    await db.users.delete_many({"email": {"$in": [
        "admin@sprojal.com", "lokesh@sprojal.com", "display@sprojal.com"
    ]}})
    seeds = [
        (ADMIN_EMAIL,  ADMIN_PASSWORD,  "Jaya Sai", "admin"),
        (STAFF_EMAIL,  STAFF_PASSWORD,  "Lokesh",   "staff"),
        (VIEWER_EMAIL, VIEWER_PASSWORD, "Display",  "viewer"),
    ]
    for email, pwd, name, role in seeds:
        existing = await db.users.find_one({"email": email})
        if not existing:
            # First time only — create with default password from env var
            await ensure_user(email, pwd, name, role)
        # Never touch existing users — passwords managed via app UI only

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
