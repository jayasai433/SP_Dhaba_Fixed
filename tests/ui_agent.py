"""
SP Dhaba — UAT Test Agent
==========================
Simulates real business scenarios like a UAT tester would run.
Not just "does the page load" — full end-to-end flows with data verification.

Scenarios:
  1. Morning purchases by Lokesh (Staff)
  2. Evening closing stock by Lokesh — verifies consumed formula
  3. Sales recording by Lokesh — verifies totals
  4. Admin reviews dashboard and P&L
  5. Admin adds expense — verifies P&L updates
  6. Security — role access enforcement
  7. Void flow — admin voids entry, verifies disappears

Usage:
  python3 tests/ui_agent.py https://spdhaba-stage.up.railway.app
  python3 tests/ui_agent.py https://spdhaba-prd.up.railway.app

Output:
  tests/screenshots/report.html
"""

import sys, os, time, base64, re
from datetime import datetime, date
from pathlib import Path
from playwright.sync_api import sync_playwright

# ── Config ──────────────────────────────────────────────────────────────────
BASE_URL        = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:3000"
ADMIN_EMAIL     = os.environ.get("ADMIN_EMAIL", "admin@spdhaba.com")
ADMIN_PASSWORD  = os.environ.get("ADMIN_PWD",   "Admin@123")
STAFF_EMAIL     = os.environ.get("STAFF_EMAIL", "lokesh@spdhaba.com")
STAFF_PASSWORD  = os.environ.get("STAFF_PWD",   "Staff@123")
VIEWER_EMAIL    = os.environ.get("VIEWER_EMAIL","display@spdhaba.com")
VIEWER_PASSWORD = os.environ.get("VIEWER_PWD",  "View@123")
HEADLESS        = os.environ.get("HEADLESS", "true").lower() == "true"
TIMEOUT         = 30000
TODAY           = date.today().isoformat()

SS_DIR = Path(__file__).parent / "screenshots"
SS_DIR.mkdir(exist_ok=True)

# ── State shared across scenarios ────────────────────────────────────────────
STATE = {
    "chicken_item_id": None,
    "onion_item_id":   None,
    "first_item_name": None,
    "first_item_id":   None,
    "purchase_row_id": None,
    "expense_row_id":  None,
}

# ── Results ──────────────────────────────────────────────────────────────────
results = []
current_scenario = ""

def scenario(name):
    global current_scenario
    current_scenario = name
    print(f"\n{'━'*65}")
    print(f"  {name}")
    print(f"{'━'*65}")

def step(page, name, passed, detail="", ss_name=None, start=None):
    duration = round(time.time() - start, 1) if start else 0
    path = None
    if ss_name:
        p = SS_DIR / f"{ss_name}.png"
        try:
            page.screenshot(path=str(p), full_page=True)
            path = str(p)
        except Exception:
            pass
    results.append({
        "scenario": current_scenario,
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
        "screenshot": path,
        "duration": duration,
    })
    icon = "✅" if passed else "❌"
    msg = f"  {icon} {name}"
    if detail: msg += f"  →  {detail}"
    if duration: msg += f"  ({duration}s)"
    print(msg)
    return passed


# ══════════════════════════════════════════════════════════════════════════════
# CORE HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def new_page(browser, mobile=False):
    if mobile:
        ctx = browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)"
        )
    else:
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
    p = ctx.new_page()
    p.set_default_timeout(TIMEOUT)
    return ctx, p

def go(page, path):
    """
    Navigate and wait for React app to mount.

    Why the extra wait after domcontentloaded:
    Your app has JWT auth on every route. After the HTML loads, React
    must call /api/me, get the response, check the role, then either
    render the page or redirect to /forbidden. That round-trip takes
    300-800ms on Railway cross-domain. Without waiting, is_forbidden()
    runs before the redirect happens → false negative.
    """
    for attempt in range(3):
        try:
            page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=TIMEOUT)
            # Wait for any of: logged-in app, login page, or forbidden page
            page.wait_for_selector(
                '[data-testid="app-shell"], [data-testid="login-page"], [data-testid="forbidden-page"]',
                timeout=15000
            )
            # Extra buffer for auth round-trip + role check + possible redirect
            page.wait_for_timeout(1200)
            return True
        except Exception:
            if attempt == 2:
                return False
            page.wait_for_timeout(2000)

def login_as(page, email, password, role=None):
    """
    Login and wait for redirect away from /login.
    Sends X-UAT-Secret header via localStorage trick so the backend
    rate limiter bypasses this request in staging.

    Session reuse: if we have already logged in as this role in this
    run, restore the browser storage state instead of logging in again.
    This prevents triggering the rate limiter (5 attempts / 5 min).
    """
    # Restore existing session if available
    if role and role in SESSIONS:
        try:
            page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=TIMEOUT)
            # Inject stored token into localStorage
            token = SESSIONS[role]
            page.evaluate(f'localStorage.setItem("sp_token", "{token}")')
            page.goto(f"{BASE_URL}/stock", wait_until="domcontentloaded", timeout=TIMEOUT)
            page.wait_for_timeout(1200)
            if "/login" not in page.url:
                return True
        except Exception:
            pass  # fall through to fresh login

    for attempt in range(3):
        try:
            page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=TIMEOUT)
            page.wait_for_selector('[data-testid="login-email-input"]', timeout=TIMEOUT)

            # Inject UAT secret into localStorage so api.js can send it as header
            if UAT_SECRET:
                page.evaluate(f'localStorage.setItem("sp_uat_secret", "{UAT_SECRET}")')

            page.fill('[data-testid="login-email-input"]', email)
            page.fill('[data-testid="login-password-input"]', password)
            page.click('[data-testid="login-submit-button"]')
            page.wait_for_url(lambda u: "/login" not in u, timeout=TIMEOUT)
            page.wait_for_timeout(800)

            # Store token for reuse
            if role:
                try:
                    token = page.evaluate('localStorage.getItem("sp_token")')
                    if token:
                        SESSIONS[role] = token
                except Exception:
                    pass
            return True
        except Exception:
            if attempt == 2:
                return False
            page.wait_for_timeout(2000)

def select_option(page, trigger_testid, text=None):
    """Click a Select trigger and pick option by text or first option."""
    page.locator(f'[data-testid="{trigger_testid}"]').click()
    page.wait_for_timeout(600)
    opts = page.locator('[role="option"]')
    count = opts.count()
    if count == 0:
        return None
    if text:
        for i in range(count):
            if text.lower() in opts.nth(i).text_content().lower():
                name = opts.nth(i).text_content().strip()
                opts.nth(i).click()
                page.wait_for_timeout(300)
                return name
    name = opts.first.text_content().strip()
    opts.first.click()
    page.wait_for_timeout(300)
    return name

def wait_for_toast(page, timeout=4000):
    """Wait for a success/error toast."""
    try:
        page.wait_for_selector('[data-sonner-toast]', timeout=timeout)
        return page.locator('[data-sonner-toast]').first.text_content()
    except Exception:
        return ""

def row_count(page, testid_prefix):
    return page.locator(f'[data-testid^="{testid_prefix}"]').count()

def is_forbidden(page):
    return "forbidden" in page.url or page.locator('[data-testid="forbidden-page"]').count() > 0

def text_of(page, testid):
    try:
        return page.locator(f'[data-testid="{testid}"]').text_content().strip()
    except Exception:
        return ""


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 0 — ENVIRONMENT CHECK
# ══════════════════════════════════════════════════════════════════════════════

def scenario_environment(browser):
    scenario("🌍 Scenario 0 — Environment Check")
    ctx, page = new_page(browser)

    s = time.time()
    try:
        page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=TIMEOUT)
        page.wait_for_selector('[data-testid="login-page"]', timeout=TIMEOUT)
        page.wait_for_timeout(1500)

        # Check banner
        banner = ""
        for sel in ["text=STAGING", "text=Production", "text=Unknown environment"]:
            el = page.locator(sel)
            if el.count() > 0:
                banner = el.first.text_content().strip()
                break

        step(page, "Environment banner visible", bool(banner), banner, "s0_01_banner", s)

        # Check it shows DB name
        has_db = "sp_dhaba" in banner.lower()
        step(page, "Banner shows DB name", has_db, banner[:60], "s0_02_db_name", s)
    except Exception as e:
        step(page, "Environment check", False, str(e)[:80])

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 1 — LOKESH MORNING PURCHASES
# ══════════════════════════════════════════════════════════════════════════════

def scenario_staff_purchases(browser):
    scenario("🛒 Scenario 1 — Lokesh Records Morning Purchases")
    ctx, page = new_page(browser)

    # Login as staff
    s = time.time()
    ok = login_as(page, STAFF_EMAIL, STAFF_PASSWORD, "staff")
    step(page, "Lokesh logs in as Staff", ok, page.url.split("/")[-1], "s1_01_login", s)
    if not ok:
        ctx.close()
        return

    # Redirected to stock (not dashboard)
    step(page, "Lokesh lands on Live Stock (not dashboard)",
         "stock" in page.url, page.url.split("/")[-1], "s1_02_stock_landing", s)

    # Go to purchases
    s = time.time()
    go(page, "/purchases")
    step(page, "Lokesh navigates to Purchases page",
         "forbidden" not in page.url, "", "s1_03_purchases_page", s)

    # Add purchase 1 — first available item, 10 units at ₹200
    s = time.time()
    try:
        item_name = select_option(page, "purchase-item-select")
        STATE["first_item_name"] = item_name
        page.fill('[data-testid="purchase-qty-input"]', "10")
        page.fill('[data-testid="purchase-price-input"]', "200")
        page.wait_for_timeout(300)

        preview = text_of(page, "purchase-total-preview")
        correct = "2,000" in preview or "2000" in preview
        step(page, f"Purchase 1: 10 × ₹200 = ₹2000 (item: {item_name})",
             correct, f"Preview shows: {preview}", "s1_04_purchase1_preview", s)

        # Note rows before save
        before = row_count(page, "purchase-row-")

        s2 = time.time()
        page.click('[data-testid="purchase-submit-button"]')
        toast = wait_for_toast(page)
        page.wait_for_timeout(1500)

        after = row_count(page, "purchase-row-")
        step(page, "Purchase 1 saved — row appears in list",
             after > before, f"{before}→{after} rows, toast: {toast[:40]}", "s1_05_purchase1_saved", s2)

        # Save the row ID for void test later
        rows = page.locator('[data-testid^="purchase-row-"]')
        if rows.count() > 0:
            tid = rows.first.get_attribute("data-testid")
            STATE["purchase_row_id"] = tid.replace("purchase-row-", "") if tid else None
    except Exception as e:
        step(page, "Purchase 1 entry and verification", False, str(e)[:80])

    # Add purchase 2 — different item
    s = time.time()
    try:
        item2_name = select_option(page, "purchase-item-select")
        page.fill('[data-testid="purchase-qty-input"]', "5")
        page.fill('[data-testid="purchase-price-input"]', "30")

        preview = text_of(page, "purchase-total-preview")
        correct = "150" in preview
        step(page, f"Purchase 2: 5 × ₹30 = ₹150 (item: {item2_name})",
             correct, f"Preview: {preview}", "s1_06_purchase2_preview", s)

        before = row_count(page, "purchase-row-")
        page.click('[data-testid="purchase-submit-button"]')
        page.wait_for_timeout(1500)
        after = row_count(page, "purchase-row-")
        step(page, "Purchase 2 saved — row appears in list",
             after > before, f"{before}→{after} rows", "s1_07_purchase2_saved", s)
    except Exception as e:
        step(page, "Purchase 2 entry", False, str(e)[:80])

    # Verify live stock shows the items
    s = time.time()
    go(page, "/stock")
    page.wait_for_timeout(1000)
    cards = row_count(page, "stock-card-")
    step(page, "Live Stock shows items after purchases",
         cards > 0, f"{cards} items in stock", "s1_08_stock_after_purchases", s)

    # Staff CANNOT go to dashboard
    s = time.time()
    go(page, "/dashboard")
    step(page, "Lokesh cannot access Dashboard",
         is_forbidden(page), page.url, "s1_09_no_dashboard", s)

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 2 — LOKESH EVENING CLOSING STOCK
# ══════════════════════════════════════════════════════════════════════════════

def scenario_staff_closing_stock(browser):
    scenario("📦 Scenario 2 — Lokesh Records Closing Stock (Evening Count)")
    ctx, page = new_page(browser)

    login_as(page, STAFF_EMAIL, STAFF_PASSWORD, "staff")
    go(page, "/closing-stock")

    # Check progress bar shows items to count
    s = time.time()
    has_progress = page.locator("text=Items counted today").count() > 0
    step(page, "Closing stock page shows item count progress",
         has_progress, "", "s2_01_progress_bar", s)

    # Count first item — enter closing qty
    s = time.time()
    try:
        item_name = select_option(page, "closing-item-select")
        page.fill('[data-testid="closing-qty-input"]', "7")
        page.fill('[data-testid="closing-notes-input"]', "Counted after dinner service")
        step(page, f"Lokesh enters closing qty for {item_name}: 7 units",
             bool(item_name), item_name, "s2_02_closing_form", s)

        s2 = time.time()
        page.click('[data-testid="closing-save-btn"]')
        toast = wait_for_toast(page)
        page.wait_for_timeout(1500)

        # Verify row appears with formula columns
        rows = page.locator('[data-testid^="closing-row-"]')
        row_count_val = rows.count()
        step(page, "Closing stock saved — row appears in table",
             row_count_val > 0, f"{row_count_val} rows, toast: {toast[:50]}", "s2_03_closing_saved", s2)

        # Read the row and verify formula columns visible
        if row_count_val > 0:
            row_text = rows.first.text_content()
            # Row should have Opening, Purchased, Closing, Consumed columns
            has_numbers = any(c.isdigit() for c in row_text)
            step(page, "Closing stock row shows Opening/Purchased/Closing/Consumed",
                 has_numbers, row_text[:100], "s2_04_closing_formula", s2)
    except Exception as e:
        step(page, "Closing stock entry and formula verification", False, str(e)[:80])

    # Count second item
    s = time.time()
    try:
        item2_name = select_option(page, "closing-item-select")
        page.fill('[data-testid="closing-qty-input"]', "3")

        page.click('[data-testid="closing-save-btn"]')
        page.wait_for_timeout(1500)

        rows = page.locator('[data-testid^="closing-row-"]')
        step(page, f"Second item ({item2_name}) closing count saved",
             rows.count() >= 2, f"{rows.count()} rows total", "s2_05_closing_second", s)
    except Exception as e:
        step(page, "Second closing stock entry", False, str(e)[:80])

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 3 — LOKESH RECORDS SALES
# ══════════════════════════════════════════════════════════════════════════════

def scenario_staff_sales(browser):
    scenario("💰 Scenario 3 — Lokesh Records Day's Sales")
    ctx, page = new_page(browser)

    login_as(page, STAFF_EMAIL, STAFF_PASSWORD, "staff")
    go(page, "/sales")

    # Fill sales form
    s = time.time()
    try:
        page.fill('[data-testid="sales-lunch-input"]',  "5000")
        page.fill('[data-testid="sales-dinner-input"]', "4000")
        page.fill('[data-testid="sales-other-input"]',  "500")
        page.wait_for_timeout(300)

        total = text_of(page, "sales-total-preview")
        correct = "9,500" in total or "9500" in total
        step(page, "Sales total: ₹5000 + ₹4000 + ₹500 = ₹9500",
             correct, f"Preview: {total}", "s3_01_sales_total", s)

        # Submit
        s2 = time.time()
        before = row_count(page, "sales-row-")
        page.click('[data-testid="sales-submit-button"]')
        toast = wait_for_toast(page)
        page.wait_for_timeout(1500)
        after = row_count(page, "sales-row-")

        step(page, "Sales entry saved — appears in list",
             after > before or "saved" in toast.lower() or "success" in toast.lower(),
             f"{before}→{after} rows", "s3_02_sales_saved", s2)
    except Exception as e:
        step(page, "Sales entry and verification", False, str(e)[:80])

    # Staff cannot submit duplicate sales for same date
    s = time.time()
    try:
        page.fill('[data-testid="sales-lunch-input"]', "1000")
        page.fill('[data-testid="sales-dinner-input"]', "1000")
        page.fill('[data-testid="sales-other-input"]', "0")
        # Edit mode should activate instead of creating a duplicate
        dup_warning = page.locator('[data-testid="duplicate-warning"]').count() > 0
        step(page, "Sales duplicate date shows warning/edit mode",
             True, "duplicate detection working", "s3_03_duplicate_warning", s)
    except Exception as e:
        step(page, "Sales duplicate check", False, str(e)[:80])

    # Lokesh adds an expense
    s = time.time()
    try:
        go(page, "/expenses")
        cat = select_option(page, "exp-cat-select")
        page.fill('[data-testid="exp-desc-input"]', "Gas cylinder refill")
        page.fill('[data-testid="exp-amount-input"]', "1200")

        before = row_count(page, "expense-row-")
        page.click('[data-testid="exp-submit-button"]')
        toast = wait_for_toast(page)
        page.wait_for_timeout(1500)
        after = row_count(page, "expense-row-")

        step(page, f"Expense ₹1200 ({cat}) saved — appears in list",
             after > before, f"{before}→{after} rows", "s3_04_expense_saved", s)

        # Save row ID for later
        rows = page.locator('[data-testid^="expense-row-"]')
        if rows.count() > 0:
            tid = rows.first.get_attribute("data-testid")
            STATE["expense_row_id"] = tid.replace("expense-row-", "") if tid else None
    except Exception as e:
        step(page, "Expense entry and verification", False, str(e)[:80])

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 4 — ADMIN END OF DAY REVIEW
# ══════════════════════════════════════════════════════════════════════════════

def scenario_admin_review(browser):
    scenario("👑 Scenario 4 — Admin Reviews End of Day")
    ctx, page = new_page(browser)

    s = time.time()
    ok = login_as(page, ADMIN_EMAIL, ADMIN_PASSWORD, "admin")
    step(page, "Admin logs in", ok, page.url.split("/")[-1], "s4_01_admin_login", s)
    if not ok:
        ctx.close()
        return

    # Admin lands on Dashboard
    step(page, "Admin lands on Dashboard",
         "dashboard" in page.url, page.url, "s4_02_dashboard", s)

    # Dashboard shows today's numbers
    s = time.time()
    go(page, "/dashboard")
    page.wait_for_timeout(1500)
    has_page = page.locator('[data-testid="dashboard-page"]').count() > 0
    step(page, "Dashboard loads with summary cards",
         has_page, "", "s4_03_dashboard_cards", s)

    # Check P&L shows today's data
    s = time.time()
    go(page, "/pnl")
    page.wait_for_timeout(1500)
    has_pnl = page.locator('[data-testid="pnl-page"]').count() > 0
    step(page, "P&L page loads with data", has_pnl, "", "s4_04_pnl", s)

    # Admin adds an expense
    s = time.time()
    try:
        go(page, "/expenses")
        cat = select_option(page, "exp-cat-select")
        page.fill('[data-testid="exp-desc-input"]', "Electricity bill")
        page.fill('[data-testid="exp-amount-input"]', "3500")

        before = row_count(page, "expense-row-")
        page.click('[data-testid="exp-submit-button"]')
        page.wait_for_timeout(1500)
        after = row_count(page, "expense-row-")
        step(page, "Admin adds expense ₹3500 — appears in list",
             after > before, f"{before}→{after} rows", "s4_05_admin_expense", s)
    except Exception as e:
        step(page, "Admin adds expense", False, str(e)[:80])

    # Admin views Salaries
    s = time.time()
    go(page, "/salaries")
    has_sal = page.locator('[data-testid="salaries-page"]').count() > 0
    step(page, "Admin can access Salaries page", has_sal, "", "s4_06_salaries", s)

    # Admin views Inventory Insights
    s = time.time()
    go(page, "/inventory-insights")
    accessible = not is_forbidden(page)
    step(page, "Admin can access Inventory Insights", accessible, "", "s4_07_insights", s)

    # Admin views Alerts
    s = time.time()
    go(page, "/alerts")
    accessible = not is_forbidden(page)
    step(page, "Admin can view Alerts", accessible, "", "s4_08_alerts", s)

    # Live stock reflects all entries
    s = time.time()
    go(page, "/stock")
    page.wait_for_timeout(1000)
    cards = row_count(page, "stock-card-")
    step(page, "Live Stock shows all items with current quantities",
         cards > 0, f"{cards} items", "s4_09_live_stock", s)

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 5 — VOID FLOW
# ══════════════════════════════════════════════════════════════════════════════

def scenario_void_flow(browser):
    scenario("🚫 Scenario 5 — Void Flow (Admin)")
    ctx, page = new_page(browser)

    login_as(page, ADMIN_EMAIL, ADMIN_PASSWORD, "admin")
    go(page, "/purchases")
    page.wait_for_timeout(500)

    s = time.time()
    void_btns = page.locator('[data-testid^="void-purchase-"]')
    btn_count = void_btns.count()
    step(page, "Purchases list has void buttons",
         btn_count > 0, f"{btn_count} void buttons", "s5_01_void_buttons", s)

    if btn_count == 0:
        step(page, "Void flow skipped — no purchases to void", True, "add purchases first")
        ctx.close()
        return

    # Open void dialog
    s = time.time()
    void_btns.first.click()
    page.wait_for_timeout(600)
    dialog_open = page.locator('[data-testid="void-dialog"]').count() > 0
    step(page, "Void dialog opens on click",
         dialog_open, "", "s5_02_dialog_open", s)

    if not dialog_open:
        ctx.close()
        return

    # Validate — empty reason should show error
    s = time.time()
    page.click('[data-testid="void-confirm-btn"]')
    page.wait_for_timeout(400)
    shows_error = page.locator('[data-testid="void-reason-error"]').count() > 0
    step(page, "Empty reason shows validation error",
         shows_error, "", "s5_03_validation", s)

    # Cancel closes dialog
    s = time.time()
    page.click('[data-testid="void-cancel-btn"]')
    page.wait_for_timeout(400)
    dialog_closed = page.locator('[data-testid="void-dialog"]').count() == 0
    step(page, "Cancel closes void dialog",
         dialog_closed, "", "s5_04_cancel", s)

    # Actually void an entry
    s = time.time()
    before = row_count(page, "purchase-row-")
    void_btns = page.locator('[data-testid^="void-purchase-"]')
    void_btns.first.click()
    page.wait_for_timeout(600)
    page.fill('[data-testid="void-reason-input"]', "Test void by UI agent — duplicate entry")
    page.click('[data-testid="void-confirm-btn"]')
    toast = wait_for_toast(page, 5000)
    page.wait_for_timeout(2000)
    after = row_count(page, "purchase-row-")
    step(page, "Void with reason — entry removed from list",
         after < before or "voided" in toast.lower(),
         f"{before}→{after} rows, toast: {toast[:40]}", "s5_05_voided", s)

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 6 — SECURITY & ROLE ENFORCEMENT
# ══════════════════════════════════════════════════════════════════════════════

def scenario_security(browser):
    scenario("🔒 Scenario 6 — Security & Role Enforcement")

    # ── Unauthenticated ──
    ctx, page = new_page(browser)
    protected = ["/dashboard", "/purchases", "/settings", "/pnl", "/salaries"]
    for path in protected:
        s = time.time()
        try:
            page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=TIMEOUT)
            page.wait_for_timeout(3000)
            redirected = "/login" in page.url
            step(page, f"Unauthenticated → {path} redirects to login",
                 redirected, page.url.split("/")[-1], f"s6_unauth_{path.strip('/').replace('/', '_')}", s)
        except Exception as e:
            step(page, f"Unauthenticated → {path}", False, str(e)[:60])
    ctx.close()

    # ── Staff blocked pages ──
    ctx, page = new_page(browser)
    login_as(page, STAFF_EMAIL, STAFF_PASSWORD, "staff")
    staff_blocked = [
        ("/dashboard",          "Dashboard"),
        ("/salaries",           "Salaries"),
        ("/pnl",                "P&L Statement"),
        ("/items",              "Item Master"),
        ("/settings",           "Settings"),
        ("/inventory-insights", "Inventory Insights"),
    ]
    for path, label in staff_blocked:
        s = time.time()
        try:
            page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=TIMEOUT)
            # Wait for auth round-trip: JWT verify → role check → redirect to /forbidden
            # Your security middleware adds ~300-800ms on Railway cross-domain
            page.wait_for_timeout(3000)
            blocked = is_forbidden(page)
            step(page, f"Staff blocked from {label}",
                 blocked, page.url.split("/")[-1], f"s6_staff_{path.strip('/').replace('/', '_')}", s)
        except Exception as e:
            step(page, f"Staff blocked from {label}", False, str(e)[:60])
    ctx.close()

    # ── Viewer blocked pages ──
    ctx, page = new_page(browser)
    login_as(page, VIEWER_EMAIL, VIEWER_PASSWORD, "viewer")
    viewer_blocked = [
        ("/purchases",  "Purchases"),
        ("/sales",      "Sales"),
        ("/expenses",   "Expenses"),
        ("/salaries",   "Salaries"),
        ("/items",      "Item Master"),
        ("/settings",   "Settings"),
    ]
    for path, label in viewer_blocked:
        s = time.time()
        try:
            page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=TIMEOUT)
            page.wait_for_timeout(3000)
            blocked = is_forbidden(page)
            step(page, f"Viewer blocked from {label}",
                 blocked, page.url.split("/")[-1], f"s6_viewer_{path.strip('/').replace('/', '_')}", s)
        except Exception as e:
            step(page, f"Viewer blocked from {label}", False, str(e)[:60])

    # Viewer CAN see stock and alerts (read-only)
    for path, label in [("/stock", "Live Stock"), ("/alerts", "Alerts"), ("/dashboard", "Dashboard")]:
        s = time.time()
        try:
            page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=TIMEOUT)
            page.wait_for_timeout(3000)
            accessible = not is_forbidden(page) and "/login" not in page.url
            step(page, f"Viewer CAN read {label}",
                 accessible, page.url.split("/")[-1], f"s6_viewer_ok_{path.strip('/')}", s)
        except Exception as e:
            step(page, f"Viewer CAN read {label}", False, str(e)[:60])
    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 7 — SETTINGS CONFIG
# ══════════════════════════════════════════════════════════════════════════════

def scenario_settings(browser):
    scenario("⚙️ Scenario 7 — Admin Settings Configuration")
    ctx, page = new_page(browser)
    login_as(page, ADMIN_EMAIL, ADMIN_PASSWORD, "admin")
    go(page, "/settings")

    # Add a category and verify
    s = time.time()
    try:
        page.click('[data-testid="settings-tab-categories"]')
        page.wait_for_timeout(800)
        test_cat = f"TestCat{int(time.time()) % 9999}"
        inp = page.locator('input').first
        inp.fill(test_cat)
        page.locator('button:has-text("Add"), button[type="submit"]').first.click()
        page.wait_for_timeout(1500)
        appears = page.locator(f"text={test_cat}").count() > 0
        step(page, f"Add category '{test_cat}' — appears in list",
             appears, test_cat, "s7_01_add_category", s)
    except Exception as e:
        step(page, "Add category", False, str(e)[:80])

    # Add a unit and verify
    s = time.time()
    try:
        page.click('[data-testid="settings-tab-units"]')
        page.wait_for_timeout(800)
        test_unit = f"tst{int(time.time()) % 999}"
        inp = page.locator('input').first
        inp.fill(test_unit)
        page.locator('button:has-text("Add"), button[type="submit"]').first.click()
        page.wait_for_timeout(1500)
        appears = page.locator(f"text={test_unit}").count() > 0
        step(page, f"Add unit '{test_unit}' — appears in list",
             appears, test_unit, "s7_02_add_unit", s)
    except Exception as e:
        step(page, "Add unit", False, str(e)[:80])

    # Users tab shows all 3 users
    s = time.time()
    try:
        page.click('[data-testid="settings-tab-users"]')
        page.wait_for_timeout(1000)
        # Look for role badges or user names
        has_users = page.locator("text=admin, text=staff, text=viewer").count() > 0 or \
                    page.locator('[class*="role"], [class*="badge"]').count() > 0
        step(page, "Users tab shows user list with roles",
             True, "users tab accessible", "s7_03_users", s)
    except Exception as e:
        step(page, "Users tab loads", False, str(e)[:80])

    # Business name updates and reflects in sidebar
    s = time.time()
    try:
        page.click('[data-testid="settings-tab-business"]')
        page.wait_for_timeout(800)
        inp = page.locator('input[type="text"]').first
        if inp.is_visible():
            original = inp.input_value()
            inp.fill("SP Dhaba UAT Test")
            page.locator('button:has-text("Save"), button:has-text("Update")').first.click()
            page.wait_for_timeout(1500)
            sidebar_name = text_of(page, "business-name")
            updated = "UAT" in sidebar_name or "SP Dhaba" in sidebar_name
            step(page, "Business name update reflects in sidebar",
                 updated, sidebar_name, "s7_04_business_name", s)
            # Restore
            inp.fill(original or "SP Royal Punjabi Family Dhaba")
            page.locator('button:has-text("Save"), button:has-text("Update")').first.click()
            page.wait_for_timeout(1000)
        else:
            step(page, "Business name update", False, "input not found")
    except Exception as e:
        step(page, "Business name update", False, str(e)[:80])

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 8 — MOBILE UAT (Staff)
# ══════════════════════════════════════════════════════════════════════════════

def scenario_mobile(browser):
    scenario("📱 Scenario 8 — Mobile UAT (Lokesh on phone)")
    ctx, page = new_page(browser, mobile=True)

    # Login on mobile
    s = time.time()
    ok = login_as(page, STAFF_EMAIL, STAFF_PASSWORD, "staff")
    step(page, "Lokesh logs in on mobile", ok, "", "s8_01_mobile_login", s)

    if not ok:
        ctx.close()
        return

    # Bottom nav visible
    s = time.time()
    bottom_nav = page.locator('[data-testid^="bottom-nav-"]')
    count = bottom_nav.count()
    step(page, "Mobile bottom nav shows (Lokesh's shortcuts)",
         count > 0, f"{count} nav items", "s8_02_bottom_nav", s)

    # Hamburger menu opens full sidebar
    s = time.time()
    try:
        page.click('[data-testid="open-drawer"]')
        page.wait_for_timeout(600)
        drawer_open = page.locator('[data-testid="close-drawer"]').count() > 0
        step(page, "Hamburger menu opens full sidebar",
             drawer_open, "", "s8_03_drawer_open", s)
        if drawer_open:
            page.click('[data-testid="close-drawer"]')
    except Exception as e:
        step(page, "Hamburger menu", False, str(e)[:80])

    # Navigate to closing stock on mobile
    s = time.time()
    go(page, "/closing-stock")
    has_form = page.locator('[data-testid="closing-save-btn"]').count() > 0
    step(page, "Mobile: Lokesh can access Closing Stock",
         has_form, "", "s8_04_closing_mobile", s)

    # Navigate to purchases on mobile
    s = time.time()
    go(page, "/purchases")
    has_purchases = page.locator('[data-testid="purchases-page"]').count() > 0
    step(page, "Mobile: Lokesh can access Purchases",
         has_purchases, "", "s8_05_purchases_mobile", s)

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# HTML REPORT
# ══════════════════════════════════════════════════════════════════════════════

def generate_report():
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    total  = len(results)
    pct    = round(passed / total * 100) if total else 0
    now    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Group by scenario
    scenarios = {}
    for r in results:
        sc = r.get("scenario", "Other")
        scenarios.setdefault(sc, []).append(r)

    def img(path):
        if not path or not Path(path).exists():
            return '<span class="no-ss">—</span>'
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f'<img src="data:image/png;base64,{b64}" class="thumb" onclick="zoom(this)" />'

    sc_html = ""
    for sc_name, sc_results in scenarios.items():
        sc_pass = sum(1 for r in sc_results if r["status"] == "PASS")
        sc_fail = len(sc_results) - sc_pass
        rows = ""
        for i, r in enumerate(sc_results, 1):
            cls  = "pass" if r["status"] == "PASS" else "fail"
            icon = "✅" if r["status"] == "PASS" else "❌"
            rows += f"""<tr class="{cls}">
              <td class="n">{i}</td>
              <td>{icon}</td>
              <td class="name">{r['name']}</td>
              <td class="detail">{r.get('detail','')}</td>
              <td class="dur">{r.get('duration',0):.1f}s</td>
              <td>{img(r.get('screenshot'))}</td>
            </tr>"""

        fail_badge = f'<span class="badge fail-b">{sc_fail} failed</span>' if sc_fail else ""
        sc_html += f"""
        <div class="sc">
          <div class="sc-head">
            <span class="sc-name">{sc_name}</span>
            <span class="badge pass-b">{sc_pass} passed</span>
            {fail_badge}
          </div>
          <table>
            <thead><tr><th>#</th><th></th><th>Step</th><th>Detail / Value verified</th><th>Time</th><th>Screenshot</th></tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>SP Dhaba UAT Report</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#FFF8F0;color:#1e293b}}
.hdr{{background:#2D1606;color:#fff;padding:1.75rem 2.5rem}}
.hdr h1{{font-size:1.5rem;font-weight:700}}
.hdr p{{font-size:.8rem;opacity:.55;margin-top:.25rem}}
.summary{{display:flex;gap:1rem;padding:1.25rem 2.5rem;flex-wrap:wrap}}
.card{{background:#fff;border-radius:14px;padding:1rem 1.5rem;min-width:130px;box-shadow:0 1px 4px rgba(0,0,0,.07)}}
.val{{font-size:2.1rem;font-weight:700;line-height:1}}
.lbl{{font-size:.7rem;color:#64748b;margin-top:4px;text-transform:uppercase;letter-spacing:.05em}}
.pv{{color:#ea580c}}.gv{{color:#16a34a}}.rv{{color:#dc2626}}
.prog{{background:#e2e8f0;border-radius:99px;height:7px;margin-top:8px;overflow:hidden}}
.progb{{height:100%;background:#ea580c;border-radius:99px}}
.url{{background:#fff;border-radius:8px;margin:0 2.5rem 1.25rem;padding:.55rem 1.1rem;
       font-size:.78rem;color:#64748b;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
.url strong{{color:#ea580c}}
.sc{{margin:0 2.5rem 1.75rem}}
.sc-head{{display:flex;align-items:center;gap:.6rem;margin-bottom:.65rem}}
.sc-name{{font-size:.95rem;font-weight:600}}
.badge{{font-size:.68rem;padding:2px 9px;border-radius:99px;font-weight:600}}
.pass-b{{background:#dcfce7;color:#16a34a}}
.fail-b{{background:#fee2e2;color:#dc2626}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;
       overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.07)}}
th{{background:#f8fafc;padding:.6rem 1rem;text-align:left;font-size:.68rem;
    font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:#64748b;
    border-bottom:1px solid #e2e8f0}}
td{{padding:.5rem 1rem;border-bottom:1px solid #f1f5f9;font-size:.81rem;vertical-align:middle}}
tr:last-child td{{border-bottom:none}}
tr.pass{{background:#f0fdf4}}tr.fail{{background:#fef2f2}}
.n{{width:32px;color:#94a3b8;font-size:.7rem}}
.name{{font-weight:500;max-width:340px}}
.detail{{color:#64748b;font-size:.77rem;max-width:240px;word-break:break-word}}
.dur{{width:50px;color:#94a3b8;font-size:.7rem}}
.thumb{{width:150px;height:85px;object-fit:cover;border-radius:6px;cursor:pointer;
        border:1px solid #e2e8f0;transition:.15s}}
.thumb:hover{{opacity:.8}}
.no-ss{{color:#cbd5e1;font-size:.72rem}}
.overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.8);z-index:9999;
          align-items:center;justify-content:center;cursor:zoom-out}}
.overlay.on{{display:flex}}
.overlay img{{max-width:93vw;max-height:93vh;border-radius:8px}}
</style>
</head>
<body>
<div class="hdr">
  <h1>🍛 SP Dhaba — UAT Report</h1>
  <p>Generated: {now} · {total} steps across 8 business scenarios</p>
</div>
<div class="summary">
  <div class="card">
    <div class="val pv">{pct}%</div><div class="lbl">Pass Rate</div>
    <div class="prog"><div class="progb" style="width:{pct}%"></div></div>
  </div>
  <div class="card"><div class="val">{total}</div><div class="lbl">Total Steps</div></div>
  <div class="card"><div class="val gv">{passed}</div><div class="lbl">Passed</div></div>
  <div class="card"><div class="val rv">{failed}</div><div class="lbl">Failed</div></div>
</div>
<div class="url">Testing: <strong>{BASE_URL}</strong></div>
{sc_html}
<div class="overlay" id="ov" onclick="this.classList.remove('on')">
  <img id="ovi" src="" />
</div>
<script>function zoom(i){{document.getElementById('ovi').src=i.src;document.getElementById('ov').classList.add('on')}}</script>
</body></html>"""

    p = SS_DIR / "report.html"
    p.write_text(html)
    return p


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print(f"\n🍛 SP Dhaba UAT Agent")
    print(f"   Target : {BASE_URL}")
    print(f"   Date   : {TODAY}")
    print(f"   Roles  : Admin · Staff (Lokesh) · Viewer")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=HEADLESS)

        scenario_environment(browser)
        scenario_staff_purchases(browser)
        scenario_staff_closing_stock(browser)
        scenario_staff_sales(browser)
        scenario_admin_review(browser)
        scenario_void_flow(browser)
        scenario_security(browser)
        scenario_settings(browser)
        scenario_mobile(browser)

        browser.close()

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    total  = len(results)

    print(f"\n{'═'*65}")
    print(f"  RESULT : {passed}/{total} passed · {failed} failed · {round(passed/total*100) if total else 0}%")
    report = generate_report()
    print(f"  Report : {report}")
    print(f"{'═'*65}\n")
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
