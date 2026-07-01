"""
Idempotent seed. Safe to run on every startup. will not overwrite anything that
already exists. On a fresh DB it creates admin/staff/viewer accounts, a starter
category list, a starter set of items with multi-unit conversion, and default
expense categories.

Kept intentionally small: any richer defaults can be added via the app UI now
that there is no dashboard/analytics dependency on a large item seed.
"""
import uuid
from core.db import db
from core.utils import now_utc, iso
from core.security import hash_password
from core.config import (
    ADMIN_EMAIL, ADMIN_PASSWORD,
    STAFF_EMAIL, STAFF_PASSWORD,
    VIEWER_EMAIL, VIEWER_PASSWORD,
)

# Starter defaults ---------------------------------------------------------
DEFAULT_CATEGORIES = [
    "Meat & Poultry", "Dairy", "Oils & Ghee", "Grains & Dal",
    "Vegetables", "Spices & Masala", "Beverages",
    "Firewood & Gas", "Packaging",
]

DEFAULT_EXPENSE_CATEGORIES = [
    "Maintenance", "Utilities", "Rent", "Transport", "Equipment", "Others",
]

# (name, category, base_unit, [(unit_name, conversion_factor, is_default)], default_price)
SEED_ITEMS = [
    ("Egg", "Meat & Poultry", "piece",
        [("piece", 1, False), ("dozen", 12, True), ("tray", 30, False)], 8),
    ("Chicken", "Meat & Poultry", "kg",
        [("kg", 1, True), ("g", 0.001, False)], 240),
    ("Milk", "Dairy", "L",
        [("L", 1, True), ("ml", 0.001, False)], 60),
    ("Paneer", "Dairy", "kg",
        [("kg", 1, True), ("g", 0.001, False)], 380),
    ("Onion", "Vegetables", "kg",
        [("kg", 1, True), ("g", 0.001, False), ("bag", 25, False)], 35),
    ("Tomato", "Vegetables", "kg",
        [("kg", 1, True), ("g", 0.001, False)], 40),
    ("Basmati Rice", "Grains & Dal", "kg",
        [("kg", 1, True), ("bag", 25, False)], 90),
    ("Sunflower Oil", "Oils & Ghee", "L",
        [("L", 1, True), ("tin", 15, False)], 140),
    ("LPG Cylinder", "Firewood & Gas", "piece",
        [("piece", 1, True)], 1150),
]


async def _ensure_user(email, password, name, role):
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
    """Create index tolerating both OptionsConflict and KeySpecsConflict on re-runs."""
    name = kwargs.get("name")
    if not name:
        name = f"{keys}_1" if isinstance(keys, str) else "_".join(f"{k}_{v}" for k, v in keys)
        kwargs["name"] = name
    try:
        await collection.create_index(keys, **kwargs)
    except Exception as e:
        err = str(e)
        if "IndexOptionsConflict" in err or "already exists with a different name" in err:
            try:
                existing = await collection.index_information()
                target = [(keys, 1)] if isinstance(keys, str) else list(keys)
                for idx_name, idx_info in existing.items():
                    if idx_name != "_id_" and idx_info.get("key") == target:
                        await collection.drop_index(idx_name)
            except Exception:
                pass
            await collection.create_index(keys, **kwargs)
        elif "IndexKeySpecsConflict" in err or "existing index" in err:
            try:
                await collection.drop_index(name)
            except Exception:
                pass
            await collection.create_index(keys, **kwargs)
        else:
            raise


async def _seed_indexes():
    # Users
    await _safe_create_index(db.users, "email", unique=True, name="users_email_unique")
    # Items
    await _safe_create_index(db.items, [("name", 1)], unique=True, name="items_name_unique")
    await _safe_create_index(db.items, [("is_active", 1)], name="items_active")
    # Purchases
    await _safe_create_index(db.purchases, [("date", -1)], name="purchases_date_desc")
    await _safe_create_index(db.purchases, [("item_id", 1), ("date", -1)], name="purchases_item_date")
    await _safe_create_index(db.purchases, [("is_void", 1), ("date", -1)], name="purchases_void_date")
    await _safe_create_index(db.purchases, [("created_at", -1)], name="purchases_created_desc")
    # Sales. one entry per date
    await _safe_create_index(db.sales, [("date", 1)], unique=True, name="sales_date_unique")
    # Expenses
    await _safe_create_index(db.expenses, [("date", -1)], name="expenses_date_desc")
    await _safe_create_index(db.expenses, [("is_void", 1), ("date", -1)], name="expenses_void_date")
    await _safe_create_index(db.expenses, [("created_at", -1)], name="expenses_created_desc")
    # Rate limiter TTL. expires automatically
    await _safe_create_index(db.login_attempts, [("expire_at", 1)],
                             expireAfterSeconds=0, name="login_attempts_ttl")
    await _safe_create_index(db.login_attempts, [("key", 1), ("ts", -1)],
                             name="login_attempts_key_ts")


async def _seed_users():
    for email, pwd, name, role in [
        (ADMIN_EMAIL,  ADMIN_PASSWORD,  "Jaya Sai", "admin"),
        (STAFF_EMAIL,  STAFF_PASSWORD,  "Lokesh",   "staff"),
        (VIEWER_EMAIL, VIEWER_PASSWORD, "Display",  "viewer"),
    ]:
        await _ensure_user(email, pwd, name, role)


async def _seed_items():
    for name, cat, base_unit, units, default_price in SEED_ITEMS:
        if await db.items.find_one({"name": name}):
            continue
        now = iso(now_utc())
        await db.items.insert_one({
            "id": str(uuid.uuid4()),
            "name": name,
            "category": cat,
            "base_unit": base_unit,
            "default_price": float(default_price),
            "units": [
                {"name": n, "conversion_factor": float(cf), "is_default": bool(isdef)}
                for (n, cf, isdef) in units
            ],
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        })


async def _seed_named_list(coll, names):
    for n in names:
        if not await coll.find_one({"name": n}):
            await coll.insert_one({
                "id": str(uuid.uuid4()),
                "name": n,
                "is_active": True,
                "created_at": iso(now_utc()),
            })


async def _seed_business_profile():
    if not await db.business_profile.find_one({"key": "main"}):
        await db.business_profile.insert_one({
            "key": "main",
            "name": "SP Royal Punjabi Family Dhaba",
            "address": "",
            "phone": "",
            "logo_base64": "",
            "updated_at": iso(now_utc()),
        })


async def seed():
    await _seed_indexes()
    await _seed_users()
    await _seed_items()
    await _seed_named_list(db.categories, DEFAULT_CATEGORIES)
    await _seed_named_list(db.expense_categories, DEFAULT_EXPENSE_CATEGORIES)
    await _seed_business_profile()
