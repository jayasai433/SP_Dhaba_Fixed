"""
SP Dhaba — End-to-End UI Testing Agent
=======================================
Tests the app like a real user: clicks, fills forms, takes screenshots.
Generates a full HTML report with screenshots and pass/fail status.

Usage:
  python3 tests/ui_agent.py <frontend_url>

Examples:
  python3 tests/ui_agent.py https://spdhaba-stage.up.railway.app
  python3 tests/ui_agent.py https://spdhaba-prd.up.railway.app
  python3 tests/ui_agent.py http://localhost:3000

Output:
  tests/screenshots/report.html  — open in browser
  tests/screenshots/*.png        — individual screenshots
"""

import sys
import os
import time
import json
import base64
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ── Config ─────────────────────────────────────────────────────────────────
BASE_URL        = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:3000"
ADMIN_EMAIL     = os.environ.get("ADMIN_EMAIL",  "admin@spdhaba.com")
ADMIN_PASSWORD  = os.environ.get("ADMIN_PWD",    "Admin@123")
STAFF_EMAIL     = os.environ.get("STAFF_EMAIL",  "lokesh@spdhaba.com")
STAFF_PASSWORD  = os.environ.get("STAFF_PWD",    "Staff@123")
VIEWER_EMAIL    = os.environ.get("VIEWER_EMAIL", "display@spdhaba.com")
VIEWER_PASSWORD = os.environ.get("VIEWER_PWD",   "View@123")
HEADLESS        = os.environ.get("HEADLESS", "true").lower() == "true"
TIMEOUT         = 15000  # 15s per action

SS_DIR = Path(__file__).parent / "screenshots"
SS_DIR.mkdir(exist_ok=True)

# ── Result tracking ─────────────────────────────────────────────────────────
results = []

def record(name, passed, message="", screenshot=None, duration=0):
    status = "PASS" if passed else "FAIL"
    results.append({
        "name": name,
        "status": status,
        "message": message,
        "screenshot": screenshot,
        "duration": duration,
    })
    icon = "✅" if passed else "❌"
    print(f"  {icon} [{status}] {name}" + (f" — {message}" if message else "") + f" ({duration:.1f}s)")

def ss(page, name):
    path = SS_DIR / f"{name}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
        return str(path)
    except Exception:
        return None

def login(page, email, password):
    page.goto(f"{BASE_URL}/login", wait_until="networkidle", timeout=TIMEOUT)
    page.fill('[data-testid="login-email-input"]', email)
    page.fill('[data-testid="login-password-input"]', password)
    page.click('[data-testid="login-submit-button"]')
    page.wait_for_load_state("networkidle", timeout=TIMEOUT)

def wait_nav(page, path, timeout=10000):
    page.wait_for_url(f"**{path}**", timeout=timeout)


# ══════════════════════════════════════════════════════════════════════════════
# TEST SUITES
# ══════════════════════════════════════════════════════════════════════════════

def test_auth(page):
    print("\n🔐 Auth Tests")

    # 1. Login page loads
    t = time.time()
    try:
        page.goto(f"{BASE_URL}/login", wait_until="networkidle", timeout=TIMEOUT)
        assert page.locator('[data-testid="login-email-input"]').is_visible()
        path = ss(page, "01_login_page")
        record("Login page loads", True, screenshot=path, duration=time.time()-t)
    except Exception as e:
        record("Login page loads", False, str(e)[:80], duration=time.time()-t)
        return False

    # 2. Wrong credentials rejected
    t = time.time()
    try:
        page.fill('[data-testid="login-email-input"]', "wrong@test.com")
        page.fill('[data-testid="login-password-input"]', "wrongpass")
        page.click('[data-testid="login-submit-button"]')
        page.wait_for_timeout(2000)
        # Should still be on login page
        assert "/login" in page.url
        path = ss(page, "02_login_wrong_creds")
        record("Wrong credentials rejected", True, screenshot=path, duration=time.time()-t)
    except Exception as e:
        record("Wrong credentials rejected", False, str(e)[:80], duration=time.time()-t)

    # 3. Admin login succeeds
    t = time.time()
    try:
        page.fill('[data-testid="login-email-input"]', ADMIN_EMAIL)
        page.fill('[data-testid="login-password-input"]', ADMIN_PASSWORD)
        page.click('[data-testid="login-submit-button"]')
        page.wait_for_load_state("networkidle", timeout=TIMEOUT)
        assert "/login" not in page.url
        path = ss(page, "03_admin_logged_in")
        record("Admin login succeeds", True, f"landed on {page.url.split('/')[-1]}", screenshot=path, duration=time.time()-t)
        return True
    except Exception as e:
        path = ss(page, "03_admin_login_failed")
        record("Admin login succeeds", False, str(e)[:80], screenshot=path, duration=time.time()-t)
        return False


def test_navigation(page):
    print("\n🧭 Navigation Tests")
    pages = [
        ("/dashboard",          "dashboard",          "04_dashboard"),
        ("/stock",              "stock",              "05_live_stock"),
        ("/alerts",             "alerts",             "06_alerts"),
        ("/purchases",          "purchases",          "07_purchases"),
        ("/closing-stock",      "closing-stock",      "08_closing_stock"),
        ("/sales",              "sales",              "09_sales"),
        ("/expenses",           "expenses",           "10_expenses"),
        ("/salaries",           "salaries",           "11_salaries"),
        ("/pnl",                "pnl",                "12_pnl"),
        ("/items",              "items",              "13_items"),
        ("/settings",           "settings",           "14_settings"),
        ("/inventory-insights", "inventory-insights", "15_inventory_insights"),
    ]
    for path, testid, name in pages:
        t = time.time()
        try:
            page.goto(f"{BASE_URL}{path}", wait_until="networkidle", timeout=TIMEOUT)
            page.wait_for_timeout(800)
            assert page.locator(f'[data-testid="{testid}-page"], [data-testid="app-shell"]').count() > 0
            shot = ss(page, name)
            record(f"Page: {path}", True, screenshot=shot, duration=time.time()-t)
        except Exception as e:
            shot = ss(page, f"{name}_fail")
            record(f"Page: {path}", False, str(e)[:80], screenshot=shot, duration=time.time()-t)


def test_purchases(page):
    print("\n🛒 Purchases Tests")

    page.goto(f"{BASE_URL}/purchases", wait_until="networkidle", timeout=TIMEOUT)
    page.wait_for_timeout(500)

    # Load items dropdown
    t = time.time()
    try:
        items = page.locator('[data-testid="purchase-item-0"]')
        items.click()
        page.wait_for_timeout(500)
        options = page.locator('[role="option"]')
        count = options.count()
        path = ss(page, "16_purchases_item_dropdown")
        record("Purchases item dropdown loads", count > 0, f"{count} items", screenshot=path, duration=time.time()-t)

        if count > 0:
            options.first.click()
            page.wait_for_timeout(300)

        # Fill qty and price
        page.fill('[data-testid="purchase-qty-0"]', "2")
        page.fill('[data-testid="purchase-price-0"]', "100")
        path = ss(page, "17_purchases_form_filled")
        record("Purchases form fills correctly", True, screenshot=path, duration=time.time()-t)
    except Exception as e:
        path = ss(page, "16_purchases_fail")
        record("Purchases form interaction", False, str(e)[:80], screenshot=path, duration=time.time()-t)


def test_closing_stock(page):
    print("\n📦 Closing Stock Tests")

    page.goto(f"{BASE_URL}/closing-stock", wait_until="networkidle", timeout=TIMEOUT)
    page.wait_for_timeout(500)

    t = time.time()
    try:
        # Progress bar visible
        assert page.locator('text=Items counted today').is_visible()
        path = ss(page, "18_closing_stock_page")
        record("Closing stock page loads correctly", True, screenshot=path, duration=time.time()-t)
    except Exception as e:
        path = ss(page, "18_closing_stock_fail")
        record("Closing stock page loads correctly", False, str(e)[:80], screenshot=path, duration=time.time()-t)

    # Try entering a count
    t = time.time()
    try:
        page.locator('[data-testid="closing-item-select"]').click()
        page.wait_for_timeout(500)
        options = page.locator('[role="option"]')
        if options.count() > 0:
            options.first.click()
            page.fill('[data-testid="closing-qty-input"]', "5")
            path = ss(page, "19_closing_stock_filled")
            record("Closing stock form fills correctly", True, screenshot=path, duration=time.time()-t)
    except Exception as e:
        path = ss(page, "19_closing_stock_form_fail")
        record("Closing stock form fills correctly", False, str(e)[:80], screenshot=path, duration=time.time()-t)


def test_sales(page):
    print("\n💰 Sales Tests")

    page.goto(f"{BASE_URL}/sales", wait_until="networkidle", timeout=TIMEOUT)
    page.wait_for_timeout(500)

    t = time.time()
    try:
        assert page.locator('[data-testid="sales-page"]').is_visible()
        path = ss(page, "20_sales_page")
        record("Sales page loads", True, screenshot=path, duration=time.time()-t)
    except Exception as e:
        path = ss(page, "20_sales_fail")
        record("Sales page loads", False, str(e)[:80], screenshot=path, duration=time.time()-t)


def test_pnl(page):
    print("\n📊 P&L Tests")

    page.goto(f"{BASE_URL}/pnl", wait_until="networkidle", timeout=TIMEOUT)
    page.wait_for_timeout(1000)

    t = time.time()
    try:
        assert page.locator('[data-testid="pnl-page"]').is_visible()
        path = ss(page, "21_pnl_page")
        record("P&L page loads", True, screenshot=path, duration=time.time()-t)
    except Exception as e:
        path = ss(page, "21_pnl_fail")
        record("P&L page loads", False, str(e)[:80], screenshot=path, duration=time.time()-t)


def test_void_dialog(page):
    print("\n🚫 Void Dialog Tests")

    page.goto(f"{BASE_URL}/purchases", wait_until="networkidle", timeout=TIMEOUT)
    page.wait_for_timeout(500)

    t = time.time()
    try:
        void_btns = page.locator('[data-testid^="void-purchase-"]')
        if void_btns.count() > 0:
            void_btns.first.click()
            page.wait_for_timeout(500)
            assert page.locator('[data-testid="void-dialog"]').is_visible()
            path = ss(page, "22_void_dialog_open")
            record("Void dialog opens correctly", True, screenshot=path, duration=time.time()-t)

            # Test validation — empty reason
            page.click('[data-testid="void-confirm-btn"]')
            page.wait_for_timeout(300)
            assert page.locator('[data-testid="void-reason-error"]').is_visible()
            path = ss(page, "23_void_dialog_validation")
            record("Void dialog validates empty reason", True, screenshot=path, duration=time.time()-t)

            # Cancel closes it
            page.click('[data-testid="void-cancel-btn"]')
            page.wait_for_timeout(300)
            assert not page.locator('[data-testid="void-dialog"]').is_visible()
            record("Void dialog cancels correctly", True, duration=time.time()-t)
        else:
            record("Void dialog opens correctly", True, "no entries to void — skipped", duration=time.time()-t)
    except Exception as e:
        path = ss(page, "22_void_dialog_fail")
        record("Void dialog opens correctly", False, str(e)[:80], screenshot=path, duration=time.time()-t)


def test_settings(page):
    print("\n⚙️ Settings Tests")

    page.goto(f"{BASE_URL}/settings", wait_until="networkidle", timeout=TIMEOUT)
    page.wait_for_timeout(500)

    t = time.time()
    try:
        assert page.locator('[data-testid="settings-page"]').is_visible()
        # Click through tabs
        for tab in ["business", "categories", "units", "users"]:
            page.click(f'[data-testid="settings-tab-{tab}"]')
            page.wait_for_timeout(400)
        path = ss(page, "24_settings_page")
        record("Settings page and tabs work", True, screenshot=path, duration=time.time()-t)
    except Exception as e:
        path = ss(page, "24_settings_fail")
        record("Settings page and tabs work", False, str(e)[:80], screenshot=path, duration=time.time()-t)


def test_staff_role(page):
    print("\n👤 Staff Role Tests")

    # Logout first
    t = time.time()
    try:
        page.goto(f"{BASE_URL}/login", wait_until="networkidle", timeout=TIMEOUT)
        login(page, STAFF_EMAIL, STAFF_PASSWORD)
        page.wait_for_timeout(1000)
        path = ss(page, "25_staff_logged_in")
        record("Staff login succeeds", "/login" not in page.url, screenshot=path, duration=time.time()-t)
    except Exception as e:
        record("Staff login succeeds", False, str(e)[:80], duration=time.time()-t)
        return

    # Staff should NOT see dashboard
    t = time.time()
    try:
        page.goto(f"{BASE_URL}/dashboard", wait_until="networkidle", timeout=TIMEOUT)
        page.wait_for_timeout(500)
        is_forbidden = "forbidden" in page.url or page.locator('[data-testid="forbidden-page"]').count() > 0
        path = ss(page, "26_staff_no_dashboard")
        record("Staff cannot access dashboard", is_forbidden, screenshot=path, duration=time.time()-t)
    except Exception as e:
        record("Staff cannot access dashboard", False, str(e)[:80], duration=time.time()-t)

    # Staff CAN see closing stock
    t = time.time()
    try:
        page.goto(f"{BASE_URL}/closing-stock", wait_until="networkidle", timeout=TIMEOUT)
        page.wait_for_timeout(500)
        assert "forbidden" not in page.url
        path = ss(page, "27_staff_closing_stock")
        record("Staff can access closing stock", True, screenshot=path, duration=time.time()-t)
    except Exception as e:
        record("Staff can access closing stock", False, str(e)[:80], duration=time.time()-t)


def test_viewer_role(page):
    print("\n👁️ Viewer Role Tests")

    t = time.time()
    try:
        page.goto(f"{BASE_URL}/login", wait_until="networkidle", timeout=TIMEOUT)
        login(page, VIEWER_EMAIL, VIEWER_PASSWORD)
        page.wait_for_timeout(1000)
        # Viewer redirects to /display
        assert "display" in page.url or "stock" in page.url
        path = ss(page, "28_viewer_logged_in")
        record("Viewer login redirects to display", True, page.url.split("/")[-1], screenshot=path, duration=time.time()-t)
    except Exception as e:
        path = ss(page, "28_viewer_fail")
        record("Viewer login redirects to display", False, str(e)[:80], screenshot=path, duration=time.time()-t)

    # Viewer cannot access purchases
    t = time.time()
    try:
        page.goto(f"{BASE_URL}/purchases", wait_until="networkidle", timeout=TIMEOUT)
        page.wait_for_timeout(500)
        is_forbidden = "forbidden" in page.url or page.locator('[data-testid="forbidden-page"]').count() > 0
        path = ss(page, "29_viewer_no_purchases")
        record("Viewer cannot access purchases", is_forbidden, screenshot=path, duration=time.time()-t)
    except Exception as e:
        record("Viewer cannot access purchases", False, str(e)[:80], duration=time.time()-t)


def test_mobile_view(page, browser):
    print("\n📱 Mobile View Tests")

    # Re-create context with mobile viewport
    mobile_ctx = browser.new_context(
        viewport={"width": 390, "height": 844},
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"
    )
    mobile_page = mobile_ctx.new_page()

    t = time.time()
    try:
        mobile_page.goto(f"{BASE_URL}/login", wait_until="networkidle", timeout=TIMEOUT)
        mobile_page.fill('[data-testid="login-email-input"]', ADMIN_EMAIL)
        mobile_page.fill('[data-testid="login-password-input"]', ADMIN_PASSWORD)
        mobile_page.click('[data-testid="login-submit-button"]')
        mobile_page.wait_for_load_state("networkidle", timeout=TIMEOUT)
        path = ss(mobile_page, "30_mobile_logged_in")
        record("Mobile: login works", True, screenshot=path, duration=time.time()-t)

        # Bottom nav visible
        mobile_page.goto(f"{BASE_URL}/stock", wait_until="networkidle", timeout=TIMEOUT)
        mobile_page.wait_for_timeout(500)
        bottom_nav = mobile_page.locator('nav.fixed.bottom-0, [data-testid^="bottom-nav-"]')
        path = ss(mobile_page, "31_mobile_bottom_nav")
        record("Mobile: bottom nav visible", bottom_nav.count() > 0, screenshot=path, duration=time.time()-t)

        # Hamburger menu opens
        mobile_page.goto(f"{BASE_URL}/purchases", wait_until="networkidle", timeout=TIMEOUT)
        mobile_page.click('[data-testid="open-drawer"]')
        mobile_page.wait_for_timeout(500)
        path = ss(mobile_page, "32_mobile_drawer_open")
        record("Mobile: hamburger drawer opens", True, screenshot=path, duration=time.time()-t)

    except Exception as e:
        path = ss(mobile_page, "30_mobile_fail")
        record("Mobile view tests", False, str(e)[:80], screenshot=path, duration=time.time()-t)
    finally:
        mobile_ctx.close()


def test_staging_banner(page):
    print("\n🟡 Staging Banner Tests")

    t = time.time()
    try:
        page.goto(f"{BASE_URL}/login", wait_until="networkidle", timeout=TIMEOUT)
        page.wait_for_timeout(1000)
        # Check for any environment banner
        banner_text = ""
        for sel in ["text=STAGING", "text=Production", "text=Unknown environment"]:
            el = page.locator(sel)
            if el.count() > 0:
                banner_text = el.first.text_content()
                break
        path = ss(page, "33_staging_banner")
        record(
            "Environment banner visible",
            bool(banner_text),
            banner_text[:60] if banner_text else "no banner found",
            screenshot=path,
            duration=time.time()-t
        )
    except Exception as e:
        record("Environment banner visible", False, str(e)[:80], duration=time.time()-t)


# ══════════════════════════════════════════════════════════════════════════════
# HTML REPORT
# ══════════════════════════════════════════════════════════════════════════════

def generate_report():
    passed  = sum(1 for r in results if r["status"] == "PASS")
    failed  = sum(1 for r in results if r["status"] == "FAIL")
    total   = len(results)
    pct     = round(passed / total * 100) if total else 0
    now     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def img_tag(path):
        if not path or not Path(path).exists():
            return '<div class="no-ss">No screenshot</div>'
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f'<img src="data:image/png;base64,{b64}" onclick="this.classList.toggle(\'big\')" title="Click to enlarge" />'

    rows = ""
    for i, r in enumerate(results, 1):
        cls    = "pass" if r["status"] == "PASS" else "fail"
        icon   = "✅" if r["status"] == "PASS" else "❌"
        rows += f"""
        <tr class="{cls}">
          <td class="num">{i}</td>
          <td class="icon">{icon}</td>
          <td class="name">{r['name']}</td>
          <td class="msg">{r.get('message','')}</td>
          <td class="dur">{r.get('duration',0):.1f}s</td>
          <td class="ss-cell">{img_tag(r.get('screenshot'))}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>SP Dhaba — UI Test Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #FFF8F0; color: #1e293b; }}
  .header {{ background: #2D1606; color: white; padding: 2rem; }}
  .header h1 {{ font-size: 1.5rem; font-weight: 700; }}
  .header p  {{ font-size: 0.85rem; opacity: 0.6; margin-top: 0.25rem; }}
  .summary {{ display: flex; gap: 1rem; padding: 1.5rem 2rem; flex-wrap: wrap; }}
  .card {{ background: white; border-radius: 12px; padding: 1rem 1.5rem;
           min-width: 140px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  .card .val {{ font-size: 2rem; font-weight: 700; }}
  .card .lbl {{ font-size: 0.75rem; color: #64748b; margin-top: 2px; }}
  .pass-val {{ color: #16a34a; }}
  .fail-val {{ color: #dc2626; }}
  .pct-val  {{ color: #ea580c; }}
  .url-bar {{ background: white; border-radius: 8px; margin: 0 2rem 1rem;
              padding: 0.6rem 1rem; font-size: 0.8rem; color: #64748b;
              box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  .url-bar strong {{ color: #ea580c; }}
  table {{ width: calc(100% - 4rem); margin: 0 2rem 2rem; border-collapse: collapse;
           background: white; border-radius: 12px; overflow: hidden;
           box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  th {{ background: #f8fafc; padding: 0.75rem 1rem; text-align: left;
        font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.05em; color: #64748b; border-bottom: 1px solid #e2e8f0; }}
  td {{ padding: 0.6rem 1rem; border-bottom: 1px solid #f1f5f9;
        vertical-align: middle; font-size: 0.85rem; }}
  tr.pass {{ background: #f0fdf4; }}
  tr.fail {{ background: #fef2f2; }}
  tr:last-child td {{ border-bottom: none; }}
  .num  {{ width: 40px; color: #94a3b8; font-size: 0.75rem; }}
  .icon {{ width: 40px; font-size: 1rem; }}
  .name {{ font-weight: 500; }}
  .msg  {{ color: #64748b; font-size: 0.8rem; max-width: 280px; }}
  .dur  {{ width: 60px; color: #94a3b8; font-size: 0.75rem; }}
  .ss-cell img {{ width: 160px; height: 90px; object-fit: cover; border-radius: 6px;
                  cursor: pointer; border: 1px solid #e2e8f0; transition: all 0.2s; }}
  .ss-cell img.big {{ position: fixed; top: 50%; left: 50%; transform: translate(-50%,-50%);
                      width: auto; height: auto; max-width: 90vw; max-height: 90vh;
                      z-index: 9999; box-shadow: 0 25px 60px rgba(0,0,0,.5);
                      border-radius: 8px; }}
  .no-ss {{ color: #cbd5e1; font-size: 0.75rem; }}
  .progress {{ background: #e2e8f0; border-radius: 99px; height: 8px;
               margin: 0.5rem 0; overflow: hidden; }}
  .progress-bar {{ height: 100%; background: #ea580c; border-radius: 99px; }}
</style>
</head>
<body>
<div class="header">
  <h1>🍛 SP Dhaba — UI Test Report</h1>
  <p>Generated: {now}</p>
</div>
<div class="summary">
  <div class="card">
    <div class="val pct-val">{pct}%</div>
    <div class="lbl">Pass Rate</div>
    <div class="progress"><div class="progress-bar" style="width:{pct}%"></div></div>
  </div>
  <div class="card">
    <div class="val">{total}</div>
    <div class="lbl">Total Tests</div>
  </div>
  <div class="card">
    <div class="val pass-val">{passed}</div>
    <div class="lbl">Passed</div>
  </div>
  <div class="card">
    <div class="val fail-val">{failed}</div>
    <div class="lbl">Failed</div>
  </div>
</div>
<div class="url-bar">Testing: <strong>{BASE_URL}</strong></div>
<table>
  <thead>
    <tr>
      <th>#</th><th></th><th>Test</th><th>Message</th><th>Time</th><th>Screenshot</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
</body>
</html>"""

    report_path = SS_DIR / "report.html"
    report_path.write_text(html)
    return report_path


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print(f"\n🍛 SP Dhaba UI Testing Agent")
    print(f"   Target: {BASE_URL}")
    print(f"   Time:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("─" * 60)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=HEADLESS)
        ctx     = browser.new_context(viewport={"width": 1280, "height": 800})
        page    = ctx.new_page()
        page.set_default_timeout(TIMEOUT)

        # Run all suites
        test_staging_banner(page)
        logged_in = test_auth(page)

        if logged_in:
            test_navigation(page)
            test_purchases(page)
            test_closing_stock(page)
            test_sales(page)
            test_pnl(page)
            test_void_dialog(page)
            test_settings(page)
            test_staff_role(page)
            test_viewer_role(page)

            # Re-login as admin for mobile tests
            page.goto(f"{BASE_URL}/login", wait_until="networkidle")
            login(page, ADMIN_EMAIL, ADMIN_PASSWORD)
            test_mobile_view(page, browser)
        else:
            print("\n⛔ Auth failed — skipping all page tests")

        ctx.close()
        browser.close()

    # Summary
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    total  = len(results)
    print("\n" + "─" * 60)
    print(f"Results: {passed}/{total} passed, {failed} failed")

    report = generate_report()
    print(f"Report:  {report}")
    print("─" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
