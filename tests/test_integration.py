"""
SP Dhaba — Full Integration Test Suite
Tests every endpoint with real sample data using a mocked MongoDB.
Run BEFORE refactor to capture baseline.
Run AFTER refactor to prove nothing broke.

Sample data:
- Admin user: admin@spdhaba.com / Admin@123
- Staff user: staff@spdhaba.com / Staff@123
- Viewer user: viewer@spdhaba.com / View@123
- 3 grocery items: Tomatoes, Onions, Oil
- Purchases, Usage, Sales, Expenses with real amounts
"""

import os, sys, uuid, pytest, asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Environment setup BEFORE importing server ──────────────────────────────
os.environ.setdefault("MONGO_URL",   "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME",     "sp_dhaba_test")
os.environ.setdefault("JWT_SECRET",  "test_secret_key_sp_dhaba_32chars!!")
os.environ.setdefault("ADMIN_EMAIL", "admin@spdhaba.com")
os.environ.setdefault("ADMIN_PASSWORD", "Admin@123")

import bcrypt, jwt as pyjwt
from mongomock_motor import AsyncMongoMockClient
from httpx import AsyncClient, ASGITransport

def now_utc(): return datetime.now(timezone.utc)
def iso(dt): return dt.isoformat()

# ── Patch the DB before server loads ──────────────────────────────────────
import unittest.mock as mock
_mock_client = AsyncMongoMockClient()
_mock_db     = _mock_client["sp_dhaba_test"]

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

with mock.patch("motor.motor_asyncio.AsyncIOMotorClient", return_value=_mock_client):
    import server
    server.db = _mock_db
    server.client = _mock_client

from server import app

# ══════════════════════════════════════════════════════════════════════════
# SAMPLE DATA
# ══════════════════════════════════════════════════════════════════════════
JWT_SECRET = os.environ["JWT_SECRET"]
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")

ADMIN  = {"id": "admin-001",  "email": "admin@spdhaba.com",  "name": "Jaya Sai",  "role": "admin",  "is_active": True}
STAFF  = {"id": "staff-001",  "email": "staff@spdhaba.com",  "name": "Lokesh",    "role": "staff",  "is_active": True}
VIEWER = {"id": "viewer-001", "email": "viewer@spdhaba.com", "name": "Display",   "role": "viewer", "is_active": True}

ITEMS = [
    {"id": "item-001", "name": "Tomatoes",  "category": "Vegetables", "unit": "kg",  "reorder_level": 2.0,  "is_active": True, "created_at": "2026-01-01T00:00:00+00:00", "updated_at": "2026-01-01T00:00:00+00:00"},
    {"id": "item-002", "name": "Onions",    "category": "Vegetables", "unit": "kg",  "reorder_level": 3.0,  "is_active": True, "created_at": "2026-01-01T00:00:00+00:00", "updated_at": "2026-01-01T00:00:00+00:00"},
    {"id": "item-003", "name": "Oil",       "category": "Pantry",     "unit": "ltr", "reorder_level": 1.0,  "is_active": True, "created_at": "2026-01-01T00:00:00+00:00", "updated_at": "2026-01-01T00:00:00+00:00"},
]

def _make_token(user):
    return pyjwt.encode(
        {"sub": user["id"], "email": user["email"], "role": user["role"],
         "exp": datetime.now(timezone.utc) + timedelta(hours=8),
         "iat": datetime.now(timezone.utc)},
        JWT_SECRET, algorithm="HS256"
    )

def _hash(pwd): return bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()

ADMIN_TOKEN  = _make_token(ADMIN)
STAFF_TOKEN  = _make_token(STAFF)
VIEWER_TOKEN = _make_token(VIEWER)

def auth(token): return {"Authorization": f"Bearer {token}"}

# ══════════════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════════════
@pytest.fixture(autouse=True)
async def seed_db():
    """Fresh DB for every test with consistent sample data"""
    # Clear all collections
    for coll in ["users","items","purchases","daily_usage","sales","expenses",
                 "salaries","staff","categories","units","business_profile",
                 "expense_categories","notifications","whatsapp_settings"]:
        await _mock_db[coll].drop()

    # Seed users with hashed passwords
    await _mock_db.users.insert_many([
        {**ADMIN,  "password_hash": _hash("Admin@123"), "created_at": "2026-01-01T00:00:00+00:00"},
        {**STAFF,  "password_hash": _hash("Staff@123"), "created_at": "2026-01-01T00:00:00+00:00"},
        {**VIEWER, "password_hash": _hash("View@123"),  "created_at": "2026-01-01T00:00:00+00:00"},
    ])

    # Seed items
    await _mock_db.items.insert_many(ITEMS)

    # Seed categories and units
    await _mock_db.categories.insert_many([
        {"id": "cat-001", "name": "Vegetables", "is_active": True},
        {"id": "cat-002", "name": "Pantry",     "is_active": True},
    ])
    await _mock_db.units.insert_many([
        {"id": "unit-001", "name": "kg",  "is_active": True},
        {"id": "unit-002", "name": "ltr", "is_active": True},
        {"id": "unit-003", "name": "pcs", "is_active": True},
    ])
    await _mock_db.expense_categories.insert_many([
        {"id": "ec-001", "name": "Gas",   "is_active": True},
        {"id": "ec-002", "name": "Wages", "is_active": True},
    ])

    # Seed business profile
    await _mock_db.business_profile.insert_one({
        "key": "main", "name": "SP Royal Punjabi Dhaba",
        "address": "123 Main St", "phone": "9999999999", "logo_base64": "",
    })

    # Seed purchases (10kg Tomatoes, 5kg Onions, 2ltr Oil)
    await _mock_db.purchases.insert_many([
        {"id": "pur-001", "item_id": "item-001", "date": TODAY, "quantity": 10.0,
         "price_per_unit": 30.0, "total_cost": 300.0,
         "created_by": "admin-001", "created_by_name": "Jaya Sai",
         "created_at": iso(now_utc()),
         "is_void": False, "voided_by": None, "voided_at": None, "void_reason": None},
        {"id": "pur-002", "item_id": "item-002", "date": TODAY, "quantity": 5.0,
         "price_per_unit": 25.0, "total_cost": 125.0,
         "created_by": "admin-001", "created_by_name": "Jaya Sai",
         "created_at": iso(now_utc()),
         "is_void": False, "voided_by": None, "voided_at": None, "void_reason": None},
        {"id": "pur-003", "item_id": "item-003", "date": TODAY, "quantity": 2.0,
         "price_per_unit": 120.0, "total_cost": 240.0,
         "created_by": "admin-001", "created_by_name": "Jaya Sai",
         "created_at": iso(now_utc()),
         "is_void": False, "voided_by": None, "voided_at": None, "void_reason": None},
    ])

    # Seed usage (4kg Tomatoes used, 2kg Onions, 1ltr Oil)
    await _mock_db.daily_usage.insert_many([
        {"id": "use-001", "item_id": "item-001", "date": TODAY, "quantity_used": 4.0,
         "notes": "lunch prep", "created_by": "staff-001", "created_by_name": "Lokesh",
         "created_at": iso(now_utc()),
         "is_void": False, "voided_by": None, "voided_at": None, "void_reason": None},
        {"id": "use-002", "item_id": "item-002", "date": TODAY, "quantity_used": 2.0,
         "notes": "", "created_by": "staff-001", "created_by_name": "Lokesh",
         "created_at": iso(now_utc()),
         "is_void": False, "voided_by": None, "voided_at": None, "void_reason": None},
        {"id": "use-003", "item_id": "item-003", "date": TODAY, "quantity_used": 1.0,
         "notes": "", "created_by": "staff-001", "created_by_name": "Lokesh",
         "created_at": iso(now_utc()),
         "is_void": False, "voided_by": None, "voided_at": None, "void_reason": None},
    ])

    # Seed sales (lunch 3000, dinner 5000, other 500)
    await _mock_db.sales.insert_one({
        "id": "sale-001", "date": TODAY,
        "lunch_amount": 3000.0, "dinner_amount": 5000.0, "other_amount": 500.0,
        "total_amount": 8500.0, "notes": "",
        "created_by": "admin-001", "created_by_name": "Jaya Sai",
        "created_at": iso(now_utc()),
    })

    # Seed expenses (Gas 500)
    await _mock_db.expenses.insert_one({
        "id": "exp-001", "date": TODAY, "category": "Gas",
        "description": "LPG refill", "amount": 500.0,
        "created_by": "admin-001", "created_by_name": "Jaya Sai",
        "created_at": iso(now_utc()),
        "is_void": False, "voided_by": None, "voided_at": None, "void_reason": None,
    })

    yield  # test runs here

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

# ══════════════════════════════════════════════════════════════════════════
# 1. AUTH TESTS
# ══════════════════════════════════════════════════════════════════════════
class TestAuth:
    async def test_login_admin_success(self, client):
        r = await client.post("/api/auth/login",
            json={"email": "admin@spdhaba.com", "password": "Admin@123"})
        assert r.status_code == 200
        data = r.json()
        assert data["user"]["role"] == "admin"
        assert data["user"]["email"] == "admin@spdhaba.com"
        assert "token" in data

    async def test_login_staff_success(self, client):
        r = await client.post("/api/auth/login",
            json={"email": "staff@spdhaba.com", "password": "Staff@123"})
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "staff"

    async def test_login_wrong_password(self, client):
        r = await client.post("/api/auth/login",
            json={"email": "admin@spdhaba.com", "password": "WrongPass!"})
        assert r.status_code == 401

    async def test_login_unknown_email(self, client):
        r = await client.post("/api/auth/login",
            json={"email": "nobody@test.com", "password": "Test@123"})
        assert r.status_code == 401

    async def test_me_with_valid_token(self, client):
        r = await client.get("/api/auth/me", headers=auth(ADMIN_TOKEN))
        assert r.status_code == 200
        assert r.json()["role"] == "admin"

    async def test_me_without_token(self, client):
        r = await client.get("/api/auth/me")
        assert r.status_code == 401

    async def test_logout(self, client):
        r = await client.post("/api/auth/logout", headers=auth(ADMIN_TOKEN))
        assert r.status_code == 200

    async def test_password_hash_not_in_me_response(self, client):
        r = await client.get("/api/auth/me", headers=auth(ADMIN_TOKEN))
        assert "password_hash" not in r.json()

# ══════════════════════════════════════════════════════════════════════════
# 2. ITEMS TESTS
# ══════════════════════════════════════════════════════════════════════════
class TestItems:
    async def test_list_items_admin(self, client):
        r = await client.get("/api/items", headers=auth(ADMIN_TOKEN))
        assert r.status_code == 200
        items = r.json()
        assert len(items) == 3
        names = [i["name"] for i in items]
        assert "Tomatoes" in names
        assert "Onions" in names
        assert "Oil" in names

    async def test_list_items_staff(self, client):
        r = await client.get("/api/items", headers=auth(STAFF_TOKEN))
        assert r.status_code == 200

    async def test_create_item_admin(self, client):
        r = await client.post("/api/items", headers=auth(ADMIN_TOKEN), json={
            "name": "Rice", "category": "Pantry", "unit": "kg", "reorder_level": 5.0
        })
        assert r.status_code == 200
        assert r.json()["name"] == "Rice"

    async def test_create_item_staff_forbidden(self, client):
        r = await client.post("/api/items", headers=auth(STAFF_TOKEN), json={
            "name": "Rice", "category": "Pantry", "unit": "kg", "reorder_level": 5.0
        })
        assert r.status_code == 403

    async def test_update_item_admin(self, client):
        r = await client.patch("/api/items/item-001", headers=auth(ADMIN_TOKEN),
            json={"reorder_level": 5.0})
        assert r.status_code == 200

# ══════════════════════════════════════════════════════════════════════════
# 3. PURCHASES TESTS
# ══════════════════════════════════════════════════════════════════════════
class TestPurchases:
    async def test_list_purchases_admin_sees_all(self, client):
        r = await client.get("/api/purchases", headers=auth(ADMIN_TOKEN))
        assert r.status_code == 200
        assert len(r.json()) == 3

    async def test_list_purchases_excludes_voided(self, client):
        # Void one purchase directly
        await _mock_db.purchases.update_one(
            {"id": "pur-001"}, {"$set": {"is_void": True}})
        r = await client.get("/api/purchases", headers=auth(ADMIN_TOKEN))
        assert len(r.json()) == 2

    async def test_list_purchases_has_created_at(self, client):
        r = await client.get("/api/purchases", headers=auth(ADMIN_TOKEN))
        for p in r.json():
            assert "created_at" in p

    async def test_create_purchase_success(self, client):
        r = await client.post("/api/purchases", headers=auth(ADMIN_TOKEN), json={
            "item_id": "item-001", "date": TODAY,
            "quantity": 3.0, "price_per_unit": 30.0
        })
        assert r.status_code == 200

    async def test_create_purchase_duplicate_10s_window(self, client):
        """Same item+date+qty within 10s → 409"""
        # Insert a purchase created 5 seconds ago
        from server import iso, now_utc
        await _mock_db.purchases.insert_one({
            "id": str(uuid.uuid4()), "item_id": "item-001", "date": TODAY,
            "quantity": 5.0, "price_per_unit": 30.0, "total_cost": 150.0,
            "created_by": "admin-001", "created_by_name": "Jaya Sai",
            "created_at": iso(now_utc() - timedelta(seconds=5)),
            "is_void": False,
        })
        r = await client.post("/api/purchases", headers=auth(ADMIN_TOKEN), json={
            "item_id": "item-001", "date": TODAY,
            "quantity": 5.0, "price_per_unit": 30.0
        })
        assert r.status_code == 409
        assert "duplicate" in r.json()["detail"].lower()

    async def test_create_purchase_same_item_old_entry_allowed(self, client):
        """Same item+qty but created 20s ago → allowed (legitimate re-entry)"""
        from server import iso, now_utc
        await _mock_db.purchases.insert_one({
            "id": str(uuid.uuid4()), "item_id": "item-001", "date": TODAY,
            "quantity": 5.0, "price_per_unit": 30.0, "total_cost": 150.0,
            "created_by": "admin-001", "created_by_name": "Jaya Sai",
            "created_at": iso(now_utc() - timedelta(seconds=20)),
            "is_void": False,
        })
        r = await client.post("/api/purchases", headers=auth(ADMIN_TOKEN), json={
            "item_id": "item-001", "date": TODAY,
            "quantity": 5.0, "price_per_unit": 30.0
        })
        assert r.status_code == 200

    async def test_create_purchase_viewer_forbidden(self, client):
        r = await client.post("/api/purchases", headers=auth(VIEWER_TOKEN), json={
            "item_id": "item-001", "date": TODAY, "quantity": 1.0, "price_per_unit": 30.0
        })
        assert r.status_code == 403

# ══════════════════════════════════════════════════════════════════════════
# 4. VOID TESTS
# ══════════════════════════════════════════════════════════════════════════
class TestVoid:
    async def test_admin_can_void_purchase(self, client):
        r = await client.patch("/api/purchases/pur-001/void",
            headers=auth(ADMIN_TOKEN), json={"reason": "Wrong quantity entered"})
        assert r.status_code == 200
        doc = await _mock_db.purchases.find_one({"id": "pur-001"})
        assert doc["is_void"] is True
        assert doc["voided_by"] == "Jaya Sai"
        assert doc["void_reason"] == "Wrong quantity entered"

    async def test_void_requires_reason(self, client):
        r = await client.patch("/api/purchases/pur-001/void",
            headers=auth(ADMIN_TOKEN), json={"reason": "  "})
        assert r.status_code == 400

    async def test_cannot_void_twice(self, client):
        await client.patch("/api/purchases/pur-001/void",
            headers=auth(ADMIN_TOKEN), json={"reason": "First void"})
        r = await client.patch("/api/purchases/pur-001/void",
            headers=auth(ADMIN_TOKEN), json={"reason": "Second void attempt"})
        assert r.status_code == 409

    async def test_staff_can_void_own_entry_same_day(self, client):
        r = await client.patch("/api/usage/use-001/void",
            headers=auth(STAFF_TOKEN), json={"reason": "Entered wrong qty"})
        assert r.status_code == 200

    async def test_staff_cannot_void_others_entry(self, client):
        # use-001 belongs to staff-001, try voiding with admin's entry
        await _mock_db.daily_usage.insert_one({
            "id": "use-admin-001", "item_id": "item-001", "date": TODAY,
            "quantity_used": 1.0, "notes": "",
            "created_by": "admin-001", "created_by_name": "Jaya Sai",
            "created_at": "2026-05-31T09:00:00+00:00",
            "is_void": False,
        })
        r = await client.patch("/api/usage/use-admin-001/void",
            headers=auth(STAFF_TOKEN), json={"reason": "trying to void admin entry"})
        assert r.status_code == 403

    async def test_viewer_cannot_void(self, client):
        r = await client.patch("/api/purchases/pur-001/void",
            headers=auth(VIEWER_TOKEN), json={"reason": "test"})
        assert r.status_code == 403

    async def test_void_nonexistent_entry(self, client):
        r = await client.patch("/api/purchases/nonexistent/void",
            headers=auth(ADMIN_TOKEN), json={"reason": "test"})
        assert r.status_code == 404

# ══════════════════════════════════════════════════════════════════════════
# 5. STOCK CALCULATION TESTS (critical — must be exact)
# ══════════════════════════════════════════════════════════════════════════
class TestStockCalculation:
    async def test_stock_tomatoes_correct(self, client):
        """10kg bought - 4kg used = 6kg left"""
        r = await client.get("/api/stock", headers=auth(ADMIN_TOKEN))
        assert r.status_code == 200
        stock = {s["item_id"]: s for s in r.json()}
        assert stock["item-001"]["qty_left"] == 6.0

    async def test_stock_onions_correct(self, client):
        """5kg bought - 2kg used = 3kg left"""
        r = await client.get("/api/stock", headers=auth(ADMIN_TOKEN))
        stock = {s["item_id"]: s for s in r.json()}
        assert stock["item-002"]["qty_left"] == 3.0

    async def test_stock_oil_correct(self, client):
        """2ltr bought - 1ltr used = 1ltr left"""
        r = await client.get("/api/stock", headers=auth(ADMIN_TOKEN))
        stock = {s["item_id"]: s for s in r.json()}
        assert stock["item-003"]["qty_left"] == 1.0

    async def test_stock_excludes_voided_purchase(self, client):
        """Void 10kg Tomato purchase → stock should drop by 10"""
        await _mock_db.purchases.update_one(
            {"id": "pur-001"}, {"$set": {"is_void": True}})
        r = await client.get("/api/stock", headers=auth(ADMIN_TOKEN))
        stock = {s["item_id"]: s for s in r.json()}
        # 0kg bought (voided) - 4kg used = -4kg → qty_left = -4
        assert stock["item-001"]["qty_left"] == -4.0

    async def test_stock_excludes_voided_usage(self, client):
        """Void 4kg Tomato usage → stock increases by 4"""
        await _mock_db.daily_usage.update_one(
            {"id": "use-001"}, {"$set": {"is_void": True}})
        r = await client.get("/api/stock", headers=auth(ADMIN_TOKEN))
        stock = {s["item_id"]: s for s in r.json()}
        # 10kg bought - 0kg used (voided) = 10kg
        assert stock["item-001"]["qty_left"] == 10.0

    async def test_stock_alert_low_when_at_reorder(self, client):
        """Oil: 1ltr left, reorder=1.0 → status=low"""
        r = await client.get("/api/stock", headers=auth(ADMIN_TOKEN))
        stock = {s["item_id"]: s for s in r.json()}
        assert stock["item-003"]["status"] == "low"

    async def test_stock_alert_in_when_above_reorder(self, client):
        """Tomatoes: 6kg left, reorder=2.0 → status=in"""
        r = await client.get("/api/stock", headers=auth(ADMIN_TOKEN))
        stock = {s["item_id"]: s for s in r.json()}
        assert stock["item-001"]["status"] == "in"

    async def test_stock_viewer_can_access(self, client):
        r = await client.get("/api/stock", headers=auth(VIEWER_TOKEN))
        assert r.status_code == 200

# ══════════════════════════════════════════════════════════════════════════
# 6. USAGE TESTS
# ══════════════════════════════════════════════════════════════════════════
class TestUsage:
    async def test_list_usage_admin_sees_all(self, client):
        r = await client.get("/api/usage", headers=auth(ADMIN_TOKEN))
        assert r.status_code == 200
        assert len(r.json()) == 3

    async def test_list_usage_staff_sees_own_only(self, client):
        r = await client.get("/api/usage", headers=auth(STAFF_TOKEN))
        assert r.status_code == 200
        # Staff only sees their own (staff-001's entries)
        for entry in r.json():
            assert entry["created_by_name"] == "Lokesh"

    async def test_list_usage_has_created_at(self, client):
        r = await client.get("/api/usage", headers=auth(ADMIN_TOKEN))
        for u in r.json():
            assert "created_at" in u

    async def test_create_usage_success(self, client):
        r = await client.post("/api/usage", headers=auth(STAFF_TOKEN), json={
            "item_id": "item-002", "date": TODAY,
            "quantity_used": 0.5, "notes": "dinner prep"
        })
        assert r.status_code == 200

    async def test_list_usage_excludes_voided(self, client):
        await _mock_db.daily_usage.update_one(
            {"id": "use-001"}, {"$set": {"is_void": True}})
        r = await client.get("/api/usage", headers=auth(ADMIN_TOKEN))
        assert len(r.json()) == 2

# ══════════════════════════════════════════════════════════════════════════
# 7. SALES TESTS
# ══════════════════════════════════════════════════════════════════════════
class TestSales:
    async def test_list_sales(self, client):
        r = await client.get("/api/sales", headers=auth(ADMIN_TOKEN))
        assert r.status_code == 200
        sales = r.json()
        assert len(sales) == 1
        assert sales[0]["total_amount"] == 8500.0

    async def test_sales_totals_correct(self, client):
        r = await client.get("/api/sales", headers=auth(ADMIN_TOKEN))
        s = r.json()[0]
        assert s["lunch_amount"] == 3000.0
        assert s["dinner_amount"] == 5000.0
        assert s["other_amount"] == 500.0

    async def test_create_sales_success(self, client):
        r = await client.post("/api/sales", headers=auth(ADMIN_TOKEN), json={
            "date": "2026-05-30",  # yesterday — not today
            "lunch_amount": 2000.0, "dinner_amount": 4000.0,
            "other_amount": 0.0, "notes": ""
        })
        assert r.status_code == 200

    async def test_create_sales_duplicate_date_blocked(self, client):
        r = await client.post("/api/sales", headers=auth(ADMIN_TOKEN), json={
            "date": TODAY,  # already exists
            "lunch_amount": 1000.0, "dinner_amount": 2000.0,
            "other_amount": 0.0, "notes": ""
        })
        assert r.status_code == 409

    async def test_check_sales_exists(self, client):
        r = await client.get(f"/api/sales/check/{TODAY}", headers=auth(ADMIN_TOKEN))
        assert r.status_code == 200
        assert r.json()["exists"] is True

    async def test_check_sales_not_exists(self, client):
        r = await client.get("/api/sales/check/2020-01-01", headers=auth(ADMIN_TOKEN))
        assert r.json()["exists"] is False

    async def test_viewer_cannot_create_sales(self, client):
        r = await client.post("/api/sales", headers=auth(VIEWER_TOKEN), json={
            "date": "2026-05-28", "lunch_amount": 1000.0,
            "dinner_amount": 2000.0, "other_amount": 0.0, "notes": ""
        })
        assert r.status_code == 403

# ══════════════════════════════════════════════════════════════════════════
# 8. EXPENSES TESTS
# ══════════════════════════════════════════════════════════════════════════
class TestExpenses:
    async def test_list_expenses(self, client):
        r = await client.get("/api/expenses", headers=auth(ADMIN_TOKEN))
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["amount"] == 500.0

    async def test_list_expenses_has_created_at(self, client):
        r = await client.get("/api/expenses", headers=auth(ADMIN_TOKEN))
        assert "created_at" in r.json()[0]

    async def test_list_expenses_excludes_voided(self, client):
        await _mock_db.expenses.update_one(
            {"id": "exp-001"}, {"$set": {"is_void": True}})
        r = await client.get("/api/expenses", headers=auth(ADMIN_TOKEN))
        assert len(r.json()) == 0

    async def test_create_expense_success(self, client):
        r = await client.post("/api/expenses", headers=auth(ADMIN_TOKEN), json={
            "date": TODAY, "category": "Gas",
            "description": "Extra LPG", "amount": 250.0
        })
        assert r.status_code == 200

    async def test_create_expense_invalid_category(self, client):
        r = await client.post("/api/expenses", headers=auth(ADMIN_TOKEN), json={
            "date": TODAY, "category": "InvalidCat",
            "description": "", "amount": 100.0
        })
        assert r.status_code == 400

    async def test_void_expense(self, client):
        r = await client.patch("/api/expenses/exp-001/void",
            headers=auth(ADMIN_TOKEN), json={"reason": "Wrong category"})
        assert r.status_code == 200
        doc = await _mock_db.expenses.find_one({"id": "exp-001"})
        assert doc["is_void"] is True

# ══════════════════════════════════════════════════════════════════════════
# 9. DASHBOARD TESTS
# ══════════════════════════════════════════════════════════════════════════
class TestDashboard:
    async def test_dashboard_admin_access(self, client):
        r = await client.get("/api/dashboard", headers=auth(ADMIN_TOKEN))
        assert r.status_code == 200

    async def test_dashboard_staff_forbidden(self, client):
        r = await client.get("/api/dashboard", headers=auth(STAFF_TOKEN))
        assert r.status_code == 403

    async def test_dashboard_viewer_access(self, client):
        r = await client.get("/api/dashboard", headers=auth(VIEWER_TOKEN))
        assert r.status_code == 200

    async def test_dashboard_excludes_voided_purchases(self, client):
        r1 = await client.get("/api/dashboard", headers=auth(ADMIN_TOKEN))
        total1 = r1.json().get("total_spent", 0)

        # Void the 300 Tomato purchase
        await _mock_db.purchases.update_one(
            {"id": "pur-001"}, {"$set": {"is_void": True}})

        r2 = await client.get("/api/dashboard", headers=auth(ADMIN_TOKEN))
        total2 = r2.json().get("total_spent", 0)

        assert total2 == round(total1 - 300.0, 2)

# ══════════════════════════════════════════════════════════════════════════
# 10. PnL TESTS
# ══════════════════════════════════════════════════════════════════════════
class TestPnL:
    async def test_pnl_admin_access(self, client):
        r = await client.get("/api/pnl?period=today", headers=auth(ADMIN_TOKEN))
        assert r.status_code == 200

    async def test_pnl_staff_forbidden(self, client):
        r = await client.get("/api/pnl?period=today", headers=auth(STAFF_TOKEN))
        assert r.status_code == 403

    async def test_pnl_revenue_correct(self, client):
        r = await client.get("/api/pnl?period=today", headers=auth(ADMIN_TOKEN))
        data = r.json()
        assert data.get("revenue") == 8500.0

    async def test_pnl_cogs_correct(self, client):
        """COGS = sum of non-voided purchases = 300+125+240 = 665"""
        r = await client.get("/api/pnl?period=today", headers=auth(ADMIN_TOKEN))
        data = r.json()
        assert data.get("cogs") == 665.0

    async def test_pnl_excludes_voided_purchase(self, client):
        await _mock_db.purchases.update_one(
            {"id": "pur-001"}, {"$set": {"is_void": True}})
        r = await client.get("/api/pnl?period=today", headers=auth(ADMIN_TOKEN))
        # COGS should drop by 300
        assert r.json().get("cogs") == 365.0

# ══════════════════════════════════════════════════════════════════════════
# 11. ALERTS TESTS
# ══════════════════════════════════════════════════════════════════════════
class TestAlerts:
    async def test_alerts_returns_list(self, client):
        r = await client.get("/api/alerts", headers=auth(ADMIN_TOKEN))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_alerts_includes_low_stock_oil(self, client):
        """Oil: 1ltr left = reorder_level → should be in alerts"""
        r = await client.get("/api/alerts", headers=auth(ADMIN_TOKEN))
        item_ids = [a["item_id"] for a in r.json()]
        assert "item-003" in item_ids

    async def test_viewer_can_see_alerts(self, client):
        r = await client.get("/api/alerts", headers=auth(VIEWER_TOKEN))
        assert r.status_code == 200

# ══════════════════════════════════════════════════════════════════════════
# 12. USERS / ROLE ENFORCEMENT
# ══════════════════════════════════════════════════════════════════════════
class TestUsersAndRoles:
    async def test_list_users_admin_only(self, client):
        r = await client.get("/api/users", headers=auth(ADMIN_TOKEN))
        assert r.status_code == 200
        assert len(r.json()) == 3

    async def test_list_users_staff_forbidden(self, client):
        r = await client.get("/api/users", headers=auth(STAFF_TOKEN))
        assert r.status_code == 403

    async def test_create_user_admin_only(self, client):
        r = await client.post("/api/users", headers=auth(ADMIN_TOKEN), json={
            "name": "New Staff", "email": "newstaff@test.com",
            "password": "NewPass8!", "role": "staff"
        })
        assert r.status_code == 200

    async def test_password_hash_not_returned(self, client):
        r = await client.get("/api/users", headers=auth(ADMIN_TOKEN))
        for u in r.json():
            assert "password_hash" not in u

    async def test_deactivated_user_cannot_login(self, client):
        await _mock_db.users.update_one(
            {"id": "staff-001"}, {"$set": {"is_active": False}})
        r = await client.post("/api/auth/login",
            json={"email": "staff@spdhaba.com", "password": "Staff@123"})
        assert r.status_code in (401, 403)

# ══════════════════════════════════════════════════════════════════════════
# 13. BUSINESS PROFILE
# ══════════════════════════════════════════════════════════════════════════
class TestBusinessProfile:
    async def test_get_profile(self, client):
        r = await client.get("/api/business-profile", headers=auth(ADMIN_TOKEN))
        assert r.status_code == 200
        assert r.json()["name"] == "SP Royal Punjabi Dhaba"

    async def test_update_profile_admin(self, client):
        r = await client.patch("/api/business-profile", headers=auth(ADMIN_TOKEN),
            json={"name": "Updated Dhaba Name"})
        assert r.status_code == 200

    async def test_update_profile_staff_forbidden(self, client):
        r = await client.patch("/api/business-profile", headers=auth(STAFF_TOKEN),
            json={"name": "Hack Name"})
        assert r.status_code == 403

    async def test_logo_size_limit(self, client):
        big_logo = "A" * 800_000  # > 700KB limit
        r = await client.patch("/api/business-profile", headers=auth(ADMIN_TOKEN),
            json={"logo_base64": big_logo})
        assert r.status_code == 400

# ══════════════════════════════════════════════════════════════════════════
# 14. CATEGORIES AND UNITS
# ══════════════════════════════════════════════════════════════════════════
class TestCategoriesUnits:
    async def test_list_categories(self, client):
        r = await client.get("/api/categories", headers=auth(ADMIN_TOKEN))
        assert r.status_code == 200

    async def test_create_category_admin(self, client):
        r = await client.post("/api/categories", headers=auth(ADMIN_TOKEN),
            json={"name": "Dairy"})
        assert r.status_code == 200

    async def test_list_units(self, client):
        r = await client.get("/api/units", headers=auth(ADMIN_TOKEN))
        assert r.status_code == 200

# ══════════════════════════════════════════════════════════════════════════
# PYTEST CONFIG
# ══════════════════════════════════════════════════════════════════════════
pytestmark = pytest.mark.asyncio

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
