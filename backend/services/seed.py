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

async def _safe_create_index(collection, keys, **kwargs):
    """
    Create an index safely — handles both conflict types:

    Code 85 IndexOptionsConflict:
      Same key, different name (e.g. auto-named "email_1" vs our "users_email_unique")
      → drop ALL existing indexes on that key pattern, then recreate

    Code 86 IndexKeySpecsConflict:
      Same name, different options (e.g. non-unique vs unique "date_1")
      → drop by name, then recreate

    Safe to run on any existing DB regardless of prior index state.
    """
    name = kwargs.get("name")
    if not name:
        if isinstance(keys, str):
            name = f"{keys}_1"
        else:
            name = "_".join(f"{k}_{v}" for k, v in keys)
        kwargs["name"] = name

    try:
        await collection.create_index(keys, **kwargs)
    except Exception as e:
        err = str(e)
        if "IndexOptionsConflict" in err or "already exists with a different name" in err:
            # Drop every index on this collection that matches these keys
            # then recreate with our explicit name
            try:
                existing = await collection.index_information()
                # Normalise keys to compare
                if isinstance(keys, str):
                    target_key = [(keys, 1)]
                else:
                    target_key = list(keys)
                for idx_name, idx_info in existing.items():
                    if idx_name == "_id_":
                        continue
                    if idx_info.get("key") == target_key:
                        await collection.drop_index(idx_name)
            except Exception:
                pass
            await collection.create_index(keys, **kwargs)
        elif "IndexKeySpecsConflict" in err or "existing index" in err:
            # Drop by name and recreate
            try:
                await collection.drop_index(name)
            except Exception:
                pass
            await collection.create_index(keys, **kwargs)
        else:
            raise


async def _seed_indexes():
    """
    Create all indexes idempotently — safe to run on every startup.
    Uses _safe_create_index to handle conflicts when re-deploying
    to an existing DB (staging or production after schema changes).
    Indexes are created sequentially to avoid overwhelming Atlas free tier.
    """
    # Users & Items
    await _safe_create_index(db.users, "email", unique=True, name="users_email_unique")
    await _safe_create_index(db.items, [("name", 1)], unique=True, name="items_name_unique")

    # Purchases
    await _safe_create_index(db.purchases, [("date", 1)], name="purchases_date")
    await _safe_create_index(db.purchases, [("item_id", 1)], name="purchases_item_id")
    await _safe_create_index(db.purchases, [("is_void", 1), ("date", 1)], name="purchases_void_date")
    await _safe_create_index(db.purchases, [("created_at", -1)], name="purchases_created_at")
    await _safe_create_index(db.purchases, [("is_void", 1), ("date", 1), ("total_cost", 1)], name="purchases_pnl_compound")

    # Daily usage (legacy — kept for backward compat)
    await _safe_create_index(db.daily_usage, [("date", 1)], name="usage_date")
    await _safe_create_index(db.daily_usage, [("item_id", 1)], name="usage_item_id")
    await _safe_create_index(db.daily_usage, [("is_void", 1), ("date", 1)], name="usage_void_date")
    await _safe_create_index(db.daily_usage, [("created_at", -1)], name="usage_created_at")

    # Sales — one entry per day (unique) + date range queries
    await _safe_create_index(db.sales, [("date", 1)], unique=True, name="sales_date_unique")

    # Expenses
    await _safe_create_index(db.expenses, [("date", 1)], name="expenses_date")
    await _safe_create_index(db.expenses, [("is_void", 1), ("date", 1)], name="expenses_void_date")
    await _safe_create_index(db.expenses, [("created_at", -1)], name="expenses_created_at")
    await _safe_create_index(db.expenses, [("is_void", 1), ("date", 1), ("amount", 1)], name="expenses_pnl_compound")

    # Salaries
    await _safe_create_index(db.salaries, [("paid_date", 1)], name="salaries_paid_date")
    await _safe_create_index(db.salaries, [("staff_id", 1), ("month", 1)], unique=True, name="salaries_staff_month_unique")
    await _safe_create_index(db.salaries, [("paid_date", 1), ("net_payable", 1)], name="salaries_pnl_compound")

    # Closing stock
    await _safe_create_index(db.closing_stock, [("item_id", 1), ("date", 1)], unique=True, name="closing_stock_item_date_unique")
    await _safe_create_index(db.closing_stock, [("date", -1)], name="closing_stock_date")
    await _safe_create_index(db.closing_stock, [("wastage_flag", 1), ("date", -1)], name="closing_stock_wastage")

    # Rate limiter TTL
    await _safe_create_index(db.login_attempts, [("expire_at", 1)], expireAfterSeconds=0, name="login_attempts_ttl")
    await _safe_create_index(db.login_attempts, [("key", 1), ("ts", -1)], name="login_attempts_key_ts")

    # Notifications
    await _safe_create_index(db.notifications, [("created_at", -1)], name="notifications_created_at")
    await _safe_create_index(db.notifications, "status", name="notifications_status")

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
