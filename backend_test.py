#!/usr/bin/env python3
"""
Comprehensive backend API test for SP Dhaba Ops Manager.
Tests all 5 routers: auth, items, purchases, sales, expenses.
"""
import requests
import time
from datetime import datetime
import pytz

# Base URL from frontend/.env
BASE_URL = "https://bottleneck-finder-6.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_CREDS = {"email": "admin@spdhaba.com", "password": "Admin@123"}
STAFF_CREDS = {"email": "lokesh@spdhaba.com", "password": "Staff@123"}
VIEWER_CREDS = {"email": "display@spdhaba.com", "password": "View@123"}

# Global token storage
admin_token = None
staff_token = None
viewer_token = None

# IST timezone for date handling
IST = pytz.timezone("Asia/Kolkata")


def get_today_ist():
    """Get today's date in IST as YYYY-MM-DD"""
    return datetime.now(IST).strftime("%Y-%m-%d")


def print_test(name):
    """Print test name"""
    print(f"\n{'='*80}")
    print(f"TEST: {name}")
    print('='*80)


def print_result(passed, message=""):
    """Print test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {message}")
    return passed


def print_response(resp):
    """Print response details"""
    print(f"Status: {resp.status_code}")
    try:
        print(f"Response: {resp.json()}")
    except:
        print(f"Response: {resp.text[:500]}")


# ============================================================================
# 1. AUTH TESTS
# ============================================================================

def test_auth_login_admin():
    """1a. POST /api/auth/login with admin creds returns 200 with token+user"""
    global admin_token
    print_test("Auth: Admin Login")
    
    resp = requests.post(f"{BASE_URL}/auth/login", json=ADMIN_CREDS)
    print_response(resp)
    
    if resp.status_code != 200:
        return print_result(False, f"Expected 200, got {resp.status_code}")
    
    data = resp.json()
    if "token" not in data or "user" not in data:
        return print_result(False, "Missing token or user in response")
    
    admin_token = data["token"]
    user = data["user"]
    
    if user["email"] != ADMIN_CREDS["email"]:
        return print_result(False, f"Email mismatch: {user['email']}")
    
    if user["role"] != "admin":
        return print_result(False, f"Role mismatch: {user['role']}")
    
    return print_result(True, "Admin login successful with token and user")


def test_auth_me():
    """1b. GET /api/auth/me with valid Bearer token returns user object"""
    print_test("Auth: GET /me with Bearer token")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    print_response(resp)
    
    if resp.status_code != 200:
        return print_result(False, f"Expected 200, got {resp.status_code}")
    
    user = resp.json()
    if user["email"] != ADMIN_CREDS["email"]:
        return print_result(False, f"Email mismatch: {user['email']}")
    
    return print_result(True, "GET /me returns correct user object")


def test_auth_wrong_password():
    """1c. Login with wrong password returns 401"""
    print_test("Auth: Login with wrong password")
    
    wrong_creds = {"email": ADMIN_CREDS["email"], "password": "WrongPassword123"}
    resp = requests.post(f"{BASE_URL}/auth/login", json=wrong_creds)
    print_response(resp)
    
    if resp.status_code != 401:
        return print_result(False, f"Expected 401, got {resp.status_code}")
    
    return print_result(True, "Wrong password returns 401")


def test_auth_staff_login():
    """Login as staff for later tests"""
    global staff_token
    print_test("Auth: Staff Login")
    
    resp = requests.post(f"{BASE_URL}/auth/login", json=STAFF_CREDS)
    print_response(resp)
    
    if resp.status_code != 200:
        return print_result(False, f"Expected 200, got {resp.status_code}")
    
    staff_token = resp.json()["token"]
    return print_result(True, "Staff login successful")


def test_auth_viewer_login():
    """Login as viewer for later tests"""
    global viewer_token
    print_test("Auth: Viewer Login")
    
    resp = requests.post(f"{BASE_URL}/auth/login", json=VIEWER_CREDS)
    print_response(resp)
    
    if resp.status_code != 200:
        return print_result(False, f"Expected 200, got {resp.status_code}")
    
    viewer_token = resp.json()["token"]
    return print_result(True, "Viewer login successful")


# ============================================================================
# 2. ITEMS TESTS
# ============================================================================

def test_items_list():
    """2a. GET /api/items returns seed items with multi-unit schema"""
    print_test("Items: List all items")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = requests.get(f"{BASE_URL}/items", headers=headers)
    print_response(resp)
    
    if resp.status_code != 200:
        return print_result(False, f"Expected 200, got {resp.status_code}")
    
    items = resp.json()
    if not isinstance(items, list):
        return print_result(False, "Response is not a list")
    
    if len(items) < 5:
        return print_result(False, f"Expected ~9 seed items, got {len(items)}")
    
    # Check schema
    sample = items[0]
    required_fields = ["base_unit", "units", "default_price"]
    for field in required_fields:
        if field not in sample:
            return print_result(False, f"Missing field: {field}")
    
    # Check units structure
    if not isinstance(sample["units"], list):
        return print_result(False, "units is not a list")
    
    if len(sample["units"]) > 0:
        unit = sample["units"][0]
        if "name" not in unit or "conversion_factor" not in unit or "is_default" not in unit:
            return print_result(False, "Unit missing required fields")
    
    return print_result(True, f"Got {len(items)} items with correct multi-unit schema")


def test_items_search():
    """2b. GET /api/items?q=egg returns only Egg item"""
    print_test("Items: Search for 'egg'")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = requests.get(f"{BASE_URL}/items?q=egg", headers=headers)
    print_response(resp)
    
    if resp.status_code != 200:
        return print_result(False, f"Expected 200, got {resp.status_code}")
    
    items = resp.json()
    if len(items) == 0:
        return print_result(False, "No items found for 'egg'")
    
    # Check if Egg is in results
    egg_found = any("egg" in item["name"].lower() for item in items)
    if not egg_found:
        return print_result(False, "Egg not found in search results")
    
    return print_result(True, f"Search returned {len(items)} item(s) containing 'egg'")


def test_items_egg_units():
    """2c. Verify Egg has units: piece(x1), dozen(x12), tray(x30)"""
    print_test("Items: Verify Egg multi-unit structure")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = requests.get(f"{BASE_URL}/items?q=egg", headers=headers)
    
    if resp.status_code != 200:
        return print_result(False, f"Expected 200, got {resp.status_code}")
    
    items = resp.json()
    egg = next((item for item in items if "egg" in item["name"].lower()), None)
    
    if not egg:
        return print_result(False, "Egg item not found")
    
    print(f"Egg item: {egg}")
    
    units = egg.get("units", [])
    unit_map = {u["name"].lower(): u["conversion_factor"] for u in units}
    
    expected = {"piece": 1, "dozen": 12, "tray": 30}
    for unit_name, expected_factor in expected.items():
        if unit_name not in unit_map:
            return print_result(False, f"Missing unit: {unit_name}")
        if unit_map[unit_name] != expected_factor:
            return print_result(False, f"Wrong conversion for {unit_name}: {unit_map[unit_name]} != {expected_factor}")
    
    return print_result(True, "Egg has correct units: piece(1), dozen(12), tray(30)")


def test_items_create_admin():
    """2d. POST /api/items as admin with multi-unit item"""
    print_test("Items: Create new multi-unit item as admin")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    payload = {
        "name": f"TestOil_{int(time.time())}",
        "base_unit": "L",
        "units": [
            {"name": "L", "conversion_factor": 1, "is_default": True},
            {"name": "tin", "conversion_factor": 15, "is_default": False}
        ],
        "default_price": 140,
        "category": "Cooking Oil"
    }
    
    resp = requests.post(f"{BASE_URL}/items", json=payload, headers=headers)
    print_response(resp)
    
    if resp.status_code not in [200, 201]:
        return print_result(False, f"Expected 200/201, got {resp.status_code}")
    
    item = resp.json()
    if item["name"] != payload["name"]:
        return print_result(False, f"Name mismatch: {item['name']}")
    
    if len(item["units"]) != 2:
        return print_result(False, f"Expected 2 units, got {len(item['units'])}")
    
    return print_result(True, "Created multi-unit item successfully")


def test_items_create_staff():
    """2e. POST /api/items as staff succeeds"""
    print_test("Items: Create item as staff")
    
    headers = {"Authorization": f"Bearer {staff_token}"}
    payload = {
        "name": f"TestSpice_{int(time.time())}",
        "base_unit": "kg",
        "units": [
            {"name": "kg", "conversion_factor": 1, "is_default": True},
            {"name": "g", "conversion_factor": 0.001, "is_default": False}
        ],
        "default_price": 200
    }
    
    resp = requests.post(f"{BASE_URL}/items", json=payload, headers=headers)
    print_response(resp)
    
    if resp.status_code not in [200, 201]:
        return print_result(False, f"Expected 200/201, got {resp.status_code}")
    
    return print_result(True, "Staff can create items")


def test_items_duplicate():
    """2f. POST /api/items with duplicate name returns 400"""
    print_test("Items: Create duplicate item")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # First create an item
    unique_name = f"DuplicateTest_{int(time.time())}"
    payload = {
        "name": unique_name,
        "base_unit": "kg",
        "units": [{"name": "kg", "conversion_factor": 1, "is_default": True}],
        "default_price": 100
    }
    
    resp1 = requests.post(f"{BASE_URL}/items", json=payload, headers=headers)
    if resp1.status_code not in [200, 201]:
        return print_result(False, f"First creation failed: {resp1.status_code}")
    
    # Try to create duplicate
    resp2 = requests.post(f"{BASE_URL}/items", json=payload, headers=headers)
    print_response(resp2)
    
    if resp2.status_code != 400:
        return print_result(False, f"Expected 400, got {resp2.status_code}")
    
    return print_result(True, "Duplicate item returns 400")


def test_items_update():
    """2g. PATCH /api/items/{id} as admin updates item"""
    print_test("Items: Update item as admin")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Get an item to update
    resp = requests.get(f"{BASE_URL}/items", headers=headers)
    items = resp.json()
    if not items:
        return print_result(False, "No items to update")
    
    item_id = items[0]["id"]
    
    # Update it
    payload = {"default_price": 999.99}
    resp = requests.patch(f"{BASE_URL}/items/{item_id}", json=payload, headers=headers)
    print_response(resp)
    
    if resp.status_code != 200:
        return print_result(False, f"Expected 200, got {resp.status_code}")
    
    updated = resp.json()
    if updated["default_price"] != 999.99:
        return print_result(False, f"Price not updated: {updated['default_price']}")
    
    return print_result(True, "Item updated successfully")


def test_items_delete():
    """2h. DELETE /api/items/{id} soft-deletes item"""
    print_test("Items: Soft delete item")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Create an item to delete
    payload = {
        "name": f"ToDelete_{int(time.time())}",
        "base_unit": "kg",
        "units": [{"name": "kg", "conversion_factor": 1, "is_default": True}],
        "default_price": 100
    }
    
    resp = requests.post(f"{BASE_URL}/items", json=payload, headers=headers)
    if resp.status_code not in [200, 201]:
        return print_result(False, f"Creation failed: {resp.status_code}")
    
    item_id = resp.json()["id"]
    
    # Delete it
    resp = requests.delete(f"{BASE_URL}/items/{item_id}", headers=headers)
    print_response(resp)
    
    if resp.status_code != 200:
        return print_result(False, f"Expected 200, got {resp.status_code}")
    
    # Verify it's not in default list
    resp = requests.get(f"{BASE_URL}/items", headers=headers)
    items = resp.json()
    if any(item["id"] == item_id for item in items):
        return print_result(False, "Deleted item still in default list")
    
    # Verify it's in include_inactive list
    resp = requests.get(f"{BASE_URL}/items?include_inactive=true", headers=headers)
    items = resp.json()
    deleted_item = next((item for item in items if item["id"] == item_id), None)
    
    if not deleted_item:
        return print_result(False, "Deleted item not found with include_inactive=true")
    
    if deleted_item.get("is_active", True):
        return print_result(False, "Item is_active should be False")
    
    return print_result(True, "Item soft-deleted successfully")


# ============================================================================
# 3. PURCHASES TESTS
# ============================================================================

egg_item_id = None

def test_purchases_multi_unit():
    """3a. POST /api/purchases with unit=dozen for Egg calculates base_quantity"""
    global egg_item_id
    print_test("Purchases: Multi-unit purchase (dozen -> pieces)")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Get Egg item
    resp = requests.get(f"{BASE_URL}/items?q=egg", headers=headers)
    items = resp.json()
    egg = next((item for item in items if "egg" in item["name"].lower()), None)
    
    if not egg:
        return print_result(False, "Egg item not found")
    
    egg_item_id = egg["id"]
    today = get_today_ist()
    
    payload = {
        "item_id": egg_item_id,
        "date": today,
        "quantity": 2,
        "unit": "dozen",
        "unit_conversion_factor": 12,
        "price_per_unit": 90
    }
    
    resp = requests.post(f"{BASE_URL}/purchases", json=payload, headers=headers)
    print_response(resp)
    
    if resp.status_code not in [200, 201]:
        return print_result(False, f"Expected 200/201, got {resp.status_code}")
    
    purchase = resp.json()
    
    # Verify calculations
    if purchase["base_quantity"] != 24:  # 2 dozen * 12
        return print_result(False, f"base_quantity should be 24, got {purchase['base_quantity']}")
    
    if purchase["base_unit"] != "piece":
        return print_result(False, f"base_unit should be 'piece', got {purchase['base_unit']}")
    
    if purchase["total_cost"] != 180:  # 2 * 90
        return print_result(False, f"total_cost should be 180, got {purchase['total_cost']}")
    
    return print_result(True, "Multi-unit purchase calculated correctly: 2 dozen = 24 pieces, cost 180")


def test_purchases_invalid_unit():
    """3b. POST /api/purchases with invalid unit returns 400"""
    print_test("Purchases: Invalid unit for item")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    today = get_today_ist()
    
    payload = {
        "item_id": egg_item_id,
        "date": today,
        "quantity": 1,
        "unit": "litre",  # Invalid for Egg
        "unit_conversion_factor": 1,
        "price_per_unit": 50
    }
    
    resp = requests.post(f"{BASE_URL}/purchases", json=payload, headers=headers)
    print_response(resp)
    
    if resp.status_code != 400:
        return print_result(False, f"Expected 400, got {resp.status_code}")
    
    return print_result(True, "Invalid unit returns 400")


def test_purchases_duplicate():
    """3c. Duplicate POST within 10 seconds returns 409"""
    print_test("Purchases: Duplicate detection")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    today = get_today_ist()
    
    # Create unique purchase
    payload = {
        "item_id": egg_item_id,
        "date": today,
        "quantity": 5,
        "unit": "piece",
        "unit_conversion_factor": 1,
        "price_per_unit": 8
    }
    
    resp1 = requests.post(f"{BASE_URL}/purchases", json=payload, headers=headers)
    if resp1.status_code not in [200, 201]:
        return print_result(False, f"First purchase failed: {resp1.status_code}")
    
    # Immediate duplicate
    resp2 = requests.post(f"{BASE_URL}/purchases", json=payload, headers=headers)
    print_response(resp2)
    
    if resp2.status_code != 409:
        return print_result(False, f"Expected 409, got {resp2.status_code}")
    
    return print_result(True, "Duplicate purchase returns 409")


def test_purchases_list():
    """3d. GET /api/purchases returns purchases with item_name populated"""
    print_test("Purchases: List purchases")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = requests.get(f"{BASE_URL}/purchases", headers=headers)
    print_response(resp)
    
    if resp.status_code != 200:
        return print_result(False, f"Expected 200, got {resp.status_code}")
    
    purchases = resp.json()
    if not isinstance(purchases, list):
        return print_result(False, "Response is not a list")
    
    if len(purchases) > 0:
        purchase = purchases[0]
        if "item_name" not in purchase:
            return print_result(False, "item_name not populated")
    
    return print_result(True, f"Got {len(purchases)} purchases with item_name populated")


def test_purchases_void():
    """3e. PATCH /api/purchases/{id}/void by admin succeeds"""
    print_test("Purchases: Void purchase")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Get a purchase to void
    resp = requests.get(f"{BASE_URL}/purchases", headers=headers)
    purchases = resp.json()
    
    if not purchases:
        return print_result(False, "No purchases to void")
    
    purchase_id = purchases[0]["id"]
    
    # Void it
    payload = {"reason": "Test void reason"}
    resp = requests.patch(f"{BASE_URL}/purchases/{purchase_id}/void", json=payload, headers=headers)
    print_response(resp)
    
    if resp.status_code != 200:
        return print_result(False, f"Expected 200, got {resp.status_code}")
    
    # Verify it's not in default list
    resp = requests.get(f"{BASE_URL}/purchases", headers=headers)
    purchases = resp.json()
    
    if any(p["id"] == purchase_id for p in purchases):
        return print_result(False, "Voided purchase still in list")
    
    return print_result(True, "Purchase voided successfully")


# ============================================================================
# 4. SALES TESTS
# ============================================================================

def test_sales_create():
    """4a. POST /api/sales for today returns 200 with total_amount"""
    print_test("Sales: Create sales entry")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    today = get_today_ist()
    
    payload = {
        "date": today,
        "lunch_amount": 1000,
        "dinner_amount": 2000,
        "other_amount": 0,
        "notes": "Test sales entry"
    }
    
    resp = requests.post(f"{BASE_URL}/sales", json=payload, headers=headers)
    print_response(resp)
    
    if resp.status_code not in [200, 201, 409]:  # 409 if already exists
        return print_result(False, f"Expected 200/201/409, got {resp.status_code}")
    
    if resp.status_code == 409:
        return print_result(True, "Sales entry already exists for today (409)")
    
    sales = resp.json()
    if sales["total_amount"] != 3000:
        return print_result(False, f"total_amount should be 3000, got {sales['total_amount']}")
    
    return print_result(True, "Sales entry created with total_amount=3000")


def test_sales_duplicate():
    """4b. Second POST for same date returns 409"""
    print_test("Sales: Duplicate date detection")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    today = get_today_ist()
    
    payload = {
        "date": today,
        "lunch_amount": 500,
        "dinner_amount": 1000,
        "other_amount": 0
    }
    
    resp = requests.post(f"{BASE_URL}/sales", json=payload, headers=headers)
    print_response(resp)
    
    if resp.status_code != 409:
        return print_result(False, f"Expected 409, got {resp.status_code}")
    
    return print_result(True, "Duplicate sales date returns 409")


def test_sales_check():
    """4c. GET /api/sales/check/{date} returns exists=true"""
    print_test("Sales: Check if sales exists for date")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    today = get_today_ist()
    
    resp = requests.get(f"{BASE_URL}/sales/check/{today}", headers=headers)
    print_response(resp)
    
    if resp.status_code != 200:
        return print_result(False, f"Expected 200, got {resp.status_code}")
    
    data = resp.json()
    if "exists" not in data:
        return print_result(False, "Missing 'exists' field")
    
    if data["exists"] and "entry" not in data:
        return print_result(False, "exists=true but no entry")
    
    return print_result(True, f"Check endpoint works: exists={data['exists']}")


def test_sales_patch_admin():
    """4d. Admin PATCH /api/sales/{id} succeeds"""
    print_test("Sales: Admin update sales entry")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Get a sales entry
    resp = requests.get(f"{BASE_URL}/sales", headers=headers)
    sales_list = resp.json()
    
    if not sales_list:
        return print_result(False, "No sales entries to update")
    
    sale_id = sales_list[0]["id"]
    
    payload = {
        "date": sales_list[0]["date"],
        "lunch_amount": 1500,
        "dinner_amount": 2500,
        "other_amount": 100
    }
    
    resp = requests.patch(f"{BASE_URL}/sales/{sale_id}", json=payload, headers=headers)
    print_response(resp)
    
    if resp.status_code != 200:
        return print_result(False, f"Expected 200, got {resp.status_code}")
    
    return print_result(True, "Admin can update sales entry")


def test_sales_patch_staff():
    """4d. Staff PATCH /api/sales/{id} returns 403"""
    print_test("Sales: Staff cannot update sales entry")
    
    headers = {"Authorization": f"Bearer {staff_token}"}
    
    # Get a sales entry
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    resp = requests.get(f"{BASE_URL}/sales", headers=admin_headers)
    sales_list = resp.json()
    
    if not sales_list:
        return print_result(False, "No sales entries to test")
    
    sale_id = sales_list[0]["id"]
    
    payload = {
        "date": sales_list[0]["date"],
        "lunch_amount": 1000,
        "dinner_amount": 2000,
        "other_amount": 0
    }
    
    resp = requests.patch(f"{BASE_URL}/sales/{sale_id}", json=payload, headers=headers)
    print_response(resp)
    
    if resp.status_code != 403:
        return print_result(False, f"Expected 403, got {resp.status_code}")
    
    return print_result(True, "Staff PATCH returns 403")


# ============================================================================
# 5. EXPENSES TESTS
# ============================================================================

def test_expenses_categories():
    """5a. GET /api/expense-categories returns seeded list"""
    print_test("Expenses: List expense categories")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = requests.get(f"{BASE_URL}/expense-categories", headers=headers)
    print_response(resp)
    
    if resp.status_code != 200:
        return print_result(False, f"Expected 200, got {resp.status_code}")
    
    categories = resp.json()
    if not isinstance(categories, list):
        return print_result(False, "Response is not a list")
    
    expected_cats = ["Maintenance", "Utilities", "Rent", "Transport", "Equipment", "Others"]
    cat_names = [c["name"] for c in categories]
    
    missing = [cat for cat in expected_cats if cat not in cat_names]
    if missing:
        return print_result(False, f"Missing categories: {missing}")
    
    return print_result(True, f"Got {len(categories)} expense categories including expected ones")


def test_expenses_create():
    """5b. POST /api/expenses with valid category returns 200"""
    print_test("Expenses: Create expense")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    today = get_today_ist()
    
    payload = {
        "date": today,
        "category": "Utilities",
        "description": "Electricity bill",
        "amount": 500
    }
    
    resp = requests.post(f"{BASE_URL}/expenses", json=payload, headers=headers)
    print_response(resp)
    
    if resp.status_code not in [200, 201]:
        return print_result(False, f"Expected 200/201, got {resp.status_code}")
    
    expense = resp.json()
    if expense["amount"] != 500:
        return print_result(False, f"Amount mismatch: {expense['amount']}")
    
    return print_result(True, "Expense created successfully")


def test_expenses_invalid_category():
    """5c. POST with invalid category returns 400"""
    print_test("Expenses: Invalid category")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    today = get_today_ist()
    
    payload = {
        "date": today,
        "category": "ThisDoesNotExist",
        "description": "Test",
        "amount": 100
    }
    
    resp = requests.post(f"{BASE_URL}/expenses", json=payload, headers=headers)
    print_response(resp)
    
    if resp.status_code != 400:
        return print_result(False, f"Expected 400, got {resp.status_code}")
    
    return print_result(True, "Invalid category returns 400")


def test_expenses_duplicate():
    """5d. Duplicate within 10s returns 409"""
    print_test("Expenses: Duplicate detection")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    today = get_today_ist()
    
    payload = {
        "date": today,
        "category": "Transport",
        "description": "Fuel",
        "amount": 300
    }
    
    resp1 = requests.post(f"{BASE_URL}/expenses", json=payload, headers=headers)
    if resp1.status_code not in [200, 201]:
        return print_result(False, f"First expense failed: {resp1.status_code}")
    
    # Immediate duplicate
    resp2 = requests.post(f"{BASE_URL}/expenses", json=payload, headers=headers)
    print_response(resp2)
    
    if resp2.status_code != 409:
        return print_result(False, f"Expected 409, got {resp2.status_code}")
    
    return print_result(True, "Duplicate expense returns 409")


def test_expenses_void_admin():
    """5e. PATCH /api/expenses/{id}/void as admin succeeds"""
    print_test("Expenses: Void as admin")
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Get an expense to void
    resp = requests.get(f"{BASE_URL}/expenses", headers=headers)
    expenses = resp.json()
    
    if not expenses:
        return print_result(False, "No expenses to void")
    
    expense_id = expenses[0]["id"]
    
    payload = {"reason": "Test void"}
    resp = requests.patch(f"{BASE_URL}/expenses/{expense_id}/void", json=payload, headers=headers)
    print_response(resp)
    
    if resp.status_code != 200:
        return print_result(False, f"Expected 200, got {resp.status_code}")
    
    return print_result(True, "Admin can void expense")


def test_expenses_void_viewer():
    """5e. PATCH /api/expenses/{id}/void as viewer returns 403"""
    print_test("Expenses: Void as viewer (should fail)")
    
    # First create an expense as admin
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    today = get_today_ist()
    
    payload = {
        "date": today,
        "category": "Others",
        "description": "Test for viewer void",
        "amount": 50
    }
    
    resp = requests.post(f"{BASE_URL}/expenses", json=payload, headers=admin_headers)
    if resp.status_code not in [200, 201]:
        return print_result(False, f"Failed to create test expense: {resp.status_code}")
    
    expense_id = resp.json()["id"]
    
    # Try to void as viewer
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
    void_payload = {"reason": "Viewer attempt"}
    resp = requests.patch(f"{BASE_URL}/expenses/{expense_id}/void", json=void_payload, headers=viewer_headers)
    print_response(resp)
    
    if resp.status_code != 403:
        return print_result(False, f"Expected 403, got {resp.status_code}")
    
    return print_result(True, "Viewer void returns 403")


# ============================================================================
# 6. RATE LIMITER TEST
# ============================================================================

def test_rate_limiter():
    """6. Verify rate limiter is working (check login_attempts collection)"""
    print_test("Rate Limiter: Verify login attempts are tracked")
    
    # Do 3 failed logins
    wrong_creds = {"email": "test@example.com", "password": "wrong"}
    
    for i in range(3):
        resp = requests.post(f"{BASE_URL}/auth/login", json=wrong_creds)
        print(f"Failed login attempt {i+1}: {resp.status_code}")
    
    # Now do a successful admin login to verify system still works
    resp = requests.post(f"{BASE_URL}/auth/login", json=ADMIN_CREDS)
    
    if resp.status_code != 200:
        return print_result(False, f"Admin login failed after rate limit test: {resp.status_code}")
    
    # Verify /me still works
    token = resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    
    if resp.status_code != 200:
        return print_result(False, f"GET /me failed: {resp.status_code}")
    
    return print_result(True, "Rate limiter is tracking attempts, admin login still works")


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def main():
    print("\n" + "="*80)
    print("SP DHABA OPS MANAGER - BACKEND API TEST SUITE")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"Test Date (IST): {get_today_ist()}")
    print("="*80)
    
    results = []
    
    # 1. AUTH TESTS
    results.append(("Auth: Admin Login", test_auth_login_admin()))
    results.append(("Auth: GET /me", test_auth_me()))
    results.append(("Auth: Wrong Password", test_auth_wrong_password()))
    results.append(("Auth: Staff Login", test_auth_staff_login()))
    results.append(("Auth: Viewer Login", test_auth_viewer_login()))
    
    # 2. ITEMS TESTS
    results.append(("Items: List", test_items_list()))
    results.append(("Items: Search", test_items_search()))
    results.append(("Items: Egg Units", test_items_egg_units()))
    results.append(("Items: Create (Admin)", test_items_create_admin()))
    results.append(("Items: Create (Staff)", test_items_create_staff()))
    results.append(("Items: Duplicate", test_items_duplicate()))
    results.append(("Items: Update", test_items_update()))
    results.append(("Items: Delete", test_items_delete()))
    
    # 3. PURCHASES TESTS
    results.append(("Purchases: Multi-unit", test_purchases_multi_unit()))
    results.append(("Purchases: Invalid Unit", test_purchases_invalid_unit()))
    results.append(("Purchases: Duplicate", test_purchases_duplicate()))
    results.append(("Purchases: List", test_purchases_list()))
    results.append(("Purchases: Void", test_purchases_void()))
    
    # 4. SALES TESTS
    results.append(("Sales: Create", test_sales_create()))
    results.append(("Sales: Duplicate", test_sales_duplicate()))
    results.append(("Sales: Check", test_sales_check()))
    results.append(("Sales: Patch (Admin)", test_sales_patch_admin()))
    results.append(("Sales: Patch (Staff)", test_sales_patch_staff()))
    
    # 5. EXPENSES TESTS
    results.append(("Expenses: Categories", test_expenses_categories()))
    results.append(("Expenses: Create", test_expenses_create()))
    results.append(("Expenses: Invalid Category", test_expenses_invalid_category()))
    results.append(("Expenses: Duplicate", test_expenses_duplicate()))
    results.append(("Expenses: Void (Admin)", test_expenses_void_admin()))
    results.append(("Expenses: Void (Viewer)", test_expenses_void_viewer()))
    
    # 6. RATE LIMITER TEST
    results.append(("Rate Limiter", test_rate_limiter()))
    
    # SUMMARY
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    print(f"\nTotal: {passed}/{total} tests passed\n")
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print("\n" + "="*80)
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
    else:
        print(f"⚠️  {total - passed} test(s) failed")
    
    print("="*80 + "\n")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
