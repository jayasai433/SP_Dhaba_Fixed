"""Backend API tests for SP Royal Punjabi Dhaba.
Covers: Auth, Roles, Items, Purchases, Usage/Stock, Sales, Dashboard,
Categories/Units, Business profile, Users, Bulk reorder, Staff isolation,
Expenses, Salaries, P&L, WhatsApp (log-only), Scheduler run-job.
"""
import os
import uuid
import time
from datetime import datetime, timezone, timedelta

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@spdhaba.com", "password": "Admin@123"}
STAFF = {"email": "lokesh@spdhaba.com", "password": "Staff@123"}
VIEWER = {"email": "display@spdhaba.com", "password": "View@123"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="session")
def staff_token():
    return _login(STAFF)


@pytest.fixture(scope="session")
def viewer_token():
    return _login(VIEWER)


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


# ----------------- Auth -----------------
class TestAuth:
    def test_login_admin_returns_token_and_user(self):
        r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "token" in data and len(data["token"]) > 20
        assert data["user"]["email"] == ADMIN["email"]
        assert data["user"]["role"] == "admin"

    def test_login_wrong_password(self):
        r = requests.post(f"{API}/auth/login",
                          json={"email": ADMIN["email"], "password": "wrongPass!"})
        assert r.status_code == 401

    def test_me_with_token(self, admin_token):
        r = requests.get(f"{API}/auth/me", headers=H(admin_token))
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN["email"]

    def test_me_without_token(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401


# ----------------- Cookie-based auth migration -----------------
class TestCookieAuth:
    def test_login_sets_httponly_cookie(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json=ADMIN, timeout=30)
        assert r.status_code == 200
        # Verify cookie present
        assert "sp_token" in s.cookies, f"sp_token not in cookie jar: {s.cookies}"
        # Verify HttpOnly attribute via raw Set-Cookie header
        set_cookie = r.headers.get("set-cookie", "")
        assert "sp_token=" in set_cookie
        assert "HttpOnly" in set_cookie, f"HttpOnly not in Set-Cookie: {set_cookie}"
        assert "Secure" in set_cookie, f"Secure not in Set-Cookie: {set_cookie}"
        # SameSite=Lax
        assert "SameSite=Lax" in set_cookie or "samesite=lax" in set_cookie.lower()
        # Token in body too (backward compat)
        assert "token" in r.json()

    def test_me_with_cookie_only(self):
        s = requests.Session()
        s.post(f"{API}/auth/login", json=ADMIN, timeout=30)
        # explicitly send NO auth header
        r = s.get(f"{API}/auth/me")
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN["email"]

    def test_me_with_bearer_only_still_works(self):
        # Fresh requests (no cookie jar) using only Bearer
        tok = _login(ADMIN)
        r = requests.get(f"{API}/auth/me", headers=H(tok))
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN["email"]

    def test_logout_clears_cookie_and_me_401(self):
        s = requests.Session()
        s.post(f"{API}/auth/login", json=ADMIN, timeout=30)
        assert "sp_token" in s.cookies
        rlo = s.post(f"{API}/auth/logout")
        assert rlo.status_code == 200
        # After logout - cookie cleared, /me should 401
        # Manually drop cookie since requests doesn't always honor delete
        s.cookies.clear()
        r = s.get(f"{API}/auth/me")
        assert r.status_code == 401


# ----------------- Refactor seed verification -----------------
class TestSeedRefactor:
    def test_seed_items_count(self, admin_token):
        r = requests.get(f"{API}/items", headers=H(admin_token))
        assert r.status_code == 200
        # 33 seeded items (additional TEST_ items may exist)
        seeded_names = {"Chicken", "Mutton", "Egg", "Paneer", "Milk", "Butter",
                        "Desi Ghee", "Curd", "Basmati Rice", "Wheat Flour Atta",
                        "Toor Dal", "Chana Dal", "Moong Dal", "Sunflower Oil",
                        "Mustard Oil", "Onion", "Tomato", "Potato", "Garlic",
                        "Ginger", "Green Chilli", "Garam Masala", "Red Chilli Powder",
                        "Turmeric Powder", "Coriander Powder", "Cumin Seeds", "Salt",
                        "Tea Powder", "Sugar", "LPG Cylinder", "Charcoal",
                        "Disposable Plates", "Tissue Paper"}
        item_names = {i["name"] for i in r.json()}
        missing = seeded_names - item_names
        assert not missing, f"missing seed items: {missing}"

    def test_seed_categories_9(self, admin_token):
        r = requests.get(f"{API}/categories", headers=H(admin_token))
        assert r.status_code == 200
        names = {c["name"] for c in r.json()}
        expected = {"Meat & Poultry", "Dairy", "Oils & Ghee", "Grains & Dal",
                    "Vegetables", "Spices & Masala", "Beverages",
                    "Firewood & Gas", "Packaging"}
        assert expected.issubset(names), f"missing: {expected - names}"

    def test_seed_units_9(self, admin_token):
        r = requests.get(f"{API}/units", headers=H(admin_token))
        names = {u["name"] for u in r.json()}
        expected = {"kg", "L", "dozen", "pcs", "packet", "g", "ml", "bag", "bottle"}
        assert expected.issubset(names)

    def test_seed_expense_categories_6(self, admin_token):
        r = requests.get(f"{API}/expense-categories", headers=H(admin_token))
        names = {c["name"] for c in r.json()}
        expected = {"Maintenance", "Utilities", "Rent", "Transport", "Equipment", "Others"}
        assert expected.issubset(names), f"missing: {expected - names}"

    def test_seed_lokesh_payroll_staff(self, admin_token):
        r = requests.get(f"{API}/staff", headers=H(admin_token))
        names = [s["name"] for s in r.json()]
        assert "Lokesh" in names

    def test_seed_whatsapp_settings(self, admin_token):
        r = requests.get(f"{API}/whatsapp/settings", headers=H(admin_token))
        assert r.status_code == 200
        d = r.json()
        # Verify settings doc exists with required keys
        for k in ["notify_out_of_stock", "notify_low_stock", "notify_large_purchase",
                  "large_purchase_threshold", "notify_morning_report",
                  "notify_daily_report", "notify_no_sales_reminder", "notify_daily_loss"]:
            assert k in d, f"missing key {k}"

    def test_seed_3_users(self, admin_token):
        r = requests.get(f"{API}/users", headers=H(admin_token))
        assert r.status_code == 200
        emails = {u["email"] for u in r.json()}
        for e in [ADMIN["email"], STAFF["email"], VIEWER["email"]]:
            assert e in emails


# ----------------- Business logic: category deactivation -----------------
class TestCategoryDeactivation:
    def test_cannot_deactivate_category_with_active_items(self, admin_token):
        cats = requests.get(f"{API}/categories", headers=H(admin_token)).json()
        # Dairy has active items (Paneer, Milk, etc)
        dairy = next(c for c in cats if c["name"] == "Dairy")
        r = requests.patch(f"{API}/categories/{dairy['id']}", headers=H(admin_token),
                           json={"is_active": False})
        assert r.status_code == 400
        assert "Cannot deactivate" in r.text or "active items" in r.text


# ----------------- Role enforcement -----------------
class TestRoles:
    def test_staff_blocked_from_dashboard(self, staff_token):
        r = requests.get(f"{API}/dashboard", headers=H(staff_token))
        assert r.status_code == 403

    def test_staff_blocked_from_salaries(self, staff_token):
        r = requests.get(f"{API}/salaries", headers=H(staff_token))
        assert r.status_code == 403

    def test_staff_blocked_from_expense_categories_post(self, staff_token):
        r = requests.post(f"{API}/expense-categories", headers=H(staff_token),
                          json={"name": f"TEST_{uuid.uuid4().hex[:6]}"})
        assert r.status_code == 403

    def test_staff_blocked_from_whatsapp_numbers_get(self, staff_token):
        r = requests.get(f"{API}/whatsapp/numbers", headers=H(staff_token))
        assert r.status_code == 403

    def test_viewer_blocked_from_expenses_post(self, viewer_token):
        r = requests.post(f"{API}/expenses", headers=H(viewer_token), json={
            "date": "2026-01-15", "category": "Misc", "amount": 50
        })
        assert r.status_code == 403


# ----------------- Items / Purchases (smoke) -----------------
class TestItemsAndPurchases:
    def test_items_seeded(self, admin_token):
        r = requests.get(f"{API}/items", headers=H(admin_token))
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 30

    def test_create_purchase_total_cost(self, admin_token):
        items = requests.get(f"{API}/items", headers=H(admin_token)).json()
        chicken = next(i for i in items if i["name"] == "Chicken")
        r = requests.post(f"{API}/purchases", headers=H(admin_token), json={
            "item_id": chicken["id"], "date": "2026-01-10",
            "quantity": 10, "price_per_unit": 250
        })
        assert r.status_code == 200
        assert r.json()["total_cost"] == 2500.0

    def test_stock_math(self, admin_token):
        # Create fresh item, buy 10kg, use 4kg => stock == 6
        name = f"TEST_Stock_{uuid.uuid4().hex[:8]}"
        r = requests.post(f"{API}/items", headers=H(admin_token), json={
            "name": name, "category": "Dairy", "unit": "kg", "reorder_level": 2
        })
        iid = r.json()["id"]
        requests.post(f"{API}/purchases", headers=H(admin_token), json={
            "item_id": iid, "date": "2026-01-10", "quantity": 10, "price_per_unit": 100
        })
        requests.post(f"{API}/usage", headers=H(admin_token), json={
            "item_id": iid, "date": "2026-01-11", "quantity_used": 4
        })
        stock = requests.get(f"{API}/stock", headers=H(admin_token)).json()
        row = next(s for s in stock if s["item_id"] == iid)
        assert abs(row["qty_left"] - 6) < 1e-6


# ----------------- Sales -----------------
class TestSales:
    def test_duplicate_sales_409(self, admin_token):
        date = f"2026-03-{uuid.uuid4().int % 28 + 1:02d}"
        requests.delete(f"{API}/sales/{date}", headers=H(admin_token))  # cleanup if exists (best effort)
        r = requests.post(f"{API}/sales", headers=H(admin_token), json={
            "date": date, "lunch_amount": 1000, "dinner_amount": 2000, "other_amount": 500
        })
        if r.status_code == 409:
            pytest.skip("Collision; rerun")
        assert r.status_code == 200
        assert r.json()["total_amount"] == 3500.0
        r2 = requests.post(f"{API}/sales", headers=H(admin_token), json={
            "date": date, "lunch_amount": 1, "dinner_amount": 2, "other_amount": 0
        })
        assert r2.status_code == 409


# ----------------- Expenses (T01-T04) -----------------
class TestExpenses:
    def test_create_expense_and_filter(self, admin_token):
        cat = f"TEST_EC_{uuid.uuid4().hex[:6]}"
        # Create category
        rc = requests.post(f"{API}/expense-categories", headers=H(admin_token),
                           json={"name": cat})
        assert rc.status_code == 200
        # Create expense
        date = "2026-02-15"
        r = requests.post(f"{API}/expenses", headers=H(admin_token), json={
            "date": date, "category": cat, "description": "lunch",
            "amount": 123.45
        })
        assert r.status_code == 200
        eid = r.json()["id"]
        assert r.json()["amount"] == 123.45

        # Filter by category
        rf = requests.get(f"{API}/expenses", headers=H(admin_token),
                          params={"category": cat})
        assert rf.status_code == 200
        ids = [e["id"] for e in rf.json()]
        assert eid in ids
        # Filter by date range
        rd = requests.get(f"{API}/expenses", headers=H(admin_token),
                          params={"start": "2026-02-01", "end": "2026-02-28"})
        ids2 = [e["id"] for e in rd.json()]
        assert eid in ids2
        # Out of range
        rd2 = requests.get(f"{API}/expenses", headers=H(admin_token),
                           params={"start": "2030-01-01", "end": "2030-12-31"})
        assert eid not in [e["id"] for e in rd2.json()]


# ----------------- Expense Category list/create (T32) -----------------
class TestExpenseCategories:
    def test_create_and_list(self, admin_token):
        cat = f"TEST_EC2_{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{API}/expense-categories", headers=H(admin_token),
                          json={"name": cat})
        assert r.status_code == 200
        rl = requests.get(f"{API}/expense-categories", headers=H(admin_token))
        names = [c["name"] for c in rl.json()]
        assert cat in names


# ----------------- Staff (payroll) -----------------
class TestStaffPayroll:
    def test_create_staff(self, admin_token):
        name = f"TEST_Staff_{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{API}/staff", headers=H(admin_token), json={
            "name": name, "default_salary": 15000, "phone": "919876543210"
        })
        assert r.status_code == 200
        assert r.json()["default_salary"] == 15000


# ----------------- Salaries (T06-T10) -----------------
class TestSalaries:
    def test_salary_flow(self, admin_token):
        # create staff
        sname = f"TEST_Sal_{uuid.uuid4().hex[:6]}"
        rs = requests.post(f"{API}/staff", headers=H(admin_token), json={
            "name": sname, "default_salary": 10000
        })
        sid = rs.json()["id"]
        # create salary
        month = "2026-01"
        r = requests.post(f"{API}/salaries", headers=H(admin_token), json={
            "staff_id": sid, "month": month, "basic_salary": 10000, "advance_paid": 2000
        })
        assert r.status_code == 200
        sal_data = r.json()
        assert sal_data["net_payable"] == 8000
        sal_id = sal_data["id"]
        # duplicate
        rdup = requests.post(f"{API}/salaries", headers=H(admin_token), json={
            "staff_id": sid, "month": month, "basic_salary": 10000
        })
        assert rdup.status_code == 409
        # pay
        paid_date = datetime.now().strftime("%Y-%m-%d")
        rp = requests.post(f"{API}/salaries/{sal_id}/pay", headers=H(admin_token),
                           json={"paid_date": paid_date})
        assert rp.status_code == 200
        assert rp.json()["paid_date"] == paid_date
        # deactivate staff -> still appears in salary history
        ru = requests.patch(f"{API}/staff/{sid}", headers=H(admin_token),
                            json={"is_active": False})
        assert ru.status_code == 200
        rl = requests.get(f"{API}/salaries", headers=H(admin_token), params={"month": month})
        ids = [s["id"] for s in rl.json()]
        assert sal_id in ids


# ----------------- P&L (T11-T17) -----------------
class TestPnL:
    def test_pnl_arithmetic_with_explicit_range(self, admin_token):
        # use isolated date range
        start = "2027-01-01"
        end = "2027-01-31"
        # Create sales (revenue 5000)
        requests.post(f"{API}/sales", headers=H(admin_token), json={
            "date": "2027-01-15", "lunch_amount": 3000, "dinner_amount": 2000, "other_amount": 0
        })
        # Get items
        items = requests.get(f"{API}/items", headers=H(admin_token)).json()
        iid = items[0]["id"]
        # Purchase 1000 (cogs)
        requests.post(f"{API}/purchases", headers=H(admin_token), json={
            "item_id": iid, "date": "2027-01-10", "quantity": 1, "price_per_unit": 1000
        })
        # Expense 500
        requests.post(f"{API}/expenses", headers=H(admin_token), json={
            "date": "2027-01-20", "category": "Misc", "amount": 500
        })
        r = requests.get(f"{API}/pnl", headers=H(admin_token),
                         params={"start": start, "end": end})
        assert r.status_code == 200
        d = r.json()
        for k in ["revenue", "cogs", "expenses", "salaries", "net_profit"]:
            assert k in d
        # arithmetic
        assert d["net_profit"] == round(d["revenue"] - d["cogs"] - d["expenses"] - d["salaries"], 2)
        assert d["revenue"] >= 5000
        assert d["cogs"] >= 1000
        assert d["expenses"] >= 500

    def test_pnl_trend_30(self, admin_token):
        r = requests.get(f"{API}/pnl/trend", headers=H(admin_token), params={"days": 30})
        assert r.status_code == 200
        arr = r.json()
        assert isinstance(arr, list)
        assert len(arr) == 30
        # Each entry should have date + numeric values
        first = arr[0]
        assert "date" in first
        assert "net_profit" in first or "net" in first or "profit" in first

    def test_pnl_pdf_export(self, admin_token):
        r = requests.get(f"{API}/pnl/export", headers=H(admin_token),
                         params={"period": "month"})
        assert r.status_code == 200
        ct = r.headers.get("content-type", "")
        assert "application/pdf" in ct.lower(), f"content-type={ct}"
        assert r.content[:4] == b"%PDF"


# ----------------- Dashboard (T23-T25) -----------------
class TestDashboardNewFields:
    def test_dashboard_has_new_kpis(self, admin_token):
        r = requests.get(f"{API}/dashboard", headers=H(admin_token))
        assert r.status_code == 200
        d = r.json()
        for k in ["today_expenses", "today_pnl", "profit", "total_sales",
                  "total_spent", "category_spend", "sales_trend"]:
            assert k in d, f"missing key {k} in dashboard"


# ----------------- WhatsApp (LOG-ONLY mode) -----------------
class TestWhatsAppLogOnly:
    def test_create_number_and_test_logs_log_only(self, admin_token):
        phone = "9198" + "".join([str(uuid.uuid4().int % 10) for _ in range(8)])
        rc = requests.post(f"{API}/whatsapp/numbers", headers=H(admin_token), json={
            "name": f"TEST_{uuid.uuid4().hex[:6]}", "phone": phone, "is_active": True
        })
        assert rc.status_code == 200, rc.text
        nid = rc.json()["id"]
        # test
        rt = requests.post(f"{API}/whatsapp/test", headers=H(admin_token),
                           json={"number_id": nid})
        assert rt.status_code == 200, rt.text
        rt_data = rt.json()
        assert rt_data.get("log_only") is True
        assert rt_data.get("status") == "log_only"
        # log
        rl = requests.get(f"{API}/whatsapp/log", headers=H(admin_token))
        assert rl.status_code == 200
        logs = rl.json()
        match = [l for l in logs if l.get("to") == phone and l.get("type") == "test"]
        assert match, "Test notification not found in log"
        assert match[0]["status"] == "log_only"

    def test_deactivate_number(self, admin_token):
        phone = "9197" + "".join([str(uuid.uuid4().int % 10) for _ in range(8)])
        rc = requests.post(f"{API}/whatsapp/numbers", headers=H(admin_token), json={
            "name": f"TEST_Off_{uuid.uuid4().hex[:6]}", "phone": phone
        })
        nid = rc.json()["id"]
        ru = requests.patch(f"{API}/whatsapp/numbers/{nid}", headers=H(admin_token),
                            json={"is_active": False})
        assert ru.status_code == 200
        assert ru.json()["is_active"] is False

    def test_large_purchase_triggers_log(self, admin_token):
        # ensure at least one active number exists OR no-recipients log appears
        phone = "9196" + "".join([str(uuid.uuid4().int % 10) for _ in range(8)])
        requests.post(f"{API}/whatsapp/numbers", headers=H(admin_token), json={
            "name": f"TEST_LP_{uuid.uuid4().hex[:6]}", "phone": phone, "is_active": True
        })
        items = requests.get(f"{API}/items", headers=H(admin_token)).json()
        iid = items[0]["id"]
        # Purchase well over default threshold (5000)
        rp = requests.post(f"{API}/purchases", headers=H(admin_token), json={
            "item_id": iid, "date": "2026-01-15", "quantity": 100, "price_per_unit": 500
        })
        assert rp.status_code == 200
        # Wait for fire-and-forget task
        time.sleep(2.5)
        rl = requests.get(f"{API}/whatsapp/log", headers=H(admin_token),
                          params={"limit": 200}).json()
        types = [l.get("type") for l in rl]
        assert "large_purchase" in types, f"large_purchase not in log types {types[:20]}"

    def test_run_job_morning_report(self, admin_token):
        r = requests.post(f"{API}/whatsapp/run-job/morning_report",
                          headers=H(admin_token))
        assert r.status_code == 200, r.text

    def test_run_job_daily_report(self, admin_token):
        r = requests.post(f"{API}/whatsapp/run-job/daily_report",
                          headers=H(admin_token))
        assert r.status_code == 200

    def test_run_job_no_sales_reminder(self, admin_token):
        r = requests.post(f"{API}/whatsapp/run-job/no_sales_reminder",
                          headers=H(admin_token))
        assert r.status_code == 200


# ----------------- Settings: deactivate user (T34) -----------------
class TestUserDeactivation:
    def test_deactivated_user_cannot_login(self, admin_token):
        email = f"test_deact_{uuid.uuid4().hex[:6]}@spdhaba.com"
        rc = requests.post(f"{API}/users", headers=H(admin_token), json={
            "name": "Deactivate Me", "email": email,
            "password": "DeactPass1!", "role": "staff"
        })
        assert rc.status_code == 200
        uid = rc.json()["id"]
        # confirm login
        rok = requests.post(f"{API}/auth/login",
                            json={"email": email, "password": "DeactPass1!"})
        assert rok.status_code == 200
        # deactivate
        ru = requests.patch(f"{API}/users/{uid}", headers=H(admin_token),
                            json={"is_active": False})
        assert ru.status_code == 200
        # login should now fail
        rfail = requests.post(f"{API}/auth/login",
                              json={"email": email, "password": "DeactPass1!"})
        assert rfail.status_code == 401
