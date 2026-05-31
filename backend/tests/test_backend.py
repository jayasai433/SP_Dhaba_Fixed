"""Backend API tests for SP Royal Punjabi Dhaba."""
import os
import uuid
from datetime import datetime, timezone

import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@sprojal.com", "password": "Admin@123"}
STAFF = {"email": "lokesh@sprojal.com", "password": "Staff@123"}
VIEWER = {"email": "display@sprojal.com", "password": "View@123"}


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
        assert "token" in data and isinstance(data["token"], str) and len(data["token"]) > 20
        assert data["user"]["email"] == ADMIN["email"]
        assert data["user"]["role"] == "admin"

    def test_login_wrong_password(self):
        r = requests.post(f"{API}/auth/login",
                          json={"email": ADMIN["email"], "password": "wrongPass!"})
        assert r.status_code == 401

    def test_login_unknown_email(self):
        r = requests.post(f"{API}/auth/login",
                          json={"email": "nobody@nowhere.com", "password": "x"})
        assert r.status_code == 401

    def test_me_with_token(self, admin_token):
        r = requests.get(f"{API}/auth/me", headers=H(admin_token))
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN["email"]

    def test_me_without_token(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401


# ----------------- Role Enforcement -----------------
class TestRoles:
    def test_staff_blocked_from_dashboard(self, staff_token):
        r = requests.get(f"{API}/dashboard", headers=H(staff_token))
        assert r.status_code == 403

    def test_staff_blocked_from_create_item(self, staff_token):
        r = requests.post(f"{API}/items", headers=H(staff_token),
                          json={"name": "X", "category": "Dairy", "unit": "kg", "reorder_level": 1})
        assert r.status_code == 403

    def test_staff_blocked_from_users(self, staff_token):
        r = requests.get(f"{API}/users", headers=H(staff_token))
        assert r.status_code == 403

    def test_viewer_blocked_from_items_post(self, viewer_token):
        r = requests.post(f"{API}/items", headers=H(viewer_token),
                          json={"name": "Y", "category": "Dairy", "unit": "kg", "reorder_level": 1})
        assert r.status_code == 403

    def test_viewer_blocked_from_purchases_post(self, viewer_token, admin_token):
        # need an item_id
        items = requests.get(f"{API}/items", headers=H(admin_token)).json()
        r = requests.post(f"{API}/purchases", headers=H(viewer_token), json={
            "item_id": items[0]["id"], "date": "2026-01-15",
            "quantity": 1, "price_per_unit": 100
        })
        assert r.status_code == 403

    def test_viewer_blocked_from_usage_post(self, viewer_token, admin_token):
        items = requests.get(f"{API}/items", headers=H(admin_token)).json()
        r = requests.post(f"{API}/usage", headers=H(viewer_token), json={
            "item_id": items[0]["id"], "date": "2026-01-15", "quantity_used": 1
        })
        assert r.status_code == 403

    def test_viewer_blocked_from_sales_post(self, viewer_token):
        r = requests.post(f"{API}/sales", headers=H(viewer_token), json={
            "date": "2026-01-15", "lunch_amount": 100, "dinner_amount": 100, "other_amount": 0
        })
        assert r.status_code == 403


# ----------------- Items -----------------
class TestItems:
    def test_seeded_33_items(self, admin_token):
        r = requests.get(f"{API}/items", headers=H(admin_token))
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 33, f"Expected >=33 items, got {len(items)}"
        names = {i["name"] for i in items}
        assert "Chicken" in names and "Paneer" in names

    def test_create_item_and_duplicate(self, admin_token):
        unique = f"TEST_Item_{uuid.uuid4().hex[:8]}"
        r = requests.post(f"{API}/items", headers=H(admin_token), json={
            "name": unique, "category": "Dairy", "unit": "kg", "reorder_level": 2
        })
        assert r.status_code == 200
        created = r.json()
        assert created["name"] == unique and "id" in created
        # duplicate
        r2 = requests.post(f"{API}/items", headers=H(admin_token), json={
            "name": unique, "category": "Dairy", "unit": "kg", "reorder_level": 2
        })
        assert r2.status_code == 400

    def test_patch_item(self, admin_token):
        unique = f"TEST_Patch_{uuid.uuid4().hex[:8]}"
        r = requests.post(f"{API}/items", headers=H(admin_token), json={
            "name": unique, "category": "Dairy", "unit": "kg", "reorder_level": 2
        })
        iid = r.json()["id"]
        new_name = unique + "_v2"
        r2 = requests.patch(f"{API}/items/{iid}", headers=H(admin_token),
                            json={"name": new_name, "reorder_level": 5, "is_active": False})
        assert r2.status_code == 200
        body = r2.json()
        assert body["name"] == new_name
        assert body["reorder_level"] == 5
        assert body["is_active"] is False


# ----------------- Purchases -----------------
class TestPurchases:
    def test_create_purchase_total_cost(self, admin_token):
        items = requests.get(f"{API}/items", headers=H(admin_token)).json()
        chicken = next(i for i in items if i["name"] == "Chicken")
        r = requests.post(f"{API}/purchases", headers=H(admin_token), json={
            "item_id": chicken["id"], "date": "2026-01-10",
            "quantity": 10, "price_per_unit": 250
        })
        assert r.status_code == 200
        data = r.json()
        assert data["total_cost"] == 2500.0
        assert data["item_id"] == chicken["id"]

    def test_purchase_qty_zero_validation(self, admin_token):
        items = requests.get(f"{API}/items", headers=H(admin_token)).json()
        r = requests.post(f"{API}/purchases", headers=H(admin_token), json={
            "item_id": items[0]["id"], "date": "2026-01-10",
            "quantity": 0, "price_per_unit": 100
        })
        assert r.status_code == 422

    def test_purchase_negative_price_validation(self, admin_token):
        items = requests.get(f"{API}/items", headers=H(admin_token)).json()
        r = requests.post(f"{API}/purchases", headers=H(admin_token), json={
            "item_id": items[0]["id"], "date": "2026-01-10",
            "quantity": 1, "price_per_unit": -50
        })
        assert r.status_code == 422

    def test_list_purchases_enriched(self, admin_token):
        r = requests.get(f"{API}/purchases", headers=H(admin_token))
        assert r.status_code == 200
        docs = r.json()
        assert isinstance(docs, list) and len(docs) > 0
        first = docs[0]
        assert "item_name" in first and "category" in first and "unit" in first


# ----------------- Usage & Stock -----------------
class TestUsageAndStock:
    def test_create_usage_and_stock_states(self, admin_token):
        # create a fresh test item for clean stock math
        name = f"TEST_Stock_{uuid.uuid4().hex[:8]}"
        r = requests.post(f"{API}/items", headers=H(admin_token), json={
            "name": name, "category": "Dairy", "unit": "kg", "reorder_level": 5
        })
        iid = r.json()["id"]
        # buy 10kg
        rp = requests.post(f"{API}/purchases", headers=H(admin_token), json={
            "item_id": iid, "date": "2026-01-10", "quantity": 10, "price_per_unit": 100
        })
        assert rp.status_code == 200
        # stock should be 'in' (10 >= reorder 5)
        stock = requests.get(f"{API}/stock", headers=H(admin_token)).json()
        row = next(s for s in stock if s["item_id"] == iid)
        assert row["qty_left"] == 10 and row["status"] == "in"

        # use 7 -> 3 left, low
        ru = requests.post(f"{API}/usage", headers=H(admin_token), json={
            "item_id": iid, "date": "2026-01-11", "quantity_used": 7
        })
        assert ru.status_code == 200
        stock = requests.get(f"{API}/stock", headers=H(admin_token)).json()
        row = next(s for s in stock if s["item_id"] == iid)
        assert abs(row["qty_left"] - 3) < 1e-6
        assert row["status"] == "low"

        # use 3 -> 0 left, out
        requests.post(f"{API}/usage", headers=H(admin_token), json={
            "item_id": iid, "date": "2026-01-12", "quantity_used": 3
        })
        stock = requests.get(f"{API}/stock", headers=H(admin_token)).json()
        row = next(s for s in stock if s["item_id"] == iid)
        assert row["qty_left"] == 0 and row["status"] == "out"

    def test_stock_count(self, admin_token):
        stock = requests.get(f"{API}/stock", headers=H(admin_token)).json()
        assert len(stock) >= 33

    def test_alerts_only_low_out(self, admin_token):
        alerts = requests.get(f"{API}/alerts", headers=H(admin_token)).json()
        for a in alerts:
            assert a["status"] in ("low", "out")
        # out items should come before low items
        statuses = [a["status"] for a in alerts]
        if "out" in statuses and "low" in statuses:
            assert statuses.index("out") < statuses.index("low")


# ----------------- Sales -----------------
class TestSales:
    def test_create_sales_and_duplicate(self, admin_token):
        date = f"2026-01-{uuid.uuid4().int % 28 + 1:02d}"
        # First ensure no entry
        requests.get(f"{API}/sales/check/{date}", headers=H(admin_token))
        r = requests.post(f"{API}/sales", headers=H(admin_token), json={
            "date": date, "lunch_amount": 1000, "dinner_amount": 2000, "other_amount": 500
        })
        if r.status_code == 409:
            pytest.skip("Date collision in test; rerun")
        assert r.status_code == 200
        data = r.json()
        assert data["total_amount"] == 3500.0
        # duplicate
        r2 = requests.post(f"{API}/sales", headers=H(admin_token), json={
            "date": date, "lunch_amount": 1, "dinner_amount": 2, "other_amount": 0
        })
        assert r2.status_code == 409

    def test_sales_check(self, admin_token):
        date = "2030-12-31"  # unlikely date
        r = requests.get(f"{API}/sales/check/{date}", headers=H(admin_token))
        assert r.status_code == 200
        assert r.json()["exists"] is False


# ----------------- Dashboard -----------------
class TestDashboard:
    def test_admin_dashboard(self, admin_token):
        r = requests.get(f"{API}/dashboard", headers=H(admin_token))
        assert r.status_code == 200
        d = r.json()
        for k in ["total_spent", "total_sales", "profit", "today_sales",
                  "low_stock_count", "out_of_stock_count", "category_spend",
                  "sales_trend", "top_items", "stock_health"]:
            assert k in d
        assert isinstance(d["sales_trend"], list) and len(d["sales_trend"]) == 30


# ----------------- Categories & Units -----------------
class TestCategoriesUnits:
    def test_list_categories(self, admin_token):
        r = requests.get(f"{API}/categories", headers=H(admin_token))
        assert r.status_code == 200
        assert len(r.json()) >= 9

    def test_create_category_admin_only(self, admin_token, staff_token):
        name = f"TEST_Cat_{uuid.uuid4().hex[:6]}"
        r_staff = requests.post(f"{API}/categories", headers=H(staff_token), json={"name": name})
        assert r_staff.status_code == 403
        r = requests.post(f"{API}/categories", headers=H(admin_token), json={"name": name})
        assert r.status_code == 200

    def test_list_units(self, admin_token):
        r = requests.get(f"{API}/units", headers=H(admin_token))
        assert r.status_code == 200
        assert len(r.json()) >= 9

    def test_create_unit_admin_only(self, admin_token, staff_token):
        name = f"TEST_U_{uuid.uuid4().hex[:6]}"
        r_staff = requests.post(f"{API}/units", headers=H(staff_token), json={"name": name})
        assert r_staff.status_code == 403
        r = requests.post(f"{API}/units", headers=H(admin_token), json={"name": name})
        assert r.status_code == 200


# ----------------- Business Profile -----------------
class TestBusinessProfile:
    def test_get_profile(self, admin_token):
        r = requests.get(f"{API}/business-profile", headers=H(admin_token))
        assert r.status_code == 200
        assert "name" in r.json()

    def test_patch_profile_admin_only(self, admin_token, staff_token):
        r_staff = requests.patch(f"{API}/business-profile", headers=H(staff_token),
                                  json={"phone": "9999999999"})
        assert r_staff.status_code == 403
        r = requests.patch(f"{API}/business-profile", headers=H(admin_token),
                           json={"phone": "9999999999"})
        assert r.status_code == 200
        assert r.json()["phone"] == "9999999999"


# ----------------- Users -----------------
class TestUsers:
    def test_create_and_update_user(self, admin_token):
        email = f"test_{uuid.uuid4().hex[:6]}@sprojal.com"
        r = requests.post(f"{API}/users", headers=H(admin_token), json={
            "name": "Test", "email": email, "password": "Test@1234", "role": "staff"
        })
        assert r.status_code == 200
        uid = r.json()["id"]
        # reset password
        rp = requests.post(f"{API}/users/{uid}/reset-password", headers=H(admin_token),
                            json={"new_password": "NewPass1!"})
        assert rp.status_code == 200
        # update name
        ru = requests.patch(f"{API}/users/{uid}", headers=H(admin_token),
                            json={"name": "Updated"})
        assert ru.status_code == 200
        assert ru.json()["name"] == "Updated"


# ----------------- Bulk Reorder -----------------
class TestBulkReorder:
    def test_bulk_reorder(self, admin_token):
        items = requests.get(f"{API}/items", headers=H(admin_token)).json()
        sample = items[:3]
        updates = [{"item_id": i["id"], "reorder_level": 99.0} for i in sample]
        r = requests.post(f"{API}/items/bulk-reorder", headers=H(admin_token),
                          json={"updates": updates})
        assert r.status_code == 200
        assert r.json()["updated"] == 3
        # verify
        items2 = requests.get(f"{API}/items", headers=H(admin_token)).json()
        by_id = {i["id"]: i for i in items2}
        for u in updates:
            assert by_id[u["item_id"]]["reorder_level"] == 99.0


# ----------------- Staff data isolation -----------------
class TestStaffIsolation:
    def test_staff_sees_only_own_purchases(self, admin_token, staff_token):
        # admin creates a purchase
        items = requests.get(f"{API}/items", headers=H(admin_token)).json()
        iid = items[0]["id"]
        requests.post(f"{API}/purchases", headers=H(admin_token), json={
            "item_id": iid, "date": "2026-01-09", "quantity": 1, "price_per_unit": 10
        })
        # staff creates one
        requests.post(f"{API}/purchases", headers=H(staff_token), json={
            "item_id": iid, "date": "2026-01-09", "quantity": 2, "price_per_unit": 20
        })
        staff_list = requests.get(f"{API}/purchases", headers=H(staff_token)).json()
        # All entries should be created_by staff user
        me = requests.get(f"{API}/auth/me", headers=H(staff_token)).json()
        for p in staff_list:
            assert p.get("created_by") == me["id"], \
                f"Staff sees foreign purchase: {p}"
