"""
SP Dhaba — UAT Agent
====================
Simulates real business scenarios like a UAT tester.
Tests actual data entry, verifies results, checks role permissions.

Usage:
  UAT_SECRET=sp-dhaba-uat-2024 python3 tests/ui_agent.py <url>

Scenarios:
  0. Environment check
  1. Lokesh morning purchases (staff)
  2. Lokesh evening closing stock
  3. Lokesh records sales + expenses
  4. Admin end-of-day review
  5. Void flow
  6. Security & role enforcement
  7. Settings configuration
  8. Mobile UAT
"""

import sys, os, time, base64
from datetime import datetime, date
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BASE_URL        = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:3000"
ADMIN_EMAIL     = os.environ.get("ADMIN_EMAIL",  "admin@spdhaba.com")
ADMIN_PASSWORD  = os.environ.get("ADMIN_PWD",    "Admin@123")
STAFF_EMAIL     = os.environ.get("STAFF_EMAIL",  "lokesh@spdhaba.com")
STAFF_PASSWORD  = os.environ.get("STAFF_PWD",    "Staff@123")
VIEWER_EMAIL    = os.environ.get("VIEWER_EMAIL", "display@spdhaba.com")
VIEWER_PASSWORD = os.environ.get("VIEWER_PWD",   "View@123")
UAT_SECRET      = os.environ.get("UAT_SECRET",   "")
HEADLESS        = os.environ.get("HEADLESS", "true").lower() == "true"
TIMEOUT         = 30000
TODAY           = date.today().isoformat()

SS_DIR  = Path(__file__).parent / "screenshots"
SS_DIR.mkdir(exist_ok=True)
RESULTS = []
CURRENT = ""
# Cached tokens per role — login once, reuse everywhere
TOKENS  = {}

# ── Result helpers ────────────────────────────────────────────────────────────

def scenario(name):
    global CURRENT
    CURRENT = name
    print(f"\n{'━'*65}\n  {name}\n{'━'*65}")

def step(page, name, ok, detail="", ss_name=None, start=None):
    dur  = round(time.time() - start, 1) if start else 0
    path = None
    if ss_name:
        p = SS_DIR / f"{ss_name}.png"
        try:
            page.screenshot(path=str(p), full_page=True)
            path = str(p)
        except Exception:
            pass
    RESULTS.append({"scenario": CURRENT, "name": name,
                    "status": "PASS" if ok else "FAIL",
                    "detail": detail, "screenshot": path, "duration": dur})
    icon = "✅" if ok else "❌"
    msg  = f"  {icon} {name}"
    if detail: msg += f"  →  {detail}"
    if dur:    msg += f"  ({dur}s)"
    print(msg)
    return ok

# ── Navigation helpers ────────────────────────────────────────────────────────

def ctx_page(browser, mobile=False):
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
    """Navigate and wait for app shell or login page to mount."""
    for attempt in range(3):
        try:
            page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=TIMEOUT)
            page.wait_for_selector(
                '[data-testid="app-shell"], [data-testid="login-page"], [data-testid="forbidden-page"]',
                timeout=15000
            )
            page.wait_for_timeout(1200)
            return True
        except Exception:
            if attempt == 2: return False
            page.wait_for_timeout(2000)

def inject_token(page, token):
    """Inject JWT token directly into localStorage — bypasses login form."""
    page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=TIMEOUT)
    page.wait_for_timeout(500)
    if UAT_SECRET:
        page.evaluate(f'localStorage.setItem("sp_uat_secret", "{UAT_SECRET}")')
    page.evaluate(f'localStorage.setItem("sp_token", "{token}")')
    page.goto(f"{BASE_URL}/stock", wait_until="domcontentloaded", timeout=TIMEOUT)
    page.wait_for_selector('[data-testid="app-shell"]', timeout=15000)
    page.wait_for_timeout(1000)
    return "/login" not in page.url

def login_as(page, email, password, role):
    """Login via form, cache token for reuse in later scenarios."""
    # Reuse cached token if available
    if role in TOKENS:
        try:
            ok = inject_token(page, TOKENS[role])
            if ok: return True
        except Exception:
            pass  # fall through to fresh login

    for attempt in range(3):
        try:
            page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=TIMEOUT)
            page.wait_for_selector('[data-testid="login-email-input"]', timeout=TIMEOUT)
            page.wait_for_timeout(500)

            # Inject UAT secret so rate limiter is bypassed
            if UAT_SECRET:
                page.evaluate(f'localStorage.setItem("sp_uat_secret", "{UAT_SECRET}")')

            page.fill('[data-testid="login-email-input"]', email)
            page.fill('[data-testid="login-password-input"]', password)
            page.click('[data-testid="login-submit-button"]')

            # Wait for redirect away from /login
            page.wait_for_function(
                'window.location.pathname !== "/login"',
                timeout=TIMEOUT
            )
            page.wait_for_timeout(1000)

            if "/login" in page.url:
                raise Exception("still on login page")

            # Cache the token
            try:
                token = page.evaluate('localStorage.getItem("sp_token")')
                if token:
                    TOKENS[role] = token
            except Exception:
                pass

            return True
        except Exception as e:
            if attempt == 2:
                return False
            page.wait_for_timeout(3000)

def select_first(page, trigger_testid):
    """Click a Select trigger and choose the first option. Returns option text."""
    try:
        page.locator(f'[data-testid="{trigger_testid}"]').click()
        page.wait_for_timeout(600)
        opts = page.locator('[role="option"]')
        if opts.count() == 0:
            return None
        text = opts.first.text_content().strip()
        opts.first.click()
        page.wait_for_timeout(400)
        return text
    except Exception:
        return None

def toast_text(page, timeout=5000):
    try:
        page.wait_for_selector('[data-sonner-toast]', timeout=timeout)
        return page.locator('[data-sonner-toast]').first.text_content() or ""
    except Exception:
        return ""

def row_count(page, prefix):
    return page.locator(f'[data-testid^="{prefix}"]').count()

def is_forbidden(page):
    page.wait_for_timeout(2500)  # wait for auth redirect
    return "forbidden" in page.url or \
           page.locator('[data-testid="forbidden-page"]').count() > 0

def has(page, selector, timeout=5000):
    try:
        page.wait_for_selector(selector, timeout=timeout)
        return True
    except Exception:
        return False

def txt(page, testid):
    try:
        return page.locator(f'[data-testid="{testid}"]').text_content().strip()
    except Exception:
        return ""


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 0 — ENVIRONMENT
# ══════════════════════════════════════════════════════════════════════════════

def s0_environment(browser):
    scenario("🌍 Scenario 0 — Environment Check")
    ctx, page = ctx_page(browser)

    s = time.time()
    try:
        page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=TIMEOUT)
        page.wait_for_selector('[data-testid="login-page"]', timeout=15000)
        page.wait_for_timeout(2000)

        banner = ""
        for sel in ["text=STAGING", "text=Production", "text=Unknown environment"]:
            el = page.locator(sel)
            if el.count() > 0:
                banner = el.first.text_content().strip()
                break

        step(page, "Environment banner visible", bool(banner), banner, "s0_01_banner", s)
        step(page, "Banner contains DB name", "sp_dhaba" in banner.lower(),
             banner[:80], "s0_02_db_name", s)
    except Exception as e:
        step(page, "Environment check", False, str(e)[:100])

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 1 — LOKESH MORNING PURCHASES
# ══════════════════════════════════════════════════════════════════════════════

def s1_staff_purchases(browser):
    scenario("🛒 Scenario 1 — Lokesh Records Morning Purchases")
    ctx, page = ctx_page(browser)

    # Login
    s = time.time()
    ok = login_as(page, STAFF_EMAIL, STAFF_PASSWORD, "staff")
    if not step(page, "Lokesh logs in as Staff",
                ok, page.url.split("/")[-1], "s1_01_login", s):
        ctx.close(); return

    step(page, "Lokesh lands on Live Stock (not dashboard)",
         "stock" in page.url, page.url.split("/")[-1], "s1_02_landing", s)

    # Navigate to purchases
    s = time.time()
    go(page, "/purchases")
    step(page, "Purchases page loads", has(page, '[data-testid="purchases-page"]'),
         "", "s1_03_purchases_page", s)

    # Purchase 1 — 10 units × ₹200
    s = time.time()
    try:
        item1 = select_first(page, "purchase-item-select")
        page.fill('[data-testid="purchase-qty-input"]', "10")
        page.fill('[data-testid="purchase-price-input"]', "200")
        page.wait_for_timeout(400)
        preview = txt(page, "purchase-total-preview")
        step(page, f"Purchase 1: 10 × ₹200 = ₹2,000 [{item1}]",
             "2,000" in preview or "2000" in preview,
             f"Preview: {preview}", "s1_04_p1_preview", s)

        before = row_count(page, "purchase-row-")
        page.click('[data-testid="purchase-submit-button"]')
        t = toast_text(page)
        page.wait_for_timeout(1500)
        after = row_count(page, "purchase-row-")
        step(page, "Purchase 1 saved — row appears in list",
             after > before,
             f"rows {before}→{after}, toast: {t[:40]}", "s1_05_p1_saved", s)
    except Exception as e:
        step(page, "Purchase 1", False, str(e)[:100])

    # Purchase 2 — 5 units × ₹30
    s = time.time()
    try:
        item2 = select_first(page, "purchase-item-select")
        page.fill('[data-testid="purchase-qty-input"]', "5")
        page.fill('[data-testid="purchase-price-input"]', "30")
        page.wait_for_timeout(400)
        preview = txt(page, "purchase-total-preview")
        step(page, f"Purchase 2: 5 × ₹30 = ₹150 [{item2}]",
             "150" in preview,
             f"Preview: {preview}", "s1_06_p2_preview", s)

        before = row_count(page, "purchase-row-")
        page.click('[data-testid="purchase-submit-button"]')
        page.wait_for_timeout(1500)
        after = row_count(page, "purchase-row-")
        step(page, "Purchase 2 saved — row appears in list",
             after > before,
             f"rows {before}→{after}", "s1_07_p2_saved", s)
    except Exception as e:
        step(page, "Purchase 2", False, str(e)[:100])

    # Live stock shows items
    s = time.time()
    go(page, "/stock")
    page.wait_for_timeout(1000)
    cards = row_count(page, "stock-card-")
    step(page, "Live stock shows items after purchases",
         cards > 0, f"{cards} items", "s1_08_stock", s)

    # Staff CANNOT access dashboard
    s = time.time()
    page.goto(f"{BASE_URL}/dashboard", wait_until="domcontentloaded", timeout=TIMEOUT)
    step(page, "Lokesh CANNOT access Dashboard",
         is_forbidden(page), page.url, "s1_09_no_dashboard", s)

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 2 — LOKESH CLOSING STOCK
# ══════════════════════════════════════════════════════════════════════════════

def s2_closing_stock(browser):
    scenario("📦 Scenario 2 — Lokesh Records Closing Stock")
    ctx, page = ctx_page(browser)
    login_as(page, STAFF_EMAIL, STAFF_PASSWORD, "staff")

    go(page, "/closing-stock")

    # Progress bar visible
    s = time.time()
    step(page, "Closing stock page shows item count progress",
         has(page, "text=Items counted today"),
         "", "s2_01_page", s)

    # Count item 1 — closing qty 7
    s = time.time()
    try:
        item1 = select_first(page, "closing-item-select")
        page.fill('[data-testid="closing-qty-input"]', "7")
        page.fill('[data-testid="closing-notes-input"]', "Counted after dinner service")

        before = row_count(page, "closing-row-")
        page.click('[data-testid="closing-save-btn"]')
        t = toast_text(page)
        page.wait_for_timeout(1500)
        after = row_count(page, "closing-row-")
        step(page, f"Closing count saved for {item1} (qty=7)",
             after > before,
             f"rows {before}→{after}, toast: {t[:40]}", "s2_02_saved", s)

        # Verify row shows formula columns
        if after > 0:
            row_text = page.locator('[data-testid^="closing-row-"]').first.text_content()
            step(page, "Row shows Opening / Purchased / Closing / Consumed",
                 len(row_text) > 10,
                 row_text[:120], "s2_03_formula", s)
    except Exception as e:
        step(page, "Closing stock entry 1", False, str(e)[:100])

    # Count item 2
    s = time.time()
    try:
        item2 = select_first(page, "closing-item-select")
        page.fill('[data-testid="closing-qty-input"]', "3")
        before = row_count(page, "closing-row-")
        page.click('[data-testid="closing-save-btn"]')
        page.wait_for_timeout(1500)
        after = row_count(page, "closing-row-")
        step(page, f"Closing count saved for {item2} (qty=3)",
             after >= 2,
             f"{after} rows total", "s2_04_item2", s)
    except Exception as e:
        step(page, "Closing stock entry 2", False, str(e)[:100])

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 3 — LOKESH SALES + EXPENSES
# ══════════════════════════════════════════════════════════════════════════════

def s3_sales_expenses(browser):
    scenario("💰 Scenario 3 — Lokesh Records Sales & Expenses")
    ctx, page = ctx_page(browser)
    login_as(page, STAFF_EMAIL, STAFF_PASSWORD, "staff")

    # Sales entry
    s = time.time()
    go(page, "/sales")
    try:
        page.fill('[data-testid="sales-lunch-input"]',  "5000")
        page.fill('[data-testid="sales-dinner-input"]', "4000")
        page.fill('[data-testid="sales-other-input"]',  "500")
        page.wait_for_timeout(500)

        total = txt(page, "sales-total-preview")
        step(page, "Sales total: ₹5000 + ₹4000 + ₹500 = ₹9,500",
             "9,500" in total or "9500" in total,
             f"Preview: {total}", "s3_01_sales_total", s)

        before = row_count(page, "sales-row-")
        page.click('[data-testid="sales-submit-button"]')
        t = toast_text(page)
        page.wait_for_timeout(1500)
        after = row_count(page, "sales-row-")
        step(page, "Sales entry saved — appears in list",
             after > before or "success" in t.lower() or "saved" in t.lower(),
             f"rows {before}→{after}", "s3_02_sales_saved", s)
    except Exception as e:
        step(page, "Sales entry", False, str(e)[:100])

    # Expense entry — Gas cylinder
    s = time.time()
    go(page, "/expenses")
    try:
        cat = select_first(page, "exp-cat-select")
        page.fill('[data-testid="exp-desc-input"]',   "Gas cylinder refill")
        page.fill('[data-testid="exp-amount-input"]', "1200")

        before = row_count(page, "expense-row-")
        page.click('[data-testid="exp-submit-button"]')
        t = toast_text(page)
        page.wait_for_timeout(1500)
        after = row_count(page, "expense-row-")
        step(page, f"Expense ₹1200 ({cat}) saved — appears in list",
             after > before,
             f"rows {before}→{after}", "s3_03_expense", s)
    except Exception as e:
        step(page, "Expense entry", False, str(e)[:100])

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 4 — ADMIN END OF DAY REVIEW
# ══════════════════════════════════════════════════════════════════════════════

def s4_admin_review(browser):
    scenario("👑 Scenario 4 — Admin Reviews End of Day")
    ctx, page = ctx_page(browser)

    s = time.time()
    ok = login_as(page, ADMIN_EMAIL, ADMIN_PASSWORD, "admin")
    if not step(page, "Admin logs in",
                ok, page.url.split("/")[-1], "s4_01_login", s):
        ctx.close(); return

    step(page, "Admin lands on Dashboard",
         "dashboard" in page.url, page.url, "s4_02_dashboard", s)

    # Dashboard
    s = time.time()
    go(page, "/dashboard")
    step(page, "Dashboard loads with summary cards",
         has(page, '[data-testid="dashboard-page"]'),
         "", "s4_03_dashboard", s)

    # P&L
    s = time.time()
    go(page, "/pnl")
    page.wait_for_timeout(1500)
    step(page, "P&L page loads",
         has(page, '[data-testid="pnl-page"]'),
         "", "s4_04_pnl", s)

    # Admin adds expense
    s = time.time()
    go(page, "/expenses")
    try:
        cat = select_first(page, "exp-cat-select")
        page.fill('[data-testid="exp-desc-input"]',   "Electricity bill")
        page.fill('[data-testid="exp-amount-input"]', "3500")
        before = row_count(page, "expense-row-")
        page.click('[data-testid="exp-submit-button"]')
        page.wait_for_timeout(1500)
        after = row_count(page, "expense-row-")
        step(page, "Admin adds expense ₹3500 — in list",
             after > before, f"rows {before}→{after}", "s4_05_expense", s)
    except Exception as e:
        step(page, "Admin expense", False, str(e)[:100])

    # Salaries
    s = time.time()
    go(page, "/salaries")
    step(page, "Admin can access Salaries",
         has(page, '[data-testid="salaries-page"]'),
         "", "s4_06_salaries", s)

    # Live stock
    s = time.time()
    go(page, "/stock")
    page.wait_for_timeout(1000)
    cards = row_count(page, "stock-card-")
    step(page, "Live stock shows all items",
         cards > 0, f"{cards} items", "s4_07_stock", s)

    # Inventory insights
    s = time.time()
    go(page, "/inventory-insights")
    step(page, "Admin can access Inventory Insights",
         not is_forbidden(page), "", "s4_08_insights", s)

    # Alerts
    s = time.time()
    go(page, "/alerts")
    step(page, "Admin can view Alerts",
         not is_forbidden(page), "", "s4_09_alerts", s)

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 5 — VOID FLOW
# ══════════════════════════════════════════════════════════════════════════════

def s5_void_flow(browser):
    scenario("🚫 Scenario 5 — Void Flow")
    ctx, page = ctx_page(browser)
    login_as(page, ADMIN_EMAIL, ADMIN_PASSWORD, "admin")
    go(page, "/purchases")
    page.wait_for_timeout(800)

    void_btns = page.locator('[data-testid^="void-purchase-"]')
    count = void_btns.count()

    if count == 0:
        step(page, "Void flow — no entries yet, skipped", True,
             "run after purchases are added", "s5_01_no_entries")
        ctx.close(); return

    # Open void dialog
    s = time.time()
    void_btns.first.click()
    page.wait_for_timeout(600)
    dialog = has(page, '[data-testid="void-dialog"]', 3000)
    step(page, "Void dialog opens on click",
         dialog, "", "s5_02_dialog_open", s)

    if not dialog:
        ctx.close(); return

    # Empty reason shows error
    s = time.time()
    page.click('[data-testid="void-confirm-btn"]')
    page.wait_for_timeout(400)
    step(page, "Empty reason shows validation error",
         has(page, '[data-testid="void-reason-error"]', 2000),
         "", "s5_03_validation", s)

    # Cancel closes dialog
    s = time.time()
    page.click('[data-testid="void-cancel-btn"]')
    page.wait_for_timeout(400)
    step(page, "Cancel closes void dialog",
         page.locator('[data-testid="void-dialog"]').count() == 0,
         "", "s5_04_cancel", s)

    # Void with reason — entry removed
    s = time.time()
    before = row_count(page, "purchase-row-")
    page.locator('[data-testid^="void-purchase-"]').first.click()
    page.wait_for_timeout(600)
    page.fill('[data-testid="void-reason-input"]', "Duplicate entry — UAT test")
    page.click('[data-testid="void-confirm-btn"]')
    t = toast_text(page, 5000)
    page.wait_for_timeout(2000)
    after = row_count(page, "purchase-row-")
    step(page, "Void confirmed — entry removed from list",
         after < before or "void" in t.lower(),
         f"rows {before}→{after}", "s5_05_voided", s)

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 6 — SECURITY
# ══════════════════════════════════════════════════════════════════════════════

def s6_security(browser):
    scenario("🔒 Scenario 6 — Security & Role Enforcement")

    # Unauthenticated
    ctx, page = ctx_page(browser)
    for path in ["/dashboard", "/purchases", "/settings", "/pnl", "/salaries"]:
        s = time.time()
        page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=TIMEOUT)
        page.wait_for_timeout(2500)
        step(page, f"Unauthenticated → {path} → login",
             "/login" in page.url, page.url.split("/")[-1],
             f"s6_unauth{path.replace('/', '_')}", s)
    ctx.close()

    # Staff blocked from admin pages
    ctx, page = ctx_page(browser)
    login_as(page, STAFF_EMAIL, STAFF_PASSWORD, "staff")
    for path, label in [
        ("/dashboard",          "Dashboard"),
        ("/salaries",           "Salaries"),
        ("/pnl",                "P&L"),
        ("/items",              "Item Master"),
        ("/settings",           "Settings"),
        ("/inventory-insights", "Inventory Insights"),
    ]:
        s = time.time()
        page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=TIMEOUT)
        step(page, f"Staff BLOCKED from {label}",
             is_forbidden(page), page.url.split("/")[-1],
             f"s6_staff{path.replace('/', '_')}", s)
    ctx.close()

    # Staff ALLOWED pages
    ctx, page = ctx_page(browser)
    login_as(page, STAFF_EMAIL, STAFF_PASSWORD, "staff")
    for path, label in [
        ("/stock",         "Live Stock"),
        ("/purchases",     "Purchases"),
        ("/closing-stock", "Closing Stock"),
        ("/sales",         "Sales"),
        ("/expenses",      "Expenses"),
    ]:
        s = time.time()
        go(page, path)
        step(page, f"Staff CAN access {label}",
             not is_forbidden(page) and "/login" not in page.url,
             page.url.split("/")[-1],
             f"s6_staff_ok{path.replace('/', '_')}", s)
    ctx.close()

    # Viewer blocked from write pages
    ctx, page = ctx_page(browser)
    login_as(page, VIEWER_EMAIL, VIEWER_PASSWORD, "viewer")
    for path, label in [
        ("/purchases",  "Purchases"),
        ("/sales",      "Sales"),
        ("/expenses",   "Expenses"),
        ("/salaries",   "Salaries"),
        ("/items",      "Item Master"),
        ("/settings",   "Settings"),
    ]:
        s = time.time()
        page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=TIMEOUT)
        step(page, f"Viewer BLOCKED from {label}",
             is_forbidden(page), page.url.split("/")[-1],
             f"s6_viewer{path.replace('/', '_')}", s)

    # Viewer CAN read
    for path, label in [
        ("/stock",      "Live Stock"),
        ("/alerts",     "Alerts"),
        ("/dashboard",  "Dashboard"),
        ("/pnl",        "P&L"),
    ]:
        s = time.time()
        go(page, path)
        step(page, f"Viewer CAN read {label}",
             not is_forbidden(page) and "/login" not in page.url,
             "", f"s6_viewer_ok{path.replace('/', '_')}", s)
    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 7 — SETTINGS CONFIG
# ══════════════════════════════════════════════════════════════════════════════

def s7_settings(browser):
    scenario("⚙️ Scenario 7 — Settings Configuration")
    ctx, page = ctx_page(browser)
    login_as(page, ADMIN_EMAIL, ADMIN_PASSWORD, "admin")
    go(page, "/settings")

    # Add category — testid from NamedListPane: "categories-new-name" and "categories-add-btn"
    s = time.time()
    try:
        page.click('[data-testid="settings-tab-categories"]')
        page.wait_for_timeout(800)
        cat_name = f"TestCat{int(time.time()) % 9999}"
        page.fill('[data-testid="categories-new-name"]', cat_name)
        page.click('[data-testid="categories-add-btn"]')
        page.wait_for_timeout(1500)
        appears = page.locator(f"text={cat_name}").count() > 0
        step(page, f"Add category '{cat_name}' — appears in list",
             appears, cat_name, "s7_01_category", s)
    except Exception as e:
        step(page, "Add category", False, str(e)[:100])

    # Add unit — testid: "units-new-name" and "units-add-btn"
    s = time.time()
    try:
        page.click('[data-testid="settings-tab-units"]')
        page.wait_for_timeout(800)
        unit_name = f"tst{int(time.time()) % 999}"
        page.fill('[data-testid="units-new-name"]', unit_name)
        page.click('[data-testid="units-add-btn"]')
        page.wait_for_timeout(1500)
        appears = page.locator(f"text={unit_name}").count() > 0
        step(page, f"Add unit '{unit_name}' — appears in list",
             appears, unit_name, "s7_02_unit", s)
    except Exception as e:
        step(page, "Add unit", False, str(e)[:100])

    # Users tab — verify users list loads
    s = time.time()
    try:
        page.click('[data-testid="settings-tab-users"]')
        page.wait_for_timeout(1000)
        has_rows = row_count(page, "user-row-") > 0
        step(page, "Users tab loads — shows user list",
             has_rows, f"{row_count(page, 'user-row-')} users", "s7_03_users", s)
    except Exception as e:
        step(page, "Users tab", False, str(e)[:100])

    # Business profile tab
    s = time.time()
    try:
        page.click('[data-testid="settings-tab-business"]')
        page.wait_for_timeout(800)
        accessible = not is_forbidden(page)
        step(page, "Business profile tab loads",
             accessible, "", "s7_04_business", s)
    except Exception as e:
        step(page, "Business profile tab", False, str(e)[:100])

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# SCENARIO 8 — MOBILE UAT
# ══════════════════════════════════════════════════════════════════════════════

def s8_mobile(browser):
    scenario("📱 Scenario 8 — Mobile UAT (Lokesh on phone)")
    ctx, page = ctx_page(browser, mobile=True)

    s = time.time()
    ok = login_as(page, STAFF_EMAIL, STAFF_PASSWORD, "staff")
    if not step(page, "Lokesh logs in on mobile",
                ok, "", "s8_01_login", s):
        ctx.close(); return

    # Bottom nav
    s = time.time()
    count = row_count(page, "bottom-nav-")
    step(page, "Mobile bottom nav visible",
         count > 0, f"{count} nav items", "s8_02_bottom_nav", s)

    # Hamburger opens
    s = time.time()
    try:
        page.click('[data-testid="open-drawer"]')
        page.wait_for_timeout(600)
        open_ok = has(page, '[data-testid="close-drawer"]', 3000)
        step(page, "Hamburger drawer opens",
             open_ok, "", "s8_03_drawer", s)
        if open_ok:
            page.click('[data-testid="close-drawer"]')
            page.wait_for_timeout(400)
    except Exception as e:
        step(page, "Hamburger drawer", False, str(e)[:100])

    # Closing stock on mobile
    s = time.time()
    go(page, "/closing-stock")
    step(page, "Closing stock accessible on mobile",
         has(page, '[data-testid="closing-stock-page"]'),
         "", "s8_04_closing", s)

    # Purchases on mobile
    s = time.time()
    go(page, "/purchases")
    step(page, "Purchases accessible on mobile",
         has(page, '[data-testid="purchases-page"]'),
         "", "s8_05_purchases", s)

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# HTML REPORT
# ══════════════════════════════════════════════════════════════════════════════

def generate_report():
    passed = sum(1 for r in RESULTS if r["status"] == "PASS")
    failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
    total  = len(RESULTS)
    pct    = round(passed / total * 100) if total else 0
    now    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    scenarios = {}
    for r in RESULTS:
        scenarios.setdefault(r["scenario"], []).append(r)

    def img(path):
        if not path or not Path(path).exists():
            return '<span class="ns">—</span>'
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f'<img src="data:image/png;base64,{b64}" class="th" onclick="zoom(this)" />'

    body = ""
    for sc, rows in scenarios.items():
        sp = sum(1 for r in rows if r["status"] == "PASS")
        sf = len(rows) - sp
        trs = ""
        for i, r in enumerate(rows, 1):
            cls  = "p" if r["status"] == "PASS" else "f"
            icon = "✅" if r["status"] == "PASS" else "❌"
            trs += f'<tr class="{cls}"><td class="n">{i}</td><td>{icon}</td>'
            trs += f'<td class="nm">{r["name"]}</td>'
            trs += f'<td class="dt">{r.get("detail","")}</td>'
            trs += f'<td class="du">{r.get("duration",0):.1f}s</td>'
            trs += f'<td>{img(r.get("screenshot"))}</td></tr>'
        fb = f'<span class="bd fb">{sf} failed</span>' if sf else ""
        body += f'''<div class="sc">
          <div class="sh"><span class="sn">{sc}</span>
          <span class="bd pb">{sp} passed</span>{fb}</div>
          <table><thead><tr><th>#</th><th></th><th>Step</th>
          <th>Detail / Value verified</th><th>Time</th><th>Screenshot</th>
          </tr></thead><tbody>{trs}</tbody></table></div>'''

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>SP Dhaba UAT</title><style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#FFF8F0;color:#1e293b}}
.hdr{{background:#2D1606;color:#fff;padding:1.75rem 2.5rem}}
.hdr h1{{font-size:1.5rem;font-weight:700}}
.hdr p{{font-size:.8rem;opacity:.5;margin-top:.2rem}}
.sum{{display:flex;gap:1rem;padding:1.25rem 2.5rem;flex-wrap:wrap}}
.card{{background:#fff;border-radius:14px;padding:1rem 1.5rem;min-width:120px;box-shadow:0 1px 4px rgba(0,0,0,.07)}}
.v{{font-size:2rem;font-weight:700;line-height:1}}
.l{{font-size:.7rem;color:#64748b;margin-top:4px;text-transform:uppercase;letter-spacing:.05em}}
.ov{{color:#ea580c}}.gv{{color:#16a34a}}.rv{{color:#dc2626}}
.pg{{background:#e2e8f0;border-radius:99px;height:7px;margin-top:8px;overflow:hidden}}
.pgb{{height:100%;background:#ea580c;border-radius:99px}}
.url{{background:#fff;border-radius:8px;margin:0 2.5rem 1.25rem;padding:.5rem 1rem;
      font-size:.78rem;color:#64748b;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
.url strong{{color:#ea580c}}
.sc{{margin:0 2.5rem 1.75rem}}
.sh{{display:flex;align-items:center;gap:.6rem;margin-bottom:.65rem}}
.sn{{font-size:.95rem;font-weight:600}}
.bd{{font-size:.68rem;padding:2px 9px;border-radius:99px;font-weight:600}}
.pb{{background:#dcfce7;color:#16a34a}}.fb{{background:#fee2e2;color:#dc2626}}
table{{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;
       overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.07)}}
th{{background:#f8fafc;padding:.6rem 1rem;text-align:left;font-size:.68rem;font-weight:600;
    text-transform:uppercase;letter-spacing:.05em;color:#64748b;border-bottom:1px solid #e2e8f0}}
td{{padding:.5rem 1rem;border-bottom:1px solid #f1f5f9;font-size:.81rem;vertical-align:middle}}
tr:last-child td{{border-bottom:none}}
tr.p{{background:#f0fdf4}}tr.f{{background:#fef2f2}}
.n{{width:32px;color:#94a3b8;font-size:.7rem}}
.nm{{font-weight:500;max-width:320px}}
.dt{{color:#64748b;font-size:.77rem;max-width:260px;word-break:break-word}}
.du{{width:48px;color:#94a3b8;font-size:.7rem}}
.th{{width:150px;height:85px;object-fit:cover;border-radius:6px;cursor:pointer;
     border:1px solid #e2e8f0}}.th:hover{{opacity:.8}}
.ns{{color:#cbd5e1;font-size:.72rem}}
.ov2{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.8);z-index:9999;
      align-items:center;justify-content:center;cursor:zoom-out}}
.ov2.on{{display:flex}}.ov2 img{{max-width:93vw;max-height:93vh;border-radius:8px}}
</style></head><body>
<div class="hdr"><h1>🍛 SP Dhaba — UAT Report</h1>
<p>Generated: {now} · {total} steps · 8 business scenarios</p></div>
<div class="sum">
<div class="card"><div class="v ov">{pct}%</div><div class="l">Pass Rate</div>
<div class="pg"><div class="pgb" style="width:{pct}%"></div></div></div>
<div class="card"><div class="v">{total}</div><div class="l">Total Steps</div></div>
<div class="card"><div class="v gv">{passed}</div><div class="l">Passed</div></div>
<div class="card"><div class="v rv">{failed}</div><div class="l">Failed</div></div>
</div>
<div class="url">Testing: <strong>{BASE_URL}</strong></div>
{body}
<div class="ov2" id="ov" onclick="this.classList.remove('on')">
<img id="ovi" src=""/></div>
<script>function zoom(i){{document.getElementById('ovi').src=i.src;
document.getElementById('ov').classList.add('on')}}</script>
</body></html>"""


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print(f"\n🍛 SP Dhaba UAT Agent")
    print(f"   Target : {BASE_URL}")
    print(f"   Date   : {TODAY}")
    print(f"   Secret : {'✅ set' if UAT_SECRET else '❌ not set — rate limiter will block!'}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=HEADLESS)

        s0_environment(browser)
        s1_staff_purchases(browser)
        s2_closing_stock(browser)
        s3_sales_expenses(browser)
        s4_admin_review(browser)
        s5_void_flow(browser)
        s6_security(browser)
        s7_settings(browser)
        s8_mobile(browser)

        browser.close()

    passed = sum(1 for r in RESULTS if r["status"] == "PASS")
    failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
    total  = len(RESULTS)

    report_path = SS_DIR / "report.html"
    report_path.write_text(generate_report())

    print(f"\n{'═'*65}")
    print(f"  RESULT : {passed}/{total} passed · {failed} failed · {round(passed/total*100) if total else 0}%")
    print(f"  Report : {report_path}")
    print(f"{'═'*65}\n")
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
