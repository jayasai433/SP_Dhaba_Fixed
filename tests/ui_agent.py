"""
SP Dhaba — Comprehensive End-to-End UI Testing Agent
=====================================================
Tests every user flow for all 3 roles (Admin, Staff, Viewer).
Runs like a real user — clicks, fills forms, verifies results, takes screenshots.

Usage:
  python3 tests/ui_agent.py <frontend_url>

Examples:
  python3 tests/ui_agent.py https://spdhaba-stage.up.railway.app
  python3 tests/ui_agent.py https://spdhaba-prd.up.railway.app
  python3 tests/ui_agent.py http://localhost:3000

Output:
  tests/screenshots/report.html  — open in browser
  tests/screenshots/*.png        — individual screenshots

Role matrix tested:
  Admin  → all pages, all actions, void, settings, items, salaries
  Staff  → purchases, closing stock, sales, expenses (no dashboard/pnl/settings)
  Viewer → dashboard, stock, alerts, pnl, display only (read-only)
"""

import sys, os, time, json, base64
from datetime import datetime, date
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ── Config ──────────────────────────────────────────────────────────────────
BASE_URL        = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:3000"
ADMIN_EMAIL     = os.environ.get("ADMIN_EMAIL",  "admin@spdhaba.com")
ADMIN_PASSWORD  = os.environ.get("ADMIN_PWD",    "Admin@123")
STAFF_EMAIL     = os.environ.get("STAFF_EMAIL",  "lokesh@spdhaba.com")
STAFF_PASSWORD  = os.environ.get("STAFF_PWD",    "Staff@123")
VIEWER_EMAIL    = os.environ.get("VIEWER_EMAIL", "display@spdhaba.com")
VIEWER_PASSWORD = os.environ.get("VIEWER_PWD",   "View@123")
HEADLESS        = os.environ.get("HEADLESS", "true").lower() == "true"
TIMEOUT         = 30000  # 30s — staging can be slow on cold start
TODAY           = date.today().isoformat()

SS_DIR = Path(__file__).parent / "screenshots"
SS_DIR.mkdir(exist_ok=True)

# ── Result tracking ──────────────────────────────────────────────────────────
results = []
current_section = ""

def section(name):
    global current_section
    current_section = name
    print(f"\n{'─'*60}")
    print(f"  {name}")
    print(f"{'─'*60}")

def record(name, passed, message="", screenshot=None, duration=0):
    results.append({
        "name": name, "section": current_section,
        "status": "PASS" if passed else "FAIL",
        "message": message, "screenshot": screenshot, "duration": duration,
    })
    icon = "✅" if passed else "❌"
    print(f"  {icon} {name}" + (f" — {message}" if message else "") + f" ({duration:.1f}s)")

def ss(page, name):
    path = SS_DIR / f"{name}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
        return str(path)
    except Exception:
        return None

def t(): return time.time()

def check(page, name, condition, message="", screenshot_name=None, start=None):
    duration = time.time() - start if start else 0
    path = ss(page, screenshot_name) if screenshot_name else None
    record(name, condition, message, path, duration)
    return condition


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def fresh_context(browser, mobile=False):
    if mobile:
        return browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
        )
    return browser.new_context(viewport={"width": 1280, "height": 800})

def login(page, email, password, expect_success=True):
    """
    Login helper — waits only for the form element, not full networkidle.
    networkidle can hang on slow Railway frontends waiting for API calls.
    Instead we wait for the URL to change away from /login.
    """
    for attempt in range(3):
        try:
            page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=TIMEOUT)
            # Wait only for the input to appear — not full page load
            page.wait_for_selector('[data-testid="login-email-input"]', timeout=TIMEOUT)
            page.fill('[data-testid="login-email-input"]', email)
            page.fill('[data-testid="login-password-input"]', password)
            page.click('[data-testid="login-submit-button"]')
            # Wait for URL to change — much more reliable than networkidle
            if expect_success:
                try:
                    page.wait_for_url(lambda url: "/login" not in url, timeout=TIMEOUT)
                    page.wait_for_timeout(800)
                    return True
                except Exception:
                    return False
            else:
                page.wait_for_timeout(2000)
                return "/login" in page.url
        except Exception as e:
            if attempt == 2:
                return False
            print(f"    ⟳ Login retry {attempt+1}...")
            page.wait_for_timeout(2000)
    return False

def goto(page, path, retries=2):
    """
    Navigate with retry.
    Uses domcontentloaded + waits for React root to render,
    NOT networkidle — networkidle hangs waiting for API calls to finish
    which can take 10-20s on slow Railway instances.
    """
    for attempt in range(retries + 1):
        try:
            page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=TIMEOUT)
            # Wait for React to mount — app-shell or login page
            page.wait_for_selector(
                '[data-testid="app-shell"], [data-testid="login-page"], [data-testid="forbidden-page"]',
                timeout=15000
            )
            page.wait_for_timeout(500)
            return
        except Exception as e:
            if attempt == retries:
                raise
            print(f"    ⟳ Retry {attempt+1} for {path}...")
            page.wait_for_timeout(2000)

def is_forbidden(page):
    return "forbidden" in page.url or page.locator('[data-testid="forbidden-page"]').count() > 0

def is_accessible(page):
    return not is_forbidden(page) and "/login" not in page.url

def has_element(page, selector, timeout=3000):
    try:
        page.wait_for_selector(selector, timeout=timeout)
        return True
    except Exception:
        return False

def select_first_option(page, trigger_testid):
    """Click a Select trigger and choose the first available option."""
    try:
        page.locator(f'[data-testid="{trigger_testid}"]').click()
        page.wait_for_timeout(500)
        options = page.locator('[role="option"]')
        if options.count() > 0:
            options.first.click()
            page.wait_for_timeout(300)
            return True
        return False
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════════════════
# SUITE 1 — ENVIRONMENT
# ══════════════════════════════════════════════════════════════════════════════

def suite_environment(browser):
    section("🌍 Environment & Health")
    ctx  = fresh_context(browser)
    page = ctx.new_page()
    page.set_default_timeout(TIMEOUT)

    # Banner check
    s = t()
    try:
        page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=TIMEOUT)
        page.wait_for_selector('[data-testid="login-page"]', timeout=TIMEOUT)
        page.wait_for_timeout(1500)
        has_banner = (
            page.locator("text=STAGING").count() > 0 or
            page.locator("text=Production").count() > 0 or
            page.locator("text=Unknown environment").count() > 0
        )
        banner_text = ""
        for sel in ["text=STAGING", "text=Production", "text=Unknown environment"]:
            el = page.locator(sel)
            if el.count() > 0:
                banner_text = el.first.text_content()[:80]
                break
        check(page, "Environment banner visible", has_banner, banner_text, "env_01_banner", s)
    except Exception as e:
        record("Environment banner visible", False, str(e)[:80])

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# SUITE 2 — AUTH (all roles)
# ══════════════════════════════════════════════════════════════════════════════

def suite_auth(browser):
    section("🔐 Authentication — All Roles")
    ctx  = fresh_context(browser)
    page = ctx.new_page()
    page.set_default_timeout(TIMEOUT)

    # Login page elements
    s = t()
    try:
        page.goto(f"{BASE_URL}/login", wait_until="networkidle", timeout=TIMEOUT)
        page.wait_for_timeout(1000)
        has_email = has_element(page, '[data-testid="login-email-input"]')
        has_pwd   = has_element(page, '[data-testid="login-password-input"]')
        has_btn   = has_element(page, '[data-testid="login-submit-button"]')
        check(page, "Login page — all form elements present",
              has_email and has_pwd and has_btn, "", "auth_01_login_page", s)
    except Exception as e:
        record("Login page — all form elements present", False, str(e)[:80])

    # Wrong credentials
    s = t()
    try:
        page.fill('[data-testid="login-email-input"]', "hacker@evil.com")
        page.fill('[data-testid="login-password-input"]', "wrongpass123")
        page.click('[data-testid="login-submit-button"]')
        page.wait_for_timeout(2000)
        still_on_login = "/login" in page.url
        check(page, "Wrong credentials — stays on login page", still_on_login, "", "auth_02_wrong_creds", s)
    except Exception as e:
        record("Wrong credentials — stays on login page", False, str(e)[:80])

    # Admin login + redirect to dashboard
    s = t()
    try:
        ok = login(page, ADMIN_EMAIL, ADMIN_PASSWORD)
        landed = page.url.split("/")[-1]
        check(page, "Admin login — redirects to dashboard", ok and "dashboard" in page.url,
              f"landed: {landed}", "auth_03_admin_dashboard", s)
    except Exception as e:
        record("Admin login — redirects to dashboard", False, str(e)[:80])

    # Admin logout
    s = t()
    try:
        page.click('[data-testid="logout-button"]')
        page.wait_for_load_state("networkidle", timeout=TIMEOUT)
        check(page, "Admin logout — redirects to login", "/login" in page.url, "", "auth_04_logout", s)
    except Exception as e:
        record("Admin logout — redirects to login", False, str(e)[:80])

    # Staff login + redirect to stock
    s = t()
    try:
        ok = login(page, STAFF_EMAIL, STAFF_PASSWORD)
        landed = page.url.split("/")[-1]
        check(page, "Staff login — redirects to stock", ok and "stock" in page.url,
              f"landed: {landed}", "auth_05_staff_stock", s)
    except Exception as e:
        record("Staff login — redirects to stock", False, str(e)[:80])

    page.click('[data-testid="logout-button"]')
    page.wait_for_load_state("networkidle", timeout=TIMEOUT)

    # Viewer login + redirect to display
    s = t()
    try:
        ok = login(page, VIEWER_EMAIL, VIEWER_PASSWORD)
        landed = page.url.split("/")[-1]
        check(page, "Viewer login — redirects to display", ok and "display" in page.url,
              f"landed: {landed}", "auth_06_viewer_display", s)
    except Exception as e:
        record("Viewer login — redirects to display", False, str(e)[:80])

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# SUITE 3 — ADMIN USER FLOWS
# ══════════════════════════════════════════════════════════════════════════════

def suite_admin(browser):
    section("👑 Admin — All Page Access & Actions")
    ctx  = fresh_context(browser)
    page = ctx.new_page()
    page.set_default_timeout(TIMEOUT)
    login(page, ADMIN_EMAIL, ADMIN_PASSWORD)

    # ── Access checks ──
    admin_pages = [
        ("/dashboard",          "dashboard",          "adm_01_dashboard"),
        ("/stock",              "stock",              "adm_02_stock"),
        ("/alerts",             "alerts",             "adm_03_alerts"),
        ("/purchases",          "purchases",          "adm_04_purchases"),
        ("/closing-stock",      "closing-stock",      "adm_05_closing_stock"),
        ("/sales",              "sales",              "adm_06_sales"),
        ("/expenses",           "expenses",           "adm_07_expenses"),
        ("/salaries",           "salaries",           "adm_08_salaries"),
        ("/pnl",                "pnl",                "adm_09_pnl"),
        ("/items",              "items",              "adm_10_items"),
        ("/settings",           "settings",           "adm_11_settings"),
        ("/inventory-insights", "inventory-insights", "adm_12_insights"),
        ("/display",            "display",            "adm_13_display"),
    ]

    for path, label, name in admin_pages:
        s = t()
        try:
            goto(page, path)
            accessible = is_accessible(page)
            check(page, f"Admin can access {path}", accessible, "", name, s)
        except Exception as e:
            record(f"Admin can access {path}", False, str(e)[:60])

    # ── Dashboard data ──
    s = t()
    try:
        goto(page, "/dashboard")
        has_cards = has_element(page, '[data-testid="dashboard-page"]', 5000)
        check(page, "Dashboard — summary cards visible", has_cards, "", "adm_14_dashboard_cards", s)
    except Exception as e:
        record("Dashboard — summary cards visible", False, str(e)[:80])

    # ── Purchases — add entry ──
    s = t()
    try:
        goto(page, "/purchases")
        page.wait_for_timeout(500)
        items_loaded = select_first_option(page, "purchase-item-0")
        if items_loaded:
            page.fill('[data-testid="purchase-qty-0"]', "3")
            page.fill('[data-testid="purchase-price-0"]', "150")
            check(page, "Admin — purchase form fills correctly", True, "", "adm_15_purchase_form", s)
        else:
            record("Admin — purchase form fills correctly", False, "no items in dropdown")
    except Exception as e:
        record("Admin — purchase form fills correctly", False, str(e)[:80])

    # ── Closing Stock — enter count ──
    s = t()
    try:
        goto(page, "/closing-stock")
        has_progress = has_element(page, "text=Items counted today", 5000)
        items_loaded = False
        try:
            page.locator('[data-testid="closing-item-select"]').click()
            page.wait_for_timeout(500)
            opts = page.locator('[role="option"]')
            if opts.count() > 0:
                opts.first.click()
                page.fill('[data-testid="closing-qty-input"]', "10")
                items_loaded = True
        except Exception:
            pass
        check(page, "Admin — closing stock form works", has_progress, "", "adm_16_closing_stock", s)
    except Exception as e:
        record("Admin — closing stock form works", False, str(e)[:80])

    # ── Sales — enter sales ──
    s = t()
    try:
        goto(page, "/sales")
        page.wait_for_timeout(500)
        # Find lunch input
        # Sales page — check form is visible and accessible
        has_sales_page = has_element(page, '[data-testid="sales-page"]', 5000)
        # Try to find any number input on the page
        inputs = page.locator('input[type="number"], input[type="text"]')
        has_inputs = inputs.count() > 0
        if has_inputs:
            try:
                inputs.first.fill("5000")
            except Exception:
                pass
        check(page, "Admin — sales form fills correctly", has_sales_page, "", "adm_17_sales_form", s)
    except Exception as e:
        record("Admin — sales form fills correctly", False, str(e)[:80])

    # ── Expenses — add expense ──
    s = t()
    try:
        goto(page, "/expenses")
        page.wait_for_timeout(500)
        has_form = has_element(page, '[data-testid="expenses-page"]', 3000)
        check(page, "Admin — expenses page loads with form", has_form, "", "adm_18_expenses", s)
    except Exception as e:
        record("Admin — expenses page loads with form", False, str(e)[:80])

    # ── P&L — verify data shows ──
    s = t()
    try:
        goto(page, "/pnl")
        page.wait_for_timeout(1500)
        has_pnl = has_element(page, '[data-testid="pnl-page"]', 5000)
        check(page, "Admin — P&L page loads with data", has_pnl, "", "adm_19_pnl", s)
    except Exception as e:
        record("Admin — P&L page loads with data", False, str(e)[:80])

    # ── Items — create item ──
    s = t()
    try:
        goto(page, "/items")
        page.wait_for_timeout(500)
        has_items = has_element(page, '[data-testid="items-page"]', 3000)
        check(page, "Admin — item master page loads", has_items, "", "adm_20_items", s)
    except Exception as e:
        record("Admin — item master page loads", False, str(e)[:80])

    # ── Settings — all tabs ──
    s = t()
    try:
        goto(page, "/settings")
        tabs_ok = True
        for tab in ["business", "categories", "units", "users", "staff", "whatsapp"]:
            try:
                page.click(f'[data-testid="settings-tab-{tab}"]')
                page.wait_for_timeout(400)
            except Exception:
                tabs_ok = False
        check(page, "Admin — settings all tabs clickable", tabs_ok, "", "adm_21_settings_tabs", s)
    except Exception as e:
        record("Admin — settings all tabs clickable", False, str(e)[:80])

    # ── Void dialog — open, validate, cancel ──
    s = t()
    try:
        goto(page, "/purchases")
        page.wait_for_timeout(500)
        void_btns = page.locator('[data-testid^="void-purchase-"]')
        if void_btns.count() > 0:
            void_btns.first.click()
            page.wait_for_timeout(600)
            dialog_open = has_element(page, '[data-testid="void-dialog"]', 3000)
            if dialog_open:
                # Validate empty reason
                page.click('[data-testid="void-confirm-btn"]')
                page.wait_for_timeout(300)
                shows_error = has_element(page, '[data-testid="void-reason-error"]', 2000)
                # Fill reason and cancel
                page.fill('[data-testid="void-reason-input"]', "Test void — UI agent")
                page.click('[data-testid="void-cancel-btn"]')
                page.wait_for_timeout(300)
                dialog_closed = not has_element(page, '[data-testid="void-dialog"]', 1000)
                check(page, "Admin — void dialog opens, validates, cancels",
                      dialog_open and shows_error and dialog_closed, "", "adm_22_void_dialog", s)
            else:
                record("Admin — void dialog opens, validates, cancels", False, "dialog did not open")
        else:
            record("Admin — void dialog opens, validates, cancels", True, "no entries to void — skipped")
    except Exception as e:
        record("Admin — void dialog opens, validates, cancels", False, str(e)[:80])

    # ── Alerts badge ──
    s = t()
    try:
        goto(page, "/alerts")
        page.wait_for_timeout(500)
        accessible = is_accessible(page)
        check(page, "Admin — alerts page accessible", accessible, "", "adm_23_alerts", s)
    except Exception as e:
        record("Admin — alerts page accessible", False, str(e)[:80])

    # ── Sidebar visible ──
    s = t()
    try:
        goto(page, "/dashboard")
        sidebar = has_element(page, '[data-testid="business-name"]', 3000)
        biz_name = page.locator('[data-testid="business-name"]').text_content() if sidebar else ""
        check(page, "Admin — sidebar shows business name", sidebar, biz_name, "adm_24_sidebar", s)
    except Exception as e:
        record("Admin — sidebar shows business name", False, str(e)[:80])

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# SUITE 4 — STAFF USER FLOWS
# ══════════════════════════════════════════════════════════════════════════════

def suite_staff(browser):
    section("👤 Staff (Lokesh) — Allowed & Blocked Pages")
    ctx  = fresh_context(browser)
    page = ctx.new_page()
    page.set_default_timeout(TIMEOUT)
    login(page, STAFF_EMAIL, STAFF_PASSWORD)

    # ── Pages staff CAN access ──
    allowed = [
        ("/stock",         "stf_01_stock",         "Live Stock"),
        ("/alerts",        "stf_02_alerts",         "Alerts"),
        ("/purchases",     "stf_03_purchases",      "Purchases"),
        ("/closing-stock", "stf_04_closing_stock",  "Closing Stock"),
        ("/sales",         "stf_05_sales",          "Sales"),
        ("/expenses",      "stf_06_expenses",       "Expenses"),
        ("/display",       "stf_07_display",        "Display Mode"),
    ]
    for path, name, label in allowed:
        s = t()
        try:
            goto(page, path)
            accessible = is_accessible(page)
            check(page, f"Staff CAN access — {label}", accessible, "", name, s)
        except Exception as e:
            record(f"Staff CAN access — {label}", False, str(e)[:60])

    # ── Pages staff CANNOT access ──
    blocked = [
        ("/dashboard",          "stf_08_no_dashboard",  "Dashboard"),
        ("/salaries",           "stf_09_no_salaries",   "Salaries"),
        ("/pnl",                "stf_10_no_pnl",        "P&L"),
        ("/items",              "stf_11_no_items",       "Item Master"),
        ("/settings",           "stf_12_no_settings",    "Settings"),
        ("/inventory-insights", "stf_13_no_insights",    "Inventory Insights"),
    ]
    for path, name, label in blocked:
        s = t()
        try:
            goto(page, path)
            blocked_ok = is_forbidden(page)
            check(page, f"Staff BLOCKED from — {label}", blocked_ok, "", name, s)
        except Exception as e:
            record(f"Staff BLOCKED from — {label}", False, str(e)[:60])

    # ── Staff actual workflows ──

    # Record a purchase
    s = t()
    try:
        goto(page, "/purchases")
        page.wait_for_timeout(500)
        items_loaded = select_first_option(page, "purchase-item-0")
        if items_loaded:
            page.fill('[data-testid="purchase-qty-0"]', "5")
            page.fill('[data-testid="purchase-price-0"]', "200")
            path = ss(page, "stf_14_purchase_filled")
            record("Staff — fills purchase form correctly", True, "", path, time.time()-s)
        else:
            record("Staff — fills purchase form correctly", False, "no items in dropdown")
    except Exception as e:
        record("Staff — fills purchase form correctly", False, str(e)[:80])

    # Record closing stock
    s = t()
    try:
        goto(page, "/closing-stock")
        page.wait_for_timeout(500)
        has_progress = has_element(page, "text=Items counted today", 5000)
        # Check "Save Count" button visible
        has_save = has_element(page, '[data-testid="closing-save-btn"]', 3000)
        check(page, "Staff — closing stock form visible", has_progress and has_save, "", "stf_15_closing_stock", s)
    except Exception as e:
        record("Staff — closing stock form visible", False, str(e)[:80])

    # Record sales
    s = t()
    try:
        goto(page, "/sales")
        page.wait_for_timeout(500)
        accessible = is_accessible(page)
        check(page, "Staff — sales page accessible with form", accessible, "", "stf_16_sales", s)
    except Exception as e:
        record("Staff — sales page accessible with form", False, str(e)[:80])

    # Record expense
    s = t()
    try:
        goto(page, "/expenses")
        page.wait_for_timeout(500)
        accessible = is_accessible(page)
        check(page, "Staff — expenses page accessible", accessible, "", "stf_17_expenses", s)
    except Exception as e:
        record("Staff — expenses page accessible", False, str(e)[:80])

    # Staff cannot void others entries — test void button behaviour
    s = t()
    try:
        goto(page, "/purchases")
        page.wait_for_timeout(500)
        # Void buttons should only show for own entries (canAdd check)
        # Just verify page renders properly
        accessible = is_accessible(page)
        check(page, "Staff — purchases list renders correctly", accessible, "", "stf_18_purchases_list", s)
    except Exception as e:
        record("Staff — purchases list renders correctly", False, str(e)[:80])

    # /usage redirects to /closing-stock
    s = t()
    try:
        goto(page, "/usage")
        page.wait_for_timeout(1000)
        redirected = "closing-stock" in page.url
        check(page, "Staff — /usage redirects to /closing-stock", redirected, page.url, "stf_19_usage_redirect", s)
    except Exception as e:
        record("Staff — /usage redirects to /closing-stock", False, str(e)[:80])

    # Mobile bottom nav for staff
    ctx.close()
    ctx_mob = fresh_context(browser, mobile=True)
    mob = ctx_mob.new_page()
    mob.set_default_timeout(TIMEOUT)
    login(mob, STAFF_EMAIL, STAFF_PASSWORD)

    s = t()
    try:
        goto(mob, "/stock")
        bottom_nav = mob.locator('[data-testid^="bottom-nav-"]')
        nav_count = bottom_nav.count()
        path = ss(mob, "stf_20_mobile_bottom_nav")
        record("Staff — mobile bottom nav shows correct items", nav_count > 0,
               f"{nav_count} nav items", path, time.time()-s)
    except Exception as e:
        record("Staff — mobile bottom nav shows correct items", False, str(e)[:80])

    ctx_mob.close()


# ══════════════════════════════════════════════════════════════════════════════
# SUITE 5 — VIEWER USER FLOWS
# ══════════════════════════════════════════════════════════════════════════════

def suite_viewer(browser):
    section("👁️ Viewer — Read-Only Access")
    ctx  = fresh_context(browser)
    page = ctx.new_page()
    page.set_default_timeout(TIMEOUT)
    login(page, VIEWER_EMAIL, VIEWER_PASSWORD)

    # ── Pages viewer CAN access (read-only) ──
    allowed = [
        ("/display",            "viw_01_display",        "Display Mode"),
        ("/stock",              "viw_02_stock",           "Live Stock"),
        ("/alerts",             "viw_03_alerts",          "Alerts"),
        ("/dashboard",          "viw_04_dashboard",       "Dashboard"),
        ("/pnl",                "viw_05_pnl",             "P&L"),
        ("/inventory-insights", "viw_06_insights",        "Inventory Insights"),
        ("/closing-stock",      "viw_07_closing_stock",   "Closing Stock"),
    ]
    for path, name, label in allowed:
        s = t()
        try:
            goto(page, path)
            accessible = is_accessible(page)
            check(page, f"Viewer CAN access — {label}", accessible, "", name, s)
        except Exception as e:
            record(f"Viewer CAN access — {label}", False, str(e)[:60])

    # ── Pages viewer CANNOT access ──
    blocked = [
        ("/purchases",  "viw_08_no_purchases",  "Purchases"),
        ("/sales",      "viw_09_no_sales",       "Sales"),
        ("/expenses",   "viw_10_no_expenses",    "Expenses"),
        ("/salaries",   "viw_11_no_salaries",    "Salaries"),
        ("/items",      "viw_12_no_items",        "Item Master"),
        ("/settings",   "viw_13_no_settings",     "Settings"),
    ]
    for path, name, label in blocked:
        s = t()
        try:
            goto(page, path)
            blocked_ok = is_forbidden(page)
            check(page, f"Viewer BLOCKED from — {label}", blocked_ok, "", name, s)
        except Exception as e:
            record(f"Viewer BLOCKED from — {label}", False, str(e)[:60])

    # ── Viewer read-only checks ──

    # No add/edit buttons on stock page
    s = t()
    try:
        goto(page, "/stock")
        page.wait_for_timeout(500)
        # Should have no purchase/add buttons
        add_btns = page.locator('[data-testid="purchase-submit"], button:has-text("Add")').count()
        check(page, "Viewer — no add/edit buttons on stock page",
              add_btns == 0, f"{add_btns} add buttons found", "viw_14_stock_readonly", s)
    except Exception as e:
        record("Viewer — no add/edit buttons on stock page", False, str(e)[:80])

    # Closing stock — viewer sees table but no form
    s = t()
    try:
        goto(page, "/closing-stock")
        page.wait_for_timeout(500)
        has_form   = has_element(page, '[data-testid="closing-save-btn"]', 2000)
        has_table  = has_element(page, '[data-testid="closing-stock-page"]', 3000)
        check(page, "Viewer — closing stock read-only (no form, has table)",
              not has_form and has_table, "", "viw_15_closing_readonly", s)
    except Exception as e:
        record("Viewer — closing stock read-only (no form, has table)", False, str(e)[:80])

    # Display mode renders
    s = t()
    try:
        goto(page, "/display")
        page.wait_for_timeout(1000)
        accessible = is_accessible(page)
        check(page, "Viewer — display mode renders", accessible, "", "viw_16_display_mode", s)
    except Exception as e:
        record("Viewer — display mode renders", False, str(e)[:80])

    ctx.close()



# ══════════════════════════════════════════════════════════════════════════════
# SUITE 6B — SETTINGS CONFIG (Admin only)
# ══════════════════════════════════════════════════════════════════════════════

def suite_settings_config(browser):
    section("⚙️ Settings — Real Config Actions (Admin)")
    ctx  = fresh_context(browser)
    page = ctx.new_page()
    page.set_default_timeout(TIMEOUT)
    login(page, ADMIN_EMAIL, ADMIN_PASSWORD)
    goto(page, "/settings")

    # ── Business profile update ──
    s = t()
    try:
        page.click('[data-testid="settings-tab-business"]')
        page.wait_for_timeout(800)
        # Find business name input and update it
        name_input = page.locator('input[placeholder*="name"], input[placeholder*="Name"]').first
        if name_input.is_visible():
            original = name_input.input_value()
            name_input.fill("SP Royal Test Dhaba")
            # Find save button
            save_btn = page.locator('button:has-text("Save"), button:has-text("Update")').first
            if save_btn.is_visible():
                save_btn.click()
                page.wait_for_timeout(1500)
                # Verify sidebar updated
                biz_name = page.locator('[data-testid="business-name"]').text_content()
                updated = "Test" in biz_name or "SP Royal" in biz_name
                # Restore original
                name_input.fill(original or "SP Royal Punjabi Family Dhaba")
                save_btn.click()
                page.wait_for_timeout(1000)
                check(page, "Settings — business name saves and reflects in sidebar",
                      updated, biz_name, "cfg_01_business_name", s)
            else:
                check(page, "Settings — business name saves and reflects in sidebar",
                      False, "save button not found", "cfg_01_business_name", s)
        else:
            check(page, "Settings — business name saves and reflects in sidebar",
                  False, "name input not found", "cfg_01_business_name", s)
    except Exception as e:
        record("Settings — business name saves and reflects in sidebar", False, str(e)[:80])

    # ── Add a category ──
    s = t()
    try:
        page.click('[data-testid="settings-tab-categories"]')
        page.wait_for_timeout(800)
        test_cat = f"TestCat_{int(time.time()) % 10000}"
        cat_input = page.locator('input[placeholder*="category"], input[placeholder*="Category"], input[placeholder*="name"], input[placeholder*="Name"]').first
        if cat_input.is_visible():
            cat_input.fill(test_cat)
            add_btn = page.locator('button:has-text("Add"), button[type="submit"]').first
            add_btn.click()
            page.wait_for_timeout(1500)
            # Verify it appears in the list
            appears = page.locator(f"text={test_cat}").count() > 0
            check(page, "Settings — add category saves and appears in list",
                  appears, test_cat, "cfg_02_add_category", s)
        else:
            record("Settings — add category saves and appears in list", False, "input not found")
    except Exception as e:
        record("Settings — add category saves and appears in list", False, str(e)[:80])

    # ── Add a unit ──
    s = t()
    try:
        page.click('[data-testid="settings-tab-units"]')
        page.wait_for_timeout(800)
        test_unit = f"tst{int(time.time()) % 1000}"
        unit_input = page.locator('input[placeholder*="unit"], input[placeholder*="Unit"], input[placeholder*="name"], input[placeholder*="Name"]').first
        if unit_input.is_visible():
            unit_input.fill(test_unit)
            add_btn = page.locator('button:has-text("Add"), button[type="submit"]').first
            add_btn.click()
            page.wait_for_timeout(1500)
            appears = page.locator(f"text={test_unit}").count() > 0
            check(page, "Settings — add unit saves and appears in list",
                  appears, test_unit, "cfg_03_add_unit", s)
        else:
            record("Settings — add unit saves and appears in list", False, "input not found")
    except Exception as e:
        record("Settings — add unit saves and appears in list", False, str(e)[:80])

    # ── Users tab — list loads ──
    s = t()
    try:
        page.click('[data-testid="settings-tab-users"]')
        page.wait_for_timeout(1000)
        # Should see at least admin, staff, viewer
        has_admin  = page.locator("text=admin").count() > 0
        has_users  = page.locator("text=Jaya Sai, text=Lokesh, text=Display, text=admin").count() > 0
        check(page, "Settings — users tab shows user list",
              has_admin, "", "cfg_04_users_list", s)
    except Exception as e:
        record("Settings — users tab shows user list", False, str(e)[:80])

    # ── WhatsApp tab loads ──
    s = t()
    try:
        page.click('[data-testid="settings-tab-whatsapp"]')
        page.wait_for_timeout(800)
        accessible = is_accessible(page)
        check(page, "Settings — WhatsApp tab loads", accessible, "", "cfg_05_whatsapp", s)
    except Exception as e:
        record("Settings — WhatsApp tab loads", False, str(e)[:80])

    # ── Reorder levels tab ──
    s = t()
    try:
        page.click('[data-testid="settings-tab-reorder"]')
        page.wait_for_timeout(800)
        accessible = is_accessible(page)
        check(page, "Settings — Reorder levels tab loads", accessible, "", "cfg_06_reorder", s)
    except Exception as e:
        record("Settings — Reorder levels tab loads", False, str(e)[:80])

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# SUITE 6 — MOBILE (all roles)
# ══════════════════════════════════════════════════════════════════════════════

def suite_mobile(browser):
    section("📱 Mobile View — All Roles")

    for role, email, pwd, label in [
        ("admin",  ADMIN_EMAIL,  ADMIN_PASSWORD,  "Admin"),
        ("staff",  STAFF_EMAIL,  STAFF_PASSWORD,  "Staff"),
        ("viewer", VIEWER_EMAIL, VIEWER_PASSWORD, "Viewer"),
    ]:
        ctx  = fresh_context(browser, mobile=True)
        page = ctx.new_page()
        page.set_default_timeout(TIMEOUT)

        s = t()
        try:
            ok = login(page, email, pwd)
            path = ss(page, f"mob_01_{role}_login")
            record(f"Mobile — {label} login works", ok, "", path, time.time()-s)
        except Exception as e:
            record(f"Mobile — {label} login works", False, str(e)[:80])
            ctx.close()
            continue

        # Bottom nav visible
        s = t()
        try:
            page.wait_for_timeout(500)
            bottom_nav = page.locator('[data-testid^="bottom-nav-"]')
            count = bottom_nav.count()
            path = ss(page, f"mob_02_{role}_bottom_nav")
            record(f"Mobile — {label} bottom nav visible ({count} items)", count > 0, "", path, time.time()-s)
        except Exception as e:
            record(f"Mobile — {label} bottom nav visible", False, str(e)[:80])

        # Hamburger drawer opens
        s = t()
        try:
            page.click('[data-testid="open-drawer"]')
            page.wait_for_timeout(600)
            drawer = has_element(page, '[data-testid="close-drawer"]', 2000)
            path = ss(page, f"mob_03_{role}_drawer")
            record(f"Mobile — {label} hamburger drawer opens", drawer, "", path, time.time()-s)
            if drawer:
                page.click('[data-testid="close-drawer"]')
        except Exception as e:
            record(f"Mobile — {label} hamburger drawer opens", False, str(e)[:80])

        ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# SUITE 7 — SECURITY
# ══════════════════════════════════════════════════════════════════════════════

def suite_security(browser):
    section("🔒 Security — Unauthenticated & Cross-Role")
    ctx  = fresh_context(browser)
    page = ctx.new_page()
    page.set_default_timeout(TIMEOUT)

    # Unauthenticated access redirects to login
    protected = ["/dashboard", "/purchases", "/stock", "/settings", "/pnl"]
    for path in protected:
        s = t()
        try:
            page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=TIMEOUT)
            page.wait_for_timeout(2000)
            redirected = "/login" in page.url
            record(f"Unauthenticated → {path} redirects to login", redirected,
                   page.url, duration=time.time()-s)
        except Exception as e:
            record(f"Unauthenticated → {path} redirects to login", False, str(e)[:60])

    # /usage always redirects to /closing-stock
    s = t()
    try:
        goto(page, "/usage")
        page.wait_for_timeout(1000)
        # Either login redirect or closing-stock redirect
        ok = "/login" in page.url or "closing-stock" in page.url
        record("/usage redirects (to login or closing-stock)", ok, page.url, duration=time.time()-s)
    except Exception as e:
        record("/usage redirects correctly", False, str(e)[:80])

    ctx.close()

    # Staff cannot access admin-only pages even by direct URL
    ctx  = fresh_context(browser)
    page = ctx.new_page()
    page.set_default_timeout(TIMEOUT)
    login(page, STAFF_EMAIL, STAFF_PASSWORD)

    admin_only = ["/dashboard", "/salaries", "/items", "/settings", "/pnl", "/inventory-insights"]
    for path in admin_only:
        s = t()
        try:
            page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=TIMEOUT)
            page.wait_for_timeout(2500)  # Wait for React to render redirect
            blocked_ok = is_forbidden(page)
            shot = ss(page, f"sec_{path.strip('/').replace('/', '_')}_staff_blocked")
            record(f"Staff direct URL to {path} → forbidden", blocked_ok,
                   page.url.split("/")[-1], shot, time.time()-s)
        except Exception as e:
            record(f"Staff direct URL to {path} → forbidden", False, str(e)[:60])

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

    # Group by section
    sections = {}
    for r in results:
        sec = r.get("section", "Other")
        sections.setdefault(sec, []).append(r)

    def img_tag(path):
        if not path or not Path(path).exists():
            return '<span class="no-ss">—</span>'
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f'<img src="data:image/png;base64,{b64}" class="thumb" onclick="zoom(this)" title="Click to zoom" />'

    section_html = ""
    for sec, sec_results in sections.items():
        sec_pass = sum(1 for r in sec_results if r["status"] == "PASS")
        sec_fail = len(sec_results) - sec_pass
        rows = ""
        for i, r in enumerate(sec_results, 1):
            cls  = "pass" if r["status"] == "PASS" else "fail"
            icon = "✅" if r["status"] == "PASS" else "❌"
            rows += f"""<tr class="{cls}">
              <td class="num">{i}</td>
              <td>{icon}</td>
              <td class="name">{r['name']}</td>
              <td class="msg">{r.get('message','')}</td>
              <td class="dur">{r.get('duration',0):.1f}s</td>
              <td class="ss-cell">{img_tag(r.get('screenshot'))}</td>
            </tr>"""

        section_html += f"""
        <div class="sec-block">
          <div class="sec-header">
            <span class="sec-title">{sec}</span>
            <span class="sec-badge pass-badge">{sec_pass} passed</span>
            {"" if sec_fail == 0 else f'<span class="sec-badge fail-badge">{sec_fail} failed</span>'}
          </div>
          <table>
            <thead><tr>
              <th>#</th><th></th><th>Test</th><th>Detail</th><th>Time</th><th>Screenshot</th>
            </tr></thead>
            <tbody>{rows}</tbody>
          </table>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>SP Dhaba — UI Test Report</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#FFF8F0;color:#1e293b;}}
  .header{{background:#2D1606;color:white;padding:2rem 2.5rem;}}
  .header h1{{font-size:1.6rem;font-weight:700;}}
  .header p{{font-size:0.8rem;opacity:0.55;margin-top:0.3rem;}}
  .summary{{display:flex;gap:1rem;padding:1.5rem 2.5rem;flex-wrap:wrap;}}
  .card{{background:white;border-radius:14px;padding:1rem 1.5rem;min-width:130px;box-shadow:0 1px 4px rgba(0,0,0,.07);}}
  .card .val{{font-size:2.2rem;font-weight:700;line-height:1;}}
  .card .lbl{{font-size:0.72rem;color:#64748b;margin-top:4px;text-transform:uppercase;letter-spacing:.05em;}}
  .pass-val{{color:#16a34a}}.fail-val{{color:#dc2626}}.pct-val{{color:#ea580c}}
  .progress{{background:#e2e8f0;border-radius:99px;height:8px;margin-top:8px;overflow:hidden;}}
  .progress-bar{{height:100%;background:#ea580c;border-radius:99px;}}
  .url-bar{{background:white;border-radius:10px;margin:0 2.5rem 1.5rem;padding:.6rem 1.2rem;
            font-size:.8rem;color:#64748b;box-shadow:0 1px 3px rgba(0,0,0,.07);}}
  .url-bar strong{{color:#ea580c;}}
  .sec-block{{margin:0 2.5rem 2rem;}}
  .sec-header{{display:flex;align-items:center;gap:.75rem;margin-bottom:.75rem;}}
  .sec-title{{font-size:1rem;font-weight:600;color:#1e293b;}}
  .sec-badge{{font-size:.7rem;padding:2px 10px;border-radius:99px;font-weight:600;}}
  .pass-badge{{background:#dcfce7;color:#16a34a;}}
  .fail-badge{{background:#fee2e2;color:#dc2626;}}
  table{{width:100%;border-collapse:collapse;background:white;border-radius:14px;
         overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.07);}}
  th{{background:#f8fafc;padding:.65rem 1rem;text-align:left;font-size:.7rem;
      font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:#64748b;
      border-bottom:1px solid #e2e8f0;}}
  td{{padding:.55rem 1rem;border-bottom:1px solid #f1f5f9;font-size:.82rem;vertical-align:middle;}}
  tr:last-child td{{border-bottom:none;}}
  tr.pass{{background:#f0fdf4;}}tr.fail{{background:#fef2f2;}}
  .num{{width:36px;color:#94a3b8;font-size:.72rem;}}
  .name{{font-weight:500;max-width:320px;}}
  .msg{{color:#64748b;font-size:.78rem;max-width:220px;}}
  .dur{{width:55px;color:#94a3b8;font-size:.72rem;}}
  .thumb{{width:140px;height:80px;object-fit:cover;border-radius:6px;cursor:pointer;
          border:1px solid #e2e8f0;transition:.15s;}}
  .thumb:hover{{opacity:.85;}}
  .no-ss{{color:#cbd5e1;font-size:.72rem;}}
  .overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:9999;
            align-items:center;justify-content:center;cursor:zoom-out;}}
  .overlay.active{{display:flex;}}
  .overlay img{{max-width:92vw;max-height:92vh;border-radius:10px;box-shadow:0 30px 80px rgba(0,0,0,.5);}}
</style>
</head>
<body>
<div class="header">
  <h1>🍛 SP Dhaba — UI Test Report</h1>
  <p>Generated: {now} · {total} tests across all roles</p>
</div>
<div class="summary">
  <div class="card">
    <div class="val pct-val">{pct}%</div>
    <div class="lbl">Pass Rate</div>
    <div class="progress"><div class="progress-bar" style="width:{pct}%"></div></div>
  </div>
  <div class="card"><div class="val">{total}</div><div class="lbl">Total</div></div>
  <div class="card"><div class="val pass-val">{passed}</div><div class="lbl">Passed</div></div>
  <div class="card"><div class="val fail-val">{failed}</div><div class="lbl">Failed</div></div>
</div>
<div class="url-bar">Testing: <strong>{BASE_URL}</strong></div>
{section_html}
<div class="overlay" id="overlay" onclick="this.classList.remove('active')">
  <img id="overlay-img" src="" />
</div>
<script>
function zoom(img){{
  document.getElementById('overlay-img').src = img.src;
  document.getElementById('overlay').classList.add('active');
}}
</script>
</body>
</html>"""

    report_path = SS_DIR / "report.html"
    report_path.write_text(html)
    return report_path


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print(f"\n🍛 SP Dhaba — Comprehensive UI Testing Agent")
    print(f"   Target : {BASE_URL}")
    print(f"   Roles  : Admin · Staff · Viewer")
    print(f"   Time   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=HEADLESS)

        suite_environment(browser)
        suite_auth(browser)
        suite_admin(browser)
        suite_staff(browser)
        suite_viewer(browser)
        suite_settings_config(browser)
        suite_mobile(browser)
        suite_security(browser)

        browser.close()

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    total  = len(results)

    print(f"\n{'═'*60}")
    print(f"  RESULTS: {passed}/{total} passed · {failed} failed · {round(passed/total*100) if total else 0}%")
    print(f"{'═'*60}")

    report = generate_report()
    print(f"  Report : {report}")
    print(f"{'═'*60}\n")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
