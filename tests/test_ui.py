"""
SP Dhaba — Playwright UI Test Suite
Runs against a live URL, tests every page, takes screenshots.

Usage:
  python3 tests/test_ui.py https://spdhaba-prd.up.railway.app

Or locally:
  python3 tests/test_ui.py http://localhost:3000

Results saved to: tests/screenshots/
"""

import sys
import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

# ── Config ────────────────────────────────────────────────────────────────
BASE_URL   = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000"
ADMIN_EMAIL    = "admin@spdhaba.com"
ADMIN_PASSWORD = "Admin@123"
STAFF_EMAIL    = "lokesh@spdhaba.com"
STAFF_PASSWORD = "Staff@123"
VIEWER_EMAIL   = "display@spdhaba.com"
VIEWER_PASSWORD= "View@123"

SCREENSHOTS_DIR = Path(__file__).parent / "screenshots"
SCREENSHOTS_DIR.mkdir(exist_ok=True)

results = []

def ss(page, name):
    """Take screenshot and save"""
    path = SCREENSHOTS_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    return path

def test(name, passed, message=""):
    icon = "✅" if passed else "❌"
    results.append((icon, name, message))
    print(f"  {icon} {name}" + (f" — {message}" if message else ""))

def login(page, email, password):
    page.goto(f"{BASE_URL}/login")
    page.wait_for_load_state("networkidle")
    page.fill('[data-testid="login-email-input"]', email)
    page.fill('[data-testid="login-password-input"]', password)
    page.click('[data-testid="login-submit-button"]')
    page.wait_for_load_state("networkidle")
    time.sleep(1)

def run_tests():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page    = context.new_page()

        print(f"\n{'='*60}")
        print(f"SP DHABA — UI TEST SUITE")
        print(f"URL: {BASE_URL}")
        print(f"{'='*60}\n")

        # ── 1. LOGIN PAGE ──────────────────────────────────────────────
        print("1. Login Page")
        page.goto(f"{BASE_URL}/login")
        page.wait_for_load_state("networkidle")
        ss(page, "01_login_page")

        # Check left side not blank (gradient should be visible)
        left_side = page.locator(".hidden.md\\:block")
        test("Login left side visible", left_side.count() > 0)

        # Check correct placeholder
        placeholder = page.locator('[data-testid="login-email-input"]').get_attribute("placeholder")
        test("Email placeholder correct", "spdhaba" in (placeholder or ""), f"Got: {placeholder}")

        # Check title
        title = page.title()
        test("Page title correct", "SP Royal" in title or "Dhaba" in title, f"Got: {title}")

        # Check no Emergent badge
        emergent = page.locator("#emergent-badge")
        test("No Emergent badge", emergent.count() == 0)

        # ── 2. ADMIN LOGIN ─────────────────────────────────────────────
        print("\n2. Admin Login")
        login(page, ADMIN_EMAIL, ADMIN_PASSWORD)
        current = page.url
        test("Admin redirects to dashboard", "/dashboard" in current, f"Got: {current}")
        ss(page, "02_dashboard")

        # Check business name visible
        biz = page.locator('[data-testid="business-name"]')
        test("Business name visible", biz.count() > 0 and len(biz.first.text_content()) > 0)

        # Check no infinite spinner
        spinner = page.locator('[data-testid="dashboard-loading"]')
        time.sleep(2)
        test("Dashboard loaded (no infinite spinner)", spinner.count() == 0)

        # ── 3. LIVE STOCK ──────────────────────────────────────────────
        print("\n3. Live Stock")
        page.goto(f"{BASE_URL}/stock")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        ss(page, "03_live_stock")
        stock_page = page.locator('[data-testid="live-stock-page"]')
        test("Live Stock page loaded", stock_page.count() > 0)

        # ── 4. PURCHASES ───────────────────────────────────────────────
        print("\n4. Purchases")
        page.goto(f"{BASE_URL}/purchases")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        ss(page, "04_purchases")
        purchases_page = page.locator('[data-testid="purchases-page"]')
        test("Purchases page loaded", purchases_page.count() > 0)

        # Check timestamp column exists
        logged_at = page.locator("text=Logged at")
        test("'Logged at' column visible", logged_at.count() > 0)

        # ── 5. DAILY USAGE ─────────────────────────────────────────────
        print("\n5. Daily Usage")
        page.goto(f"{BASE_URL}/usage")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        ss(page, "05_daily_usage")
        usage_page = page.locator('[data-testid="usage-page"]')
        test("Daily Usage page loaded", usage_page.count() > 0)

        # ── 6. SALES ──────────────────────────────────────────────────
        print("\n6. Sales")
        page.goto(f"{BASE_URL}/sales")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        ss(page, "06_sales")
        sales_page = page.locator('[data-testid="sales-page"]')
        test("Sales page loaded", sales_page.count() > 0)

        # ── 7. EXPENSES ────────────────────────────────────────────────
        print("\n7. Expenses")
        page.goto(f"{BASE_URL}/expenses")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        ss(page, "07_expenses")
        expenses_page = page.locator('[data-testid="expenses-page"]')
        test("Expenses page loaded", expenses_page.count() > 0)

        # ── 8. P&L ────────────────────────────────────────────────────
        print("\n8. P&L")
        page.goto(f"{BASE_URL}/pnl")
        page.wait_for_load_state("networkidle")
        time.sleep(3)
        ss(page, "08_pnl")
        pnl_page = page.locator('[data-testid="pnl-page"]')
        test("P&L page loaded", pnl_page.count() > 0)

        # ── 9. ALERTS ─────────────────────────────────────────────────
        print("\n9. Alerts")
        page.goto(f"{BASE_URL}/alerts")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        ss(page, "09_alerts")
        test("Alerts page loaded", "/alerts" in page.url)

        # ── 10. ITEMS ─────────────────────────────────────────────────
        print("\n10. Items")
        page.goto(f"{BASE_URL}/items")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        ss(page, "10_items")
        test("Items page loaded", "/items" in page.url)

        # ── 11. SALARIES ──────────────────────────────────────────────
        print("\n11. Salaries")
        page.goto(f"{BASE_URL}/salaries")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        ss(page, "11_salaries")
        test("Salaries page loaded", "/salaries" in page.url)

        # ── 12. SETTINGS ──────────────────────────────────────────────
        print("\n12. Settings")
        page.goto(f"{BASE_URL}/settings")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        ss(page, "12_settings")
        test("Settings page loaded", "/settings" in page.url)

        # ── 13. DISPLAY MODE ──────────────────────────────────────────
        print("\n13. Display Mode")
        page.goto(f"{BASE_URL}/display")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        ss(page, "13_display_mode")
        display_page = page.locator('[data-testid="display-mode-page"]')
        test("Display Mode loaded", display_page.count() > 0)

        # Test fullscreen button doesn't open new tab
        tabs_before = len(context.pages)
        fs_btn = page.locator('[data-testid="display-fullscreen"]')
        if fs_btn.count() > 0:
            fs_btn.click()
            time.sleep(1)
            tabs_after = len(context.pages)
            test("Fullscreen no new tab", tabs_after == tabs_before,
                 f"Before: {tabs_before} After: {tabs_after}")
        else:
            test("Fullscreen button found", False, "Button not found")

        # ── 14. STAFF LOGIN ───────────────────────────────────────────
        print("\n14. Staff Login (Lokesh)")
        page.goto(f"{BASE_URL}/login")
        page.wait_for_load_state("networkidle")
        login(page, STAFF_EMAIL, STAFF_PASSWORD)
        ss(page, "14_staff_login")
        current = page.url
        test("Staff redirects to /stock", "/stock" in current, f"Got: {current}")

        # Staff should NOT see dashboard
        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        test("Staff cannot access dashboard", "/forbidden" in page.url or "/stock" in page.url,
             f"Got: {page.url}")
        ss(page, "14b_staff_no_dashboard")

        # ── 15. VIEWER LOGIN ──────────────────────────────────────────
        print("\n15. Viewer Login (Display)")
        page.goto(f"{BASE_URL}/login")
        page.wait_for_load_state("networkidle")
        login(page, VIEWER_EMAIL, VIEWER_PASSWORD)
        ss(page, "15_viewer_login")
        current = page.url
        test("Viewer redirects to /display", "/display" in current, f"Got: {current}")

        # Viewer should NOT access settings
        page.goto(f"{BASE_URL}/settings")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        test("Viewer cannot access settings", "/forbidden" in page.url or "/display" in page.url,
             f"Got: {page.url}")
        ss(page, "15b_viewer_no_settings")

        # ── SUMMARY ───────────────────────────────────────────────────
        browser.close()

        passed = sum(1 for r in results if r[0] == "✅")
        failed = sum(1 for r in results if r[0] == "❌")
        total  = len(results)

        print(f"\n{'='*60}")
        print(f"RESULTS: {passed}/{total} passed  |  {failed} failed")
        print(f"Screenshots saved to: {SCREENSHOTS_DIR}/")
        print(f"{'='*60}")

        if failed > 0:
            print("\nFailed tests:")
            for icon, name, msg in results:
                if icon == "❌":
                    print(f"  ❌ {name}" + (f" — {msg}" if msg else ""))

        return failed == 0

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
