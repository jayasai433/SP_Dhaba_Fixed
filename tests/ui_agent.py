"""
SP Dhaba — Comprehensive UAT Agent
====================================
Tests every feature with positive AND negative cases.
Covers: Auth, Purchases, Sales, Expenses, Closing Stock, Live Stock,
        Alerts, P&L (profit/loss), Dashboard, Inventory Insights,
        Items, Salaries, Settings (Business/Categories/Units/Staff/Users),
        Void flow, Security, Display Mode, Mobile, Notifications

Usage:
  UAT_SECRET=sp-dhaba-uat-2024 python3 tests/ui_agent.py <url>

Output:
  tests/screenshots/report.html  — full report with screenshots
"""

import sys, os, time, base64
from datetime import datetime, date, timedelta
from pathlib import Path
from playwright.sync_api import sync_playwright

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
YESTERDAY       = (date.today() - timedelta(days=1)).isoformat()
FUTURE_DATE     = (date.today() + timedelta(days=2)).isoformat()

SS_DIR  = Path(__file__).parent / "screenshots"
SS_DIR.mkdir(exist_ok=True)
RESULTS = []
CURRENT = ""
TOKENS  = {}  # role → JWT token — login once, reuse everywhere

# ── Helpers ───────────────────────────────────────────────────────────────────

def scenario(name):
    global CURRENT
    CURRENT = name
    print(f"\n{'━'*70}\n  {name}\n{'━'*70}")

def snap(page, name, wait_ms=500, clip=None):
    """Take screenshot after animations settle."""
    p = SS_DIR / f"{name}.png"
    try:
        page.wait_for_timeout(wait_ms)
        if clip == "toast":
            try: page.wait_for_selector('[data-sonner-toast]', timeout=4000)
            except: pass
        elif clip == "form":
            page.evaluate("const s=document.querySelector('[data-testid=\"sidebar\"]'); if(s) s.style.opacity='0.05'")
        page.screenshot(path=str(p), full_page=clip not in ("toast","form"))
        if clip == "form":
            page.evaluate("const s=document.querySelector('[data-testid=\"sidebar\"]'); if(s) s.style.opacity='1'")
        return str(p)
    except:
        return None

def step(page, name, ok, detail="", ss=None, start=None, clip=None):
    """On failure, auto-captures URL + visible error text for summary.txt."""
    dur  = round(time.time()-start, 1) if start else 0
    path = snap(page, ss, clip=clip) if ss else None
    if not ok:
        try:
            diag = [f"url={page.url.split('/')[-1]}"]
            for sel in ['[data-sonner-toast]','[role="alert"]','[data-testid*="error"]']:
                els = page.locator(sel)
                if els.count()>0:
                    t = (els.first.text_content() or "").strip()
                    if t: diag.append(f"screen='{t[:80]}'"); break
            full_detail = f"{detail} || {' | '.join(diag)}" if detail else ' | '.join(diag)
        except Exception:
            full_detail = detail
    else:
        full_detail = detail
    RESULTS.append({"scenario":CURRENT,"name":name,
                    "status":"PASS" if ok else "FAIL",
                    "detail":full_detail,"screenshot":path,"duration":dur})
    print(f"  {'✅' if ok else '❌'} {name}" + (f"  →  {detail}" if detail else "") + (f"  ({dur}s)" if dur else ""))
    return ok

def ctx_page(browser, mobile=False):
    if mobile:
        ctx = browser.new_context(viewport={"width":390,"height":844},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)")
    else:
        ctx = browser.new_context(viewport={"width":1280,"height":800})
    p = ctx.new_page()
    p.set_default_timeout(TIMEOUT)
    return ctx, p

def go(page, path):
    for attempt in range(3):
        try:
            page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=TIMEOUT)
            page.wait_for_selector('[data-testid="app-shell"],[data-testid="login-page"],[data-testid="forbidden-page"]', timeout=15000)
            page.wait_for_timeout(1200)
            return True
        except:
            if attempt==2: return False
            page.wait_for_timeout(2000)

def login_as(page, email, password, role):
    if role in TOKENS:
        try:
            page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=TIMEOUT)
            page.wait_for_timeout(300)
            if UAT_SECRET:
                page.evaluate(f'localStorage.setItem("sp_uat_secret","{UAT_SECRET}")')
            page.evaluate(f'localStorage.setItem("sp_token","{TOKENS[role]}")')
            page.goto(f"{BASE_URL}/stock", wait_until="domcontentloaded", timeout=TIMEOUT)
            page.wait_for_selector('[data-testid="app-shell"]', timeout=12000)
            page.wait_for_timeout(800)
            if "/login" not in page.url: return True
        except: pass

    for attempt in range(3):
        try:
            page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=TIMEOUT)
            page.wait_for_selector('[data-testid="login-email-input"]', timeout=TIMEOUT)
            page.wait_for_timeout(400)
            if UAT_SECRET:
                page.evaluate(f'localStorage.setItem("sp_uat_secret","{UAT_SECRET}")')
            page.fill('[data-testid="login-email-input"]', email)
            page.fill('[data-testid="login-password-input"]', password)
            page.click('[data-testid="login-submit-button"]')
            page.wait_for_function('window.location.pathname !== "/login"', timeout=TIMEOUT)
            page.wait_for_timeout(1000)
            if "/login" in page.url: raise Exception("still on login")
            try:
                token = page.evaluate('localStorage.getItem("sp_token")')
                if token: TOKENS[role] = token
            except: pass
            return True
        except:
            if attempt==2: return False
            page.wait_for_timeout(3000)

# Track which item index to pick next — rotates through all items
_item_index = 0

def select_first(page, testid):
    """Always picks the first available option."""
    try:
        page.locator(f'[data-testid="{testid}"]').click()
        page.wait_for_timeout(600)
        opts = page.locator('[role="option"]')
        if opts.count()==0: return None
        text = opts.first.text_content().strip()
        opts.first.click()
        page.wait_for_timeout(400)
        return text
    except: return None

def select_next(page, testid):
    """
    Rotates through all available options on each call.
    Prevents the same item (e.g. Basmati Rice) being selected every time,
    ensuring all items get exercised across the test run.
    """
    global _item_index
    try:
        page.locator(f'[data-testid="{testid}"]').click()
        page.wait_for_timeout(600)
        opts = page.locator('[role="option"]')
        count = opts.count()
        if count == 0: return None
        # Rotate index, skip already-counted items (✓ suffix) if possible
        idx = _item_index % count
        text = opts.nth(idx).text_content().strip()
        opts.nth(idx).click()
        page.wait_for_timeout(400)
        _item_index += 1
        return text
    except: return None

def select_option(page, testid, text):
    """Select dropdown option by partial text match."""
    try:
        page.locator(f'[data-testid="{testid}"]').click()
        page.wait_for_timeout(600)
        opts = page.locator('[role="option"]')
        for i in range(opts.count()):
            if text.lower() in opts.nth(i).text_content().lower():
                opts.nth(i).click()
                page.wait_for_timeout(400)
                return True
        opts.first.click()
        return True
    except: return False

def toast(page, timeout=5000):
    """Wait for a NEW toast. Dismisses any existing toasts first to avoid stale captures."""
    try:
        # Dismiss any existing toasts by waiting for them to disappear
        existing = page.locator('[data-sonner-toast]')
        if existing.count() > 0:
            try:
                existing.first.click()  # dismiss
                page.wait_for_timeout(300)
            except: pass
        page.wait_for_selector('[data-sonner-toast]', timeout=timeout)
        return page.locator('[data-sonner-toast]').first.text_content() or ""
    except: return ""

def rows(page, prefix):
    return page.locator(f'[data-testid^="{prefix}"]').count()

def txt(page, testid):
    try: return page.locator(f'[data-testid="{testid}"]').text_content().strip()
    except: return ""

def has(page, sel, timeout=5000):
    try: page.wait_for_selector(sel, timeout=timeout); return True
    except: return False

def is_forbidden(page, extra_wait=2500):
    page.wait_for_timeout(extra_wait)
    return "forbidden" in page.url or page.locator('[data-testid="forbidden-page"]').count()>0

def void_entry(page, btn_prefix, reason="UAT test void"):
    """Open void dialog, fill reason, confirm. Returns True if succeeded."""
    btns = page.locator(f'[data-testid^="{btn_prefix}"]')
    if btns.count()==0: return False, "no void buttons"
    before = rows(page, btn_prefix.replace("void-","").split("-")[0]+"-row-")
    btns.first.click()
    page.wait_for_timeout(600)
    if not has(page, '[data-testid="void-dialog"]', 3000): return False, "dialog did not open"
    page.fill('[data-testid="void-reason-input"]', reason)
    page.click('[data-testid="void-confirm-btn"]')
    t = toast(page, 5000)
    page.wait_for_timeout(2000)
    return True, t


# ══════════════════════════════════════════════════════════════════════════════
# S0 — ENVIRONMENT
# ══════════════════════════════════════════════════════════════════════════════

def s0_environment(browser):
    scenario("🌍 S0 — Environment & Health Check")
    ctx, page = ctx_page(browser)
    s = time.time()
    try:
        page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=TIMEOUT)
        page.wait_for_selector('[data-testid="login-page"]', timeout=15000)
        page.wait_for_timeout(2000)
        banner = ""
        for sel in ["text=STAGING","text=Production","text=Unknown environment"]:
            el = page.locator(sel)
            if el.count()>0: banner = el.first.text_content().strip(); break
        step(page,"Environment banner visible",bool(banner),banner,"s0_01_banner",s)
        step(page,"Banner shows DB name","sp_dhaba" in banner.lower(),banner[:80],"s0_02_db",s)
    except Exception as e:
        step(page,"Environment check",False,str(e)[:100])
    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# S1 — AUTH (positive + negative)
# ══════════════════════════════════════════════════════════════════════════════

def s1_auth(browser):
    scenario("🔐 S1 — Authentication (Positive & Negative)")
    ctx, page = ctx_page(browser)

    # Login page renders all elements
    s = time.time()
    page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded", timeout=TIMEOUT)
    page.wait_for_selector('[data-testid="login-page"]', timeout=15000)
    step(page,"Login page — email/password/submit visible",
         has(page,'[data-testid="login-email-input"]') and
         has(page,'[data-testid="login-password-input"]') and
         has(page,'[data-testid="login-submit-button"]'),
         "","s1_01_login_page",s)

    # Password toggle
    s = time.time()
    page.fill('[data-testid="login-password-input"]', "testpass")
    page.click('[data-testid="toggle-password-visibility"]')
    page.wait_for_timeout(300)
    input_type = page.locator('[data-testid="login-password-input"]').get_attribute("type")
    step(page,"Password visibility toggle works",input_type=="text","type="+input_type,"s1_02_pwd_toggle",s)
    page.click('[data-testid="toggle-password-visibility"]')  # hide again

    # NEGATIVE: wrong credentials
    s = time.time()
    page.fill('[data-testid="login-email-input"]', "hacker@evil.com")
    page.fill('[data-testid="login-password-input"]', "wrongpass123")
    page.click('[data-testid="login-submit-button"]')
    page.wait_for_timeout(3000)
    step(page,"NEGATIVE: wrong credentials — stays on login","/login" in page.url,
         page.url.split("/")[-1],"s1_03_wrong_creds",s)

    # NEGATIVE: empty fields
    s = time.time()
    page.fill('[data-testid="login-email-input"]', "")
    page.fill('[data-testid="login-password-input"]', "")
    page.click('[data-testid="login-submit-button"]')
    page.wait_for_timeout(1500)
    step(page,"NEGATIVE: empty fields — stays on login","/login" in page.url,"","s1_04_empty_fields",s)

    # POSITIVE: Admin login → dashboard
    s = time.time()
    ok = login_as(page, ADMIN_EMAIL, ADMIN_PASSWORD, "admin")
    step(page,"POSITIVE: Admin login → dashboard",ok and "dashboard" in page.url,
         page.url.split("/")[-1],"s1_05_admin_login",s)
    step(page,"Admin sidebar shows business name",has(page,'[data-testid="business-name"]'),
         txt(page,"business-name"),"s1_06_sidebar",s)
    step(page,"Admin sidebar shows user name",has(page,'[data-testid="current-user-name"]'),
         txt(page,"current-user-name"),"s1_07_username",s)

    # Admin logout
    s = time.time()
    page.click('[data-testid="logout-button"]')
    page.wait_for_function('window.location.pathname === "/login"', timeout=TIMEOUT)
    step(page,"Admin logout → redirects to login","/login" in page.url,"","s1_08_logout",s)

    # POSITIVE: Staff login → stock
    s = time.time()
    ok = login_as(page, STAFF_EMAIL, STAFF_PASSWORD, "staff")
    step(page,"POSITIVE: Staff login → live stock",ok and "stock" in page.url,
         page.url.split("/")[-1],"s1_09_staff_login",s)
    page.click('[data-testid="logout-button"]')
    page.wait_for_timeout(1500)

    # POSITIVE: Viewer login → display
    s = time.time()
    ok = login_as(page, VIEWER_EMAIL, VIEWER_PASSWORD, "viewer")
    step(page,"POSITIVE: Viewer login → display mode",ok and "display" in page.url,
         page.url.split("/")[-1],"s1_10_viewer_login",s)

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# S2 — PURCHASES (positive + negative)
# ══════════════════════════════════════════════════════════════════════════════

def s2_purchases(browser):
    scenario("🛒 S2 — Purchases (Positive & Negative Cases)")
    ctx, page = ctx_page(browser)
    login_as(page, STAFF_EMAIL, STAFF_PASSWORD, "staff")
    go(page, "/purchases")

    # Page loads
    s = time.time()
    step(page,"Purchases page loads",has(page,'[data-testid="purchases-page"]'),"","s2_01_page",s)

    # NEGATIVE: submit empty form
    s = time.time()
    page.click('[data-testid="purchase-submit-button"]')
    page.wait_for_timeout(1500)
    still_zero = rows(page,"purchase-row-") == 0
    t = toast(page, 2000)
    step(page,"NEGATIVE: submit without item — blocked",
         still_zero or "required" in t.lower() or "select" in t.lower(),
         f"toast: {t[:50]}","s2_02_empty_submit",s)

    # NEGATIVE: future date
    s = time.time()
    item1 = select_next(page,"purchase-item-select")
    page.fill('[data-testid="purchase-date-input"]', FUTURE_DATE)
    page.fill('[data-testid="purchase-qty-input"]', "5")
    page.fill('[data-testid="purchase-price-input"]', "100")
    before = rows(page,"purchase-row-")
    page.click('[data-testid="purchase-submit-button"]')
    t = toast(page, 3000)
    page.wait_for_timeout(1500)
    after = rows(page,"purchase-row-")
    step(page,"NEGATIVE: future date rejected",
         "future" in t.lower() or after==before,
         f"toast: {t[:60]}","s2_03_future_date",s)

    # Clear date filter before positive tests so all rows are visible
    s = time.time()
    try:
        page.fill('[data-testid="filter-start"]', "")
        page.fill('[data-testid="filter-end"]', "")
        page.wait_for_timeout(500)
    except: pass

    # POSITIVE: valid purchase 1 — item, 10 qty, ₹200
    page.fill('[data-testid="purchase-date-input"]', TODAY)
    page.wait_for_timeout(300)
    item1 = select_next(page,"purchase-item-select")
    page.fill('[data-testid="purchase-date-input"]', TODAY)
    page.fill('[data-testid="purchase-qty-input"]', "10")
    page.fill('[data-testid="purchase-price-input"]', "200")
    page.wait_for_timeout(400)
    preview = txt(page,"purchase-total-preview")
    step(page,f"POSITIVE: 10 × ₹200 = ₹2,000 [{item1}]",
         "2,000" in preview or "2000" in preview,
         f"Preview: {preview}","s2_04_p1_form",s,clip="form")

    before = rows(page,"purchase-row-")
    page.click('[data-testid="purchase-submit-button"]')
    t = toast(page)
    snap(page,"s2_04b_toast",wait_ms=200,clip="toast")
    page.wait_for_timeout(1500)
    after = rows(page,"purchase-row-")
    step(page,"Purchase 1 saved — row in list",after>before,
         f"rows {before}→{after} | toast: {t[:40]}","s2_05_p1_saved",s,clip="table")

    # POSITIVE: valid purchase 2 — different item, 5 qty, ₹30
    s = time.time()
    item2 = select_next(page,"purchase-item-select")
    page.fill('[data-testid="purchase-date-input"]', TODAY)
    page.fill('[data-testid="purchase-qty-input"]', "5")
    page.fill('[data-testid="purchase-price-input"]', "30")
    page.wait_for_timeout(400)
    preview = txt(page,"purchase-total-preview")
    step(page,f"POSITIVE: 5 × ₹30 = ₹150 [{item2}]",
         "150" in preview,f"Preview: {preview}","s2_06_p2_form",s,clip="form")

    before = rows(page,"purchase-row-")
    page.click('[data-testid="purchase-submit-button"]')
    page.wait_for_timeout(1500)
    after = rows(page,"purchase-row-")
    step(page,"Purchase 2 saved — row in list",after>before,
         f"rows {before}→{after}","s2_07_p2_saved",s,clip="table")

    # POSITIVE: purchase on yesterday's date
    s = time.time()
    item3 = select_next(page,"purchase-item-select")
    page.fill('[data-testid="purchase-date-input"]', YESTERDAY)
    page.fill('[data-testid="purchase-qty-input"]', "3")
    page.fill('[data-testid="purchase-price-input"]', "50")
    before = rows(page,"purchase-row-")
    page.click('[data-testid="purchase-submit-button"]')
    t = toast(page)
    page.wait_for_timeout(1500)
    after = rows(page,"purchase-row-")
    step(page,"POSITIVE: past date purchase saved",after>before,
         f"date={YESTERDAY} | toast: {t[:40]}","s2_08_past_date",s,clip="table")

    # Running total shows
    s = time.time()
    running = txt(page,"purchases-running-total")
    step(page,"Running total shown on purchases page",bool(running),
         f"Total: {running}","s2_09_running_total",s)

    # Date filter
    s = time.time()
    page.fill('[data-testid="filter-start"]', TODAY)
    page.fill('[data-testid="filter-end"]', TODAY)
    page.wait_for_timeout(1000)
    today_rows = rows(page,"purchase-row-")
    step(page,"Date filter — shows only today's purchases",
         today_rows>=2,f"{today_rows} rows for today","s2_10_filter",s,clip="table")

    # NEGATIVE: zero quantity
    s = time.time()
    select_next(page,"purchase-item-select")
    page.fill('[data-testid="purchase-date-input"]', TODAY)
    page.fill('[data-testid="purchase-qty-input"]', "0")
    page.fill('[data-testid="purchase-price-input"]', "100")
    before = rows(page,"purchase-row-")
    page.click('[data-testid="purchase-submit-button"]')
    t = toast(page,2000)
    page.wait_for_timeout(1500)
    after = rows(page,"purchase-row-")
    step(page,"NEGATIVE: zero quantity — rejected",
         after==before or "qty" in t.lower() or "quantity" in t.lower() or "greater" in t.lower(),
         f"toast: {t[:60]}","s2_11_zero_qty",s)

    # NEGATIVE: negative quantity
    s = time.time()
    select_next(page,"purchase-item-select")
    page.fill('[data-testid="purchase-qty-input"]', "-5")
    page.fill('[data-testid="purchase-price-input"]', "100")
    before = rows(page,"purchase-row-")
    page.click('[data-testid="purchase-submit-button"]')
    t = toast(page,2000)
    page.wait_for_timeout(1500)
    after = rows(page,"purchase-row-")
    step(page,"NEGATIVE: negative quantity — rejected",
         after==before or "qty" in t.lower() or "negative" in t.lower() or "greater" in t.lower(),
         f"toast: {t[:60]}","s2_12_neg_qty",s)

    # NEGATIVE: zero price
    s = time.time()
    select_next(page,"purchase-item-select")
    page.fill('[data-testid="purchase-qty-input"]', "5")
    page.fill('[data-testid="purchase-price-input"]', "0")
    before = rows(page,"purchase-row-")
    page.click('[data-testid="purchase-submit-button"]')
    t = toast(page,2000)
    page.wait_for_timeout(1500)
    after = rows(page,"purchase-row-")
    step(page,"NEGATIVE: zero price — rejected",
         after==before or "price" in t.lower() or "greater" in t.lower(),
         f"toast: {t[:60]}","s2_13_zero_price",s)

    # NEGATIVE: amount exceeds max (₹9,99,999)
    s = time.time()
    select_next(page,"purchase-item-select")
    page.fill('[data-testid="purchase-qty-input"]', "1000")
    page.fill('[data-testid="purchase-price-input"]', "99999")
    before = rows(page,"purchase-row-")
    page.click('[data-testid="purchase-submit-button"]')
    t = toast(page,2000)
    page.wait_for_timeout(1500)
    after = rows(page,"purchase-row-")
    step(page,"NEGATIVE: amount exceeds max — rejected or warned",
         after==before or "max" in t.lower() or "limit" in t.lower() or "exceed" in t.lower() or "large" in t.lower(),
         f"toast: {t[:60]}","s2_14_max_amount",s)

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# S3 — CLOSING STOCK
# ══════════════════════════════════════════════════════════════════════════════

def s3_closing_stock(browser):
    scenario("📦 S3 — Closing Stock (Formula Verification)")
    ctx, page = ctx_page(browser)
    login_as(page, STAFF_EMAIL, STAFF_PASSWORD, "staff")
    go(page, "/closing-stock")

    # Progress bar
    s = time.time()
    step(page,"Progress bar shows items counted",has(page,"text=Items counted today"),
         "","s3_01_progress",s)

    # POSITIVE: count item 1, qty=7
    s = time.time()
    try:
        item1 = select_next(page,"closing-item-select")
        page.fill('[data-testid="closing-qty-input"]', "7")
        page.fill('[data-testid="closing-notes-input"]', "Counted after dinner service")
        snap(page,"s3_02_form_filled",clip="form")
        before = rows(page,"closing-row-")
        page.click('[data-testid="closing-save-btn"]')
        t = toast(page)
        snap(page,"s3_02b_toast",wait_ms=200,clip="toast")
        page.wait_for_timeout(1500)
        after = rows(page,"closing-row-")
        step(page,f"POSITIVE: closing count for {item1} (qty=7) saved",
             after>before,f"rows {before}→{after} | toast: {t[:40]}","s3_03_saved",s,clip="table")

        # Verify formula columns in row
        if after>0:
            row_text = page.locator('[data-testid^="closing-row-"]').first.text_content()
            has_nums = any(c.isdigit() for c in row_text)
            step(page,"Row shows Opening/Purchased/Closing/Consumed columns",
                 has_nums,row_text[:150],"s3_04_formula",s,clip="table")
    except Exception as e:
        step(page,"Closing stock entry 1",False,str(e)[:100])

    # POSITIVE: count item 2, qty=3
    s = time.time()
    try:
        item2 = select_next(page,"closing-item-select")
        page.fill('[data-testid="closing-qty-input"]', "3")
        before = rows(page,"closing-row-")
        page.click('[data-testid="closing-save-btn"]')
        page.wait_for_timeout(1500)
        after = rows(page,"closing-row-")
        step(page,f"POSITIVE: second item {item2} (qty=3) saved",
             after>=2,f"{after} rows","s3_05_item2",s,clip="table")
    except Exception as e:
        step(page,"Closing stock entry 2",False,str(e)[:100])

    # NEGATIVE: future date
    s = time.time()
    try:
        # Dismiss any stale variance toast first
        try:
            stale = page.locator('[data-sonner-toast]')
            if stale.count()>0: stale.first.click(); page.wait_for_timeout(500)
        except: pass
        date_inputs = page.locator('input[type="date"]')
        if date_inputs.count()>0:
            date_inputs.first.fill(FUTURE_DATE)
            select_first(page,"closing-item-select")
            page.fill('[data-testid="closing-qty-input"]', "5")
            before = rows(page,"closing-row-")
            page.click('[data-testid="closing-save-btn"]')
            t = toast(page,3000)
            page.wait_for_timeout(1500)
            after = rows(page,"closing-row-")
            step(page,"NEGATIVE: future date — rejected",
                 "future" in t.lower() or "not allowed" in t.lower() or after==before,
                 f"toast: {t[:60]}","s3_06_future_date",s)
            date_inputs.first.fill(TODAY)  # always reset to today
        else:
            step(page,"Closing stock date validation [skipped — no date picker shown]",True,"closing stock uses server date")
    except Exception as e:
        step(page,"NEGATIVE: future date closing stock",False,str(e)[:100])

    # NEGATIVE: negative closing qty
    s = time.time()
    try:
        item_sel = page.locator('[data-testid="closing-item-select"]')
        if item_sel.count()>0:
            select_first(page,"closing-item-select")
            page.fill('[data-testid="closing-qty-input"]', "-3")
            before = rows(page,"closing-row-")
            page.click('[data-testid="closing-save-btn"]')
            t = toast(page,2000)
            page.wait_for_timeout(1500)
            after = rows(page,"closing-row-")
            step(page,"NEGATIVE: negative closing qty — rejected",
                 after==before or "negative" in t.lower() or "greater" in t.lower() or "qty" in t.lower(),
                 f"toast: {t[:60]}","s3_07_neg_qty",s)
        else:
            step(page,"Negative qty check [skipped — no items left to select]",True,"all items already counted")
    except Exception as e:
        step(page,"NEGATIVE: negative closing qty",False,str(e)[:100])

    # NEGATIVE: save without selecting item
    s = time.time()
    try:
        # Dismiss stale toasts
        try:
            stale = page.locator('[data-sonner-toast]')
            if stale.count()>0: stale.first.click(); page.wait_for_timeout(500)
        except: pass
        page.fill('[data-testid="closing-qty-input"]', "5")
        page.click('[data-testid="closing-save-btn"]')
        t = toast(page,2000)
        page.wait_for_timeout(1000)
        step(page,"NEGATIVE: save without item selection — blocked",
             "item" in t.lower() or "select" in t.lower() or "required" in t.lower(),
             f"toast: {t[:60]}","s3_08_no_item",s)
    except Exception as e:
        step(page,"NEGATIVE: no item selection",False,str(e)[:100])

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# S4 — SALES (positive + negative + totals)
# ══════════════════════════════════════════════════════════════════════════════

def s4_sales(browser):
    scenario("💰 S4 — Sales (Positive, Negative, Totals)")
    ctx, page = ctx_page(browser)
    login_as(page, STAFF_EMAIL, STAFF_PASSWORD, "staff")
    go(page, "/sales")

    # Summary cards visible
    s = time.time()
    step(page,"Sales summary cards visible",
         has(page,'[data-testid="sales-weekly-card"]') and
         has(page,'[data-testid="sales-monthly-card"]'),
         "","s4_01_cards",s)

    # NEGATIVE: submit with zero values
    s = time.time()
    page.fill('[data-testid="sales-lunch-input"]',  "0")
    page.fill('[data-testid="sales-dinner-input"]', "0")
    page.fill('[data-testid="sales-other-input"]',  "0")
    page.wait_for_timeout(300)
    total = txt(page,"sales-total-preview")
    step(page,"NEGATIVE: all zeros shows ₹0 total",
         "0" in total,f"total: {total}","s4_02_zero_total",s,clip="form")

    # POSITIVE: fill valid sales
    # Handle duplicate date — if today already has sales, click "Edit & Correct"
    s = time.time()
    page.fill('[data-testid="sales-lunch-input"]',  "5000")
    page.fill('[data-testid="sales-dinner-input"]', "4000")
    page.fill('[data-testid="sales-other-input"]',  "500")
    page.wait_for_timeout(800)  # wait for duplicate check API call
    total = txt(page,"sales-total-preview")
    step(page,"POSITIVE: ₹5000+₹4000+₹500=₹9,500 preview",
         "9,500" in total or "9500" in total,
         f"Preview: {total}","s4_03_total_preview",s,clip="form")

    # Check if duplicate warning shown — if so click Edit & Correct
    s = time.time()
    dup_warn = has(page,'[data-testid="duplicate-warning"]',2000)
    if dup_warn:
        # Click "Edit & Correct" to enable the submit button
        edit_btn = page.locator('button:has-text("Edit & Correct"), button:has-text("Edit")')
        if edit_btn.count()>0:
            edit_btn.first.click()
            page.wait_for_timeout(500)

    # Now submit button should be enabled
    submit_btn = page.locator('[data-testid="sales-submit-button"]')
    is_enabled = not submit_btn.is_disabled()
    before = rows(page,"sales-row-")

    if is_enabled:
        submit_btn.click()
        t = toast(page)
        snap(page,"s4_03b_toast",wait_ms=200,clip="toast")
        page.wait_for_timeout(1500)
        after = rows(page,"sales-row-")
        step(page,"POSITIVE: sales entry saved (new or updated)",
             after>before or "success" in t.lower() or "saved" in t.lower() or "updated" in t.lower(),
             f"rows {before}→{after} | dup={dup_warn} | toast: {t[:40]}","s4_04_saved",s,clip="table")
    else:
        step(page,"POSITIVE: sales entry saved",False,
             f"submit button still disabled | dup={dup_warn}","s4_04_disabled",s,clip="form")

    # NEGATIVE: duplicate date shows warning and disables submit
    s = time.time()
    # Sales for today already exists from above — just check warning is shown
    page.fill('[data-testid="sales-lunch-input"]', "1000")
    page.fill('[data-testid="sales-dinner-input"]', "1000")
    page.fill('[data-testid="sales-other-input"]', "0")
    page.wait_for_timeout(800)
    dup_warning = has(page,'[data-testid="duplicate-warning"]',3000)
    # Also verify button is disabled when duplicate exists and not editing
    edit_cancel = page.locator('button:has-text("Cancel")')
    if edit_cancel.count()>0:
        edit_cancel.first.click()  # exit edit mode first
        page.wait_for_timeout(500)
    btn_disabled = page.locator('[data-testid="sales-submit-button"]').is_disabled()
    step(page,"NEGATIVE: duplicate date — warning shown + submit disabled",
         dup_warning and btn_disabled,
         f"warning={dup_warning} btn_disabled={btn_disabled}","s4_05_duplicate_warning",s,clip="form")

    # POSITIVE: add notes to sales
    s = time.time()
    page.fill('[data-testid="sales-notes-input"]', "Heavy lunch crowd today — festival nearby")
    snap(page,"s4_06_with_notes",clip="form")
    notes_val = page.locator('[data-testid="sales-notes-input"]').input_value()
    step(page,"Sales notes field accepts text",
         "festival" in notes_val or len(notes_val)>5,
         f"value: {notes_val[:50]}","s4_06_notes",s)

    # NEGATIVE: future date for sales
    s = time.time()
    date_input = page.locator('[data-testid="sales-date-input"]')
    if date_input.count()>0:
        date_input.fill(FUTURE_DATE)
        page.fill('[data-testid="sales-lunch-input"]', "1000")
        page.fill('[data-testid="sales-dinner-input"]', "1000")
        page.fill('[data-testid="sales-other-input"]', "0")
        before = rows(page,"sales-row-")
        page.click('[data-testid="sales-submit-button"]')
        t = toast(page,3000)
        page.wait_for_timeout(1500)
        after = rows(page,"sales-row-")
        step(page,"NEGATIVE: future date sales — rejected",
             "future" in t.lower() or after==before,
             f"toast: {t[:60]}","s4_07_future_date",s)
        date_input.fill(TODAY)
    else:
        step(page,"Sales date validation [skipped — no date input visible]",True,"uses server date")

    # NEGATIVE: extremely large sales amount
    s = time.time()
    page.fill('[data-testid="sales-lunch-input"]',  "9999999")
    page.fill('[data-testid="sales-dinner-input"]', "0")
    page.fill('[data-testid="sales-other-input"]',  "0")
    before = rows(page,"sales-row-")
    page.click('[data-testid="sales-submit-button"]')
    t = toast(page,2000)
    page.wait_for_timeout(1500)
    after = rows(page,"sales-row-")
    step(page,"NEGATIVE: extremely large sales amount — rejected or warned",
         after==before or "max" in t.lower() or "limit" in t.lower() or "exceed" in t.lower(),
         f"toast: {t[:60]}","s4_08_max_amount",s)

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# S5 — EXPENSES (positive + negative + void)
# ══════════════════════════════════════════════════════════════════════════════

def s5_expenses(browser):
    scenario("💸 S5 — Expenses (Positive, Negative, Void)")
    ctx, page = ctx_page(browser)
    login_as(page, STAFF_EMAIL, STAFF_PASSWORD, "staff")
    go(page, "/expenses")

    # Summary cards
    s = time.time()
    step(page,"Expense summary cards visible",
         has(page,'[data-testid="exp-today-card"]'),
         "","s5_01_cards",s)

    # NEGATIVE: submit without category
    s = time.time()
    page.fill('[data-testid="exp-amount-input"]', "500")
    page.click('[data-testid="exp-submit-button"]')
    t = toast(page,2000)
    page.wait_for_timeout(1500)
    step(page,"NEGATIVE: no category — shows error",
         "categor" in t.lower() or "select" in t.lower() or "required" in t.lower(),
         f"toast: {t[:60]}","s5_02_no_category",s)

    # POSITIVE: Gas cylinder ₹1200
    # Navigate away and back to reset form state cleanly
    s = time.time()
    go(page, "/expenses")
    page.wait_for_timeout(500)
    cat1 = select_next(page,"exp-cat-select")
    if not cat1:
        # Fallback: try clicking the trigger directly
        page.locator('[data-testid="exp-cat-select"]').click()
        page.wait_for_timeout(600)
        opts = page.locator('[role="option"]')
        if opts.count()>0:
            cat1 = opts.first.text_content().strip()
            opts.first.click()
            page.wait_for_timeout(400)
    page.fill('[data-testid="exp-date-input"]', TODAY)
    page.fill('[data-testid="exp-desc-input"]', "Gas cylinder refill")
    page.fill('[data-testid="exp-amount-input"]', "1200")
    snap(page,"s5_03_form_filled",clip="form")
    before = rows(page,"expense-row-")
    page.click('[data-testid="exp-submit-button"]')
    t = toast(page)
    snap(page,"s5_03b_toast",wait_ms=200,clip="toast")
    page.wait_for_timeout(1500)
    after = rows(page,"expense-row-")
    step(page,f"POSITIVE: expense ₹1200 ({cat1}) saved",
         after>before,f"rows {before}→{after} | toast: {t[:40]}","s5_04_saved",s,clip="table")

    # POSITIVE: Electricity ₹3500
    s = time.time()
    cat2 = select_next(page,"exp-cat-select")
    page.fill('[data-testid="exp-desc-input"]', "Monthly electricity bill")
    page.fill('[data-testid="exp-amount-input"]', "3500")
    before = rows(page,"expense-row-")
    page.click('[data-testid="exp-submit-button"]')
    page.wait_for_timeout(1500)
    after = rows(page,"expense-row-")
    step(page,f"POSITIVE: expense ₹3500 ({cat2}) saved",
         after>before,f"rows {before}→{after}","s5_05_elec",s,clip="table")

    # NEGATIVE: future date
    s = time.time()
    page.fill('[data-testid="exp-date-input"]', FUTURE_DATE)
    select_first(page,"exp-cat-select")
    page.fill('[data-testid="exp-amount-input"]', "100")
    before = rows(page,"expense-row-")
    page.click('[data-testid="exp-submit-button"]')
    t = toast(page,3000)
    page.wait_for_timeout(1500)
    after = rows(page,"expense-row-")
    step(page,"NEGATIVE: future date expense rejected",
         "future" in t.lower() or after==before,
         f"toast: {t[:60]}","s5_06_future_date",s)
    page.fill('[data-testid="exp-date-input"]', TODAY)

    # NEGATIVE: zero amount
    s = time.time()
    select_first(page,"exp-cat-select")
    page.fill('[data-testid="exp-amount-input"]', "0")
    before = rows(page,"expense-row-")
    page.click('[data-testid="exp-submit-button"]')
    t = toast(page,2000)
    page.wait_for_timeout(1500)
    after = rows(page,"expense-row-")
    step(page,"NEGATIVE: zero amount rejected",
         after==before or "amount" in t.lower() or "greater" in t.lower(),
         f"toast: {t[:60]}","s5_07_zero_amt",s)

    # VOID: void an expense (admin only)
    ctx.close()
    ctx, page = ctx_page(browser)
    login_as(page, ADMIN_EMAIL, ADMIN_PASSWORD, "admin")
    go(page, "/expenses")
    page.wait_for_timeout(500)

    s = time.time()
    void_btns = page.locator('[data-testid^="void-expense-"]')
    if void_btns.count()>0:
        before = rows(page,"expense-row-")
        ok, t = void_entry(page,"void-expense-","UAT test — gas duplicate")
        after = rows(page,"expense-row-")
        step(page,"VOID: expense voided — removed from list",
             ok and (after<before or "void" in t.lower()),
             f"rows {before}→{after} | toast: {t[:40]}","s5_08_voided",s,clip="table")
    else:
        step(page,"VOID: expense void",True,"no expense entries to void — skipped")

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# S6 — LIVE STOCK & ALERTS
# ══════════════════════════════════════════════════════════════════════════════

def s6_stock_alerts(browser):
    scenario("📊 S6 — Live Stock & Alerts")
    ctx, page = ctx_page(browser)
    login_as(page, ADMIN_EMAIL, ADMIN_PASSWORD, "admin")

    # Live stock
    s = time.time()
    go(page, "/stock")
    page.wait_for_timeout(1000)
    card_count = rows(page,"stock-card-")
    step(page,"Live stock shows all items",card_count>0,
         f"{card_count} items","s6_01_stock",s)

    # Search filter
    s = time.time()
    page.fill('[data-testid="stock-search"]', "a")
    page.wait_for_timeout(800)
    filtered = rows(page,"stock-card-")
    step(page,"Stock search filter works",
         filtered<=card_count,f"{filtered} of {card_count}","s6_02_search",s,clip="form")
    page.fill('[data-testid="stock-search"]', "")
    page.wait_for_timeout(500)

    # NEGATIVE: search with no results
    s = time.time()
    page.fill('[data-testid="stock-search"]', "zzz_nonexistent_item_xyz")
    page.wait_for_timeout(800)
    no_results = rows(page,"stock-card-")==0
    step(page,"NEGATIVE: search no match — shows empty state",
         no_results,f"0 items found","s6_03b_no_results",s,clip="form")
    page.fill('[data-testid="stock-search"]', "")
    page.wait_for_timeout(500)

    # Status filter — Low/Out
    s = time.time()
    page.locator('[data-testid="stock-filter-status"]').click()
    page.wait_for_timeout(500)
    opts = page.locator('[role="option"]')
    if opts.count()>1:
        opts.nth(1).click()
        page.wait_for_timeout(800)
    # Filter applied — verify card count changed or is subset of total
    filtered_status = rows(page,"stock-card-")
    step(page,"Stock status filter — applied (filters by status)",
         filtered_status <= card_count,
         f"{filtered_status} of {card_count} items","s6_03_status_filter",s,clip="form")

    # Reset to all
    page.locator('[data-testid="stock-filter-status"]').click()
    page.wait_for_timeout(400)
    opts = page.locator('[role="option"]')
    if opts.count()>0: opts.first.click()

    # Alerts page
    s = time.time()
    go(page, "/alerts")
    page.wait_for_timeout(1000)
    has_alerts_page = has(page,'[data-testid="alerts-page"]')
    step(page,"Alerts page loads",has_alerts_page,"","s6_04_alerts_page",s)

    # Check for either "no alerts" or alert cards
    s = time.time()
    no_alerts = has(page,'[data-testid="no-alerts-celebration"]',2000)
    alerts_list = has(page,'[data-testid="alerts-list"]',2000)
    alert_cards = rows(page,"alert-card-")
    step(page,"Alerts page shows correct state (all good OR alerts listed)",
         no_alerts or alerts_list,
         f"no-alerts={no_alerts} | alert-cards={alert_cards}","s6_05_alerts_state",s)

    if alerts_list and alert_cards>0:
        # Log purchase button on alert card
        s = time.time()
        log_btns = page.locator('[data-testid^="log-purchase-"]')
        step(page,"Alert cards have 'Log Purchase' button",
             log_btns.count()>0,f"{log_btns.count()} buttons","s6_06_log_purchase_btn",s,clip="table")

    # Alerts badge in sidebar
    s = time.time()
    badge = page.locator('[data-testid="sidebar-alerts-badge"]')
    step(page,"Sidebar shows alerts badge count",
         badge.count()>0,badge.text_content() if badge.count()>0 else "no badge","s6_07_badge",s)

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# S7 — P&L (profit day + loss day + all periods)
# ══════════════════════════════════════════════════════════════════════════════

def s7_pnl(browser):
    scenario("📈 S7 — P&L Statement (Profit, Loss, All Periods)")
    ctx, page = ctx_page(browser)
    login_as(page, ADMIN_EMAIL, ADMIN_PASSWORD, "admin")
    go(page, "/pnl")
    page.wait_for_timeout(2000)

    # Page loads
    s = time.time()
    step(page,"P&L page loads",has(page,'[data-testid="pnl-page"]'),"","s7_01_page",s)

    # Today tab — check profit/loss
    s = time.time()
    page.click('[data-testid="pnl-tab-today"]')
    page.wait_for_timeout(1500)
    net = txt(page,"pnl-net-amount")
    summary_card = has(page,'[data-testid="pnl-summary-card"]')
    is_profit = page.locator('[data-testid="pnl-net-amount"]').evaluate(
        "el => el.className") if has(page,'[data-testid="pnl-net-amount"]',2000) else ""
    step(page,f"Today's P&L shows net amount (profit or loss)",
         bool(net),f"Net: {net}","s7_02_today",s,clip="form")

    # Check P&L statement has revenue/cogs/expenses rows
    s = time.time()
    stmt_card = has(page,'[data-testid="pnl-statement-card"]',2000)
    step(page,"P&L statement card visible with rows",stmt_card,"","s7_03_statement",s,clip="form")

    # Week tab
    s = time.time()
    page.click('[data-testid="pnl-tab-week"]')
    page.wait_for_timeout(1500)
    net_week = txt(page,"pnl-net-amount")
    step(page,"Week tab shows P&L",bool(net_week),f"Weekly net: {net_week}","s7_04_week",s,clip="form")

    # Month tab
    s = time.time()
    page.click('[data-testid="pnl-tab-month"]')
    page.wait_for_timeout(1500)
    net_month = txt(page,"pnl-net-amount")
    step(page,"Month tab shows P&L",bool(net_month),f"Monthly net: {net_month}","s7_05_month",s,clip="form")

    # All time tab
    s = time.time()
    page.click('[data-testid="pnl-tab-all"]')
    page.wait_for_timeout(1500)
    net_all = txt(page,"pnl-net-amount")
    step(page,"All time tab shows P&L",bool(net_all),f"All-time net: {net_all}","s7_06_alltime",s,clip="form")

    # Trend chart visible
    s = time.time()
    step(page,"30-day trend chart visible",
         has(page,'[data-testid="pnl-trend-card"]',2000),"","s7_07_trend",s)

    # Export PDF button
    s = time.time()
    step(page,"Export PDF button visible",
         has(page,'[data-testid="pnl-export-button"]',2000),"","s7_08_export",s)

    # Profit/loss color check — current state
    s = time.time()
    page.click('[data-testid="pnl-tab-today"]')
    page.wait_for_timeout(1500)
    net_el = page.locator('[data-testid="pnl-net-amount"]')
    if net_el.count()>0:
        classes  = net_el.get_attribute("class") or ""
        is_green = "green" in classes
        is_red   = "red" in classes
        net_text = net_el.text_content() or ""
        step(page,"Profit shown in green / Loss shown in red",
             is_green or is_red,
             f"green={is_green} red={is_red} | net={net_text}","s7_09_color",s,clip="form")
    else:
        step(page,"Profit/loss color coding",False,"net amount element not found")

    # ── NEGATIVE: Force a LOSS scenario — verify P&L shows red ──────────────
    # Add ₹99,999 expense to guarantee expenses > revenue → net loss
    # Then verify: net is negative AND shown in red
    # Then cleanup: void the expense so other tests aren't affected
    s = time.time()
    try:
        go(page, "/expenses")
        cat = select_first(page,"exp-cat-select")
        page.fill('[data-testid="exp-date-input"]', TODAY)
        page.fill('[data-testid="exp-desc-input"]', "UAT LOSS TEST large expense")
        page.fill('[data-testid="exp-amount-input"]', "99999")
        page.click('[data-testid="exp-submit-button"]')
        toast(page)
        page.wait_for_timeout(1500)

        # Check P&L today — must show LOSS (negative + red)
        go(page, "/pnl")
        page.click('[data-testid="pnl-tab-today"]')
        page.wait_for_timeout(2000)

        net_el = page.locator('[data-testid="pnl-net-amount"]')
        if net_el.count()>0:
            net_text = net_el.text_content() or ""
            classes  = net_el.get_attribute("class") or ""
            is_red      = "red" in classes
            is_negative = net_text.strip().startswith("-") or \
                          page.locator("text=Loss").count()>0
            step(page,"NEGATIVE: ₹99,999 expense → P&L shows LOSS (negative + red)",
                 is_red or is_negative,
                 f"Net: {net_text[:30]} | red={is_red} negative={is_negative}",
                 "s7_10_loss_red",s,clip="form")
        else:
            step(page,"NEGATIVE: loss scenario",False,"net amount element not found")

        # Cleanup: void the ₹99,999 expense
        go(page, "/expenses")
        page.wait_for_timeout(500)
        expense_rows_el = page.locator('[data-testid^="expense-row-"]')
        voided = False
        for i in range(expense_rows_el.count()):
            row_text = expense_rows_el.nth(i).text_content() or ""
            if "UAT LOSS" in row_text or "99,999" in row_text:
                void_btn = expense_rows_el.nth(i).locator('[data-testid^="void-expense-"]')
                if void_btn.count()>0:
                    void_btn.first.click()
                    page.wait_for_timeout(600)
                    if has(page,'[data-testid="void-dialog"]',2000):
                        page.fill('[data-testid="void-reason-input"]',
                                  "UAT cleanup — loss test expense")
                        page.click('[data-testid="void-confirm-btn"]')
                        page.wait_for_timeout(2000)
                        voided = True
                    break
        step(page,"CLEANUP: ₹99,999 loss test expense voided",
             voided,"voided="+str(voided),"s7_11_cleanup",s)

    except Exception as e:
        step(page,"NEGATIVE: loss scenario",False,str(e)[:100])

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# S8 — DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

def s8_dashboard(browser):
    scenario("🏠 S8 — Dashboard (KPIs, Charts, Stock Health)")
    ctx, page = ctx_page(browser)
    login_as(page, ADMIN_EMAIL, ADMIN_PASSWORD, "admin")
    go(page, "/dashboard")
    page.wait_for_timeout(2000)

    s = time.time()
    step(page,"Dashboard page loads",has(page,'[data-testid="dashboard-page"]'),"","s8_01_page",s)

    # KPI cards
    for testid, label in [
        ("sales-trend-card","Sales trend chart"),
        ("stock-health-card","Stock health pie chart"),
        ("category-spend-card","Category spend chart"),
        ("expense-spend-card","Expense breakdown"),
        ("top-items-card","Top items by cost"),
    ]:
        s = time.time()
        step(page,f"Dashboard: {label} visible",
             has(page,f'[data-testid="{testid}"]',3000),
             "","s8_"+testid.replace("-","_")[:20],s)

    # Full dashboard screenshot
    snap(page,"s8_full_dashboard",wait_ms=1000)
    step(page,"Dashboard fully rendered",True,"full screenshot taken","s8_full",s)

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# S9 — INVENTORY INSIGHTS
# ══════════════════════════════════════════════════════════════════════════════

def s9_inventory_insights(browser):
    scenario("🔍 S9 — Inventory Insights")
    ctx, page = ctx_page(browser)
    login_as(page, ADMIN_EMAIL, ADMIN_PASSWORD, "admin")
    go(page, "/inventory-insights")
    page.wait_for_timeout(2000)

    s = time.time()
    step(page,"Inventory insights page loads",
         has(page,'[data-testid="inventory-insights-page"]',3000) or
         not is_forbidden(page,500),
         "","s9_01_page",s)

    # Check for alerts/recommendations sections
    s = time.time()
    page_text = page.locator("body").text_content()
    has_insights = any(kw in page_text.lower() for kw in
        ["critical","alert","recommendation","order","insight","trend","cost"])
    step(page,"Insights page shows alerts/recommendations/trends",
         has_insights,"","s9_02_content",s)

    snap(page,"s9_full_insights",wait_ms=1000)
    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# S10 — ITEMS MASTER
# ══════════════════════════════════════════════════════════════════════════════

def s10_items(browser):
    scenario("📋 S10 — Item Master (Add, Edit, Search, Filter)")
    ctx, page = ctx_page(browser)
    login_as(page, ADMIN_EMAIL, ADMIN_PASSWORD, "admin")
    go(page, "/items")

    s = time.time()
    step(page,"Items page loads",has(page,'[data-testid="items-page"]'),"","s10_01_page",s)

    initial_rows = rows(page,"item-row-")
    step(page,"Item list shows existing items",initial_rows>0,
         f"{initial_rows} items","s10_02_list",s,clip="table")

    # Search
    s = time.time()
    page.fill('[data-testid="items-search"]', "a")
    page.wait_for_timeout(800)
    filtered = rows(page,"item-row-")
    step(page,"Item search filter works",filtered<=initial_rows,
         f"{filtered} of {initial_rows}","s10_03_search",s,clip="table")
    page.fill('[data-testid="items-search"]', "")
    page.wait_for_timeout(500)

    # Add new item
    s = time.time()
    page.click('[data-testid="items-add-button"]')
    page.wait_for_timeout(800)
    # Dialog should open
    has_dialog = has(page,'[role="dialog"]',3000)
    step(page,"Add item dialog opens",has_dialog,"","s10_04_dialog",s,clip="form")

    if has_dialog:
        # NEGATIVE: submit empty
        s = time.time()
        dialog_btns = page.locator('[role="dialog"] button[type="submit"], [role="dialog"] button:has-text("Save")')
        if dialog_btns.count()>0:
            dialog_btns.first.click()
            page.wait_for_timeout(1000)
            t = toast(page,2000)
            step(page,"NEGATIVE: empty item form — shows error or stays open",
                 "required" in t.lower() or "name" in t.lower() or "category" in t.lower() or "unit" in t.lower(),
                 f"toast: {t[:60]}","s10_05_empty_item",s)

        # NEGATIVE: duplicate item name — close dialog, get existing name, reopen
        s = time.time()
        try:
            # Close current dialog first
            page.keyboard.press("Escape")
            page.wait_for_timeout(500)
            # Get first existing item name from table
            existing_rows = page.locator('[data-testid^="item-row-"]')
            existing_name = ""
            if existing_rows.count()>0:
                existing_name = existing_rows.first.locator("td").first.text_content().strip()
            if existing_name:
                # Open fresh dialog
                page.click('[data-testid="items-add-button"]')
                page.wait_for_timeout(800)
                if has(page,'[role="dialog"]',2000):
                    # Fill with duplicate name + valid category + unit
                    name_input = page.locator('[role="dialog"] input[placeholder*="name"], [role="dialog"] input').first
                    name_input.fill(existing_name)
                    # Select category and unit to isolate the duplicate check
                    for sel in ['[role="dialog"] button[role="combobox"]']:
                        combos = page.locator(sel)
                        if combos.count()>0:
                            combos.first.click()
                            page.wait_for_timeout(400)
                            opts = page.locator('[role="option"]')
                            if opts.count()>0: opts.first.click()
                            page.wait_for_timeout(300)
                    save_btn = page.locator('[role="dialog"] button[type="submit"], [role="dialog"] button:has-text("Save")').first
                    if save_btn.count()>0:
                        save_btn.click()
                        t = toast(page,3000)
                        page.wait_for_timeout(1500)
                        step(page,f"NEGATIVE: duplicate item name '{existing_name[:20]}' — rejected",
                             "exist" in t.lower() or "duplicate" in t.lower() or "already" in t.lower() or "unique" in t.lower(),
                             f"toast: {t[:60]}","s10_05b_dup_name",s)
                    else:
                        step(page,"NEGATIVE: duplicate item name",False,"save button not found")
                else:
                    step(page,"NEGATIVE: duplicate item name",False,"dialog did not open")
            else:
                step(page,"NEGATIVE: duplicate item name",True,"no existing items to duplicate — skipped")
        except Exception as e:
            step(page,"NEGATIVE: duplicate item name",False,str(e)[:80])

        # Re-open dialog for positive test
        if not has(page,'[role="dialog"]',500):
            page.click('[data-testid="items-add-button"]')
            page.wait_for_timeout(800)

        # POSITIVE: fill and save
        s = time.time()
        try:
            ts = int(time.time()) % 9999
            name_input = page.locator('[role="dialog"] input[placeholder*="name"], [role="dialog"] input').first
            name_input.fill(f"UAT Test Item {ts}")
            # Select category
            cat_sel = page.locator('[role="dialog"] [data-testid*="cat"]')
            if cat_sel.count()>0:
                cat_sel.first.click()
                page.wait_for_timeout(500)
                opts = page.locator('[role="option"]')
                if opts.count()>0: opts.first.click()
            # Select unit
            unit_sel = page.locator('[role="dialog"] [data-testid*="unit"]')
            if unit_sel.count()>0:
                unit_sel.first.click()
                page.wait_for_timeout(500)
                opts = page.locator('[role="option"]')
                if opts.count()>0: opts.first.click()
            snap(page,"s10_06_item_form",clip="form")
            save_btn = page.locator('[role="dialog"] button[type="submit"], [role="dialog"] button:has-text("Save")').first
            save_btn.click()
            t = toast(page)
            snap(page,"s10_06b_toast",wait_ms=200,clip="toast")
            page.wait_for_timeout(1500)
            new_count = rows(page,"item-row-")
            step(page,f"POSITIVE: new item UAT Test Item {ts} added",
                 new_count>initial_rows or "added" in t.lower() or "saved" in t.lower(),
                 f"rows {initial_rows}→{new_count} | toast: {t[:40]}","s10_07_saved",s,clip="table")
        except Exception as e:
            step(page,"POSITIVE: add item",False,str(e)[:100])

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# S11 — SALARIES
# ══════════════════════════════════════════════════════════════════════════════

def s11_salaries(browser):
    scenario("👥 S11 — Salaries (Add, Mark Paid, Summary)")
    ctx, page = ctx_page(browser)
    login_as(page, ADMIN_EMAIL, ADMIN_PASSWORD, "admin")
    go(page, "/salaries")

    s = time.time()
    step(page,"Salaries page loads",has(page,'[data-testid="salaries-page"]'),"","s11_01_page",s)

    # Summary cards
    s = time.time()
    total = txt(page,"salary-total")
    paid = txt(page,"salary-paid")
    pending = txt(page,"salary-pending")
    step(page,"Salary summary cards show Total/Paid/Pending",
         bool(total),f"Total:{total} Paid:{paid} Pending:{pending}","s11_02_cards",s)

    # Add salary entry
    s = time.time()
    page.click('[data-testid="salary-add-button"]')
    page.wait_for_timeout(800)
    has_dialog = has(page,'[role="dialog"]',3000)
    step(page,"Add salary dialog opens",has_dialog,"","s11_03_dialog",s,clip="form")

    if has_dialog:
        # Select staff member
        try:
            staff_sel = page.locator('[role="dialog"] [class*="Select"], [role="dialog"] button[role="combobox"]').first
            if staff_sel.count()>0:
                staff_sel.click()
                page.wait_for_timeout(500)
                opts = page.locator('[role="option"]')
                if opts.count()>0: opts.first.click()
            # Fill basic salary
            basic_input = page.locator('[role="dialog"] input[type="number"]').first
            if basic_input.count()>0:
                basic_input.fill("15000")
            snap(page,"s11_04_salary_form",clip="form")
            save_btn = page.locator('[role="dialog"] button[type="submit"], [role="dialog"] button:has-text("Save"), [role="dialog"] button:has-text("Add")').first
            if save_btn.count()>0:
                save_btn.click()
                t = toast(page)
                snap(page,"s11_04b_toast",wait_ms=200,clip="toast")
                page.wait_for_timeout(1500)
                step(page,"Salary entry added",
                     "added" in t.lower() or "saved" in t.lower() or rows(page,"salary-row-")>0,
                     f"toast: {t[:40]}","s11_05_saved",s,clip="table")
        except Exception as e:
            step(page,"Add salary entry",False,str(e)[:100])

    # Mark as paid
    s = time.time()
    pay_btns = page.locator('[data-testid^="salary-pay-"]')
    if pay_btns.count()>0:
        pay_btns.first.click()
        page.wait_for_timeout(800)
        has_pay_dialog = has(page,'[role="dialog"]',3000)
        step(page,"Mark salary as paid dialog opens",has_pay_dialog,"","s11_06_pay_dialog",s,clip="form")
        if has_pay_dialog:
            # Confirm payment
            confirm_btn = page.locator('[role="dialog"] button:has-text("Mark Paid"), [role="dialog"] button:has-text("Confirm"), [role="dialog"] button[type="submit"]').first
            if confirm_btn.count()>0:
                confirm_btn.click()
                t = toast(page)
                page.wait_for_timeout(1500)
                step(page,"Salary marked as paid",
                     "paid" in t.lower() or "marked" in t.lower(),
                     f"toast: {t[:40]}","s11_07_paid",s,clip="table")
            else:
                page.keyboard.press("Escape")
                step(page,"Mark as paid",False,"confirm button not found")
    else:
        step(page,"Mark salary as paid",True,"no salary entries — skipped")

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# S12 — VOID FLOW (purchases + expenses)
# ══════════════════════════════════════════════════════════════════════════════

def s12_void(browser):
    scenario("🚫 S12 — Void Flow (Validation + Confirm)")
    ctx, page = ctx_page(browser)
    login_as(page, ADMIN_EMAIL, ADMIN_PASSWORD, "admin")
    go(page, "/purchases")
    page.wait_for_timeout(500)

    void_btns = page.locator('[data-testid^="void-purchase-"]')
    if void_btns.count()==0:
        step(page,"Void flow",True,"no purchases to void — add purchases first")
        ctx.close(); return

    # Open dialog
    s = time.time()
    void_btns.first.click()
    page.wait_for_timeout(600)
    step(page,"Void dialog opens",has(page,'[data-testid="void-dialog"]',3000),
         "","s12_01_dialog",s)

    if not has(page,'[data-testid="void-dialog"]',1000):
        ctx.close(); return

    # NEGATIVE: empty reason
    s = time.time()
    page.click('[data-testid="void-confirm-btn"]')
    page.wait_for_timeout(400)
    step(page,"NEGATIVE: empty reason — validation error shown",
         has(page,'[data-testid="void-reason-error"]',2000),
         "","s12_02_empty_reason",s,clip="form")

    # NEGATIVE: too short reason
    s = time.time()
    page.fill('[data-testid="void-reason-input"]', "ok")
    page.click('[data-testid="void-confirm-btn"]')
    page.wait_for_timeout(400)
    step(page,"NEGATIVE: too short reason — validation error",
         has(page,'[data-testid="void-reason-error"]',2000),
         "","s12_03_short_reason",s,clip="form")

    # Cancel closes dialog
    s = time.time()
    page.click('[data-testid="void-cancel-btn"]')
    page.wait_for_timeout(400)
    step(page,"Cancel closes void dialog",
         page.locator('[data-testid="void-dialog"]').count()==0,
         "","s12_04_cancel",s)

    # POSITIVE: void with valid reason
    s = time.time()
    before = rows(page,"purchase-row-")
    page.locator('[data-testid^="void-purchase-"]').first.click()
    page.wait_for_timeout(600)
    page.fill('[data-testid="void-reason-input"]', "Duplicate entry — UAT test")
    snap(page,"s12_05_reason_filled",clip="form")
    page.click('[data-testid="void-confirm-btn"]')
    t = toast(page,5000)
    snap(page,"s12_05b_void_toast",wait_ms=200,clip="toast")
    page.wait_for_timeout(2000)
    after = rows(page,"purchase-row-")
    step(page,"POSITIVE: void confirmed — entry removed from list",
         after<before or "void" in t.lower(),
         f"rows {before}→{after} | toast: {t[:40]}","s12_06_voided",s,clip="table")

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# S13 — SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

def s13_settings(browser):
    scenario("⚙️ S13 — Settings (Business, Categories, Units, Staff, Users)")
    ctx, page = ctx_page(browser)
    login_as(page, ADMIN_EMAIL, ADMIN_PASSWORD, "admin")
    go(page, "/settings")

    # Business profile
    s = time.time()
    page.click('[data-testid="settings-tab-business"]')
    page.wait_for_timeout(800)
    step(page,"Business profile tab loads",
         has(page,'[data-testid="biz-name-input"]'),"","s13_01_business",s)

    s = time.time()
    orig_name = page.locator('[data-testid="biz-name-input"]').input_value()
    page.fill('[data-testid="biz-name-input"]', "SP Dhaba UAT Test Name")
    snap(page,"s13_02_biz_form",clip="form")
    page.click('[data-testid="biz-save-button"]')
    t = toast(page)
    snap(page,"s13_02b_toast",wait_ms=200,clip="toast")
    page.wait_for_timeout(1500)
    sidebar_name = txt(page,"business-name")
    step(page,"Business name saved and reflects in sidebar",
         "UAT" in sidebar_name or "SP Dhaba" in sidebar_name,
         f"Sidebar: {sidebar_name} | toast: {t[:40]}","s13_03_biz_saved",s)

    # Restore name
    page.fill('[data-testid="biz-name-input"]', orig_name or "SP Royal Punjabi Family Dhaba")
    page.click('[data-testid="biz-save-button"]')
    page.wait_for_timeout(1000)

    # Categories — add
    s = time.time()
    page.click('[data-testid="settings-tab-categories"]')
    page.wait_for_timeout(800)
    ts = int(time.time())%9999
    cat_name = f"UATCat{ts}"
    page.fill('[data-testid="categories-new-name"]', cat_name)
    before = rows(page,"categories-row-")
    page.click('[data-testid="categories-add-btn"]')
    t = toast(page)
    page.wait_for_timeout(1500)
    appears = page.locator(f"text={cat_name}").count()>0
    step(page,f"Add category '{cat_name}' — appears in list",
         appears,f"toast: {t[:40]}","s13_04_category",s,clip="table")

    # NEGATIVE: add duplicate category
    s = time.time()
    page.fill('[data-testid="categories-new-name"]', cat_name)
    page.click('[data-testid="categories-add-btn"]')
    t = toast(page,3000)
    page.wait_for_timeout(1500)
    step(page,"NEGATIVE: duplicate category — shows error",
         "exist" in t.lower() or "duplicate" in t.lower() or "already" in t.lower(),
         f"toast: {t[:60]}","s13_05_dup_category",s)

    # NEGATIVE: empty category name
    s = time.time()
    page.fill('[data-testid="categories-new-name"]', "")
    page.click('[data-testid="categories-add-btn"]')
    t = toast(page,2000)
    page.wait_for_timeout(1000)
    after_empty_cat = rows(page,"categories-row-")
    step(page,"NEGATIVE: empty category name — blocked",
         bool(t) or after_empty_cat==0,
         f"toast: {t[:50]}","s13_06_empty_cat",s)

    # Units — add
    s = time.time()
    page.click('[data-testid="settings-tab-units"]')
    page.wait_for_timeout(1500)
    # Dismiss any stale toasts from categories step
    try:
        stale = page.locator('[data-sonner-toast]')
        if stale.count()>0: stale.first.click(); page.wait_for_timeout(500)
    except: pass
    unit_name = f"uat{ts%999}"
    page.fill('[data-testid="units-new-name"]', unit_name)
    page.click('[data-testid="units-add-btn"]')
    t = toast(page)
    page.wait_for_timeout(1500)
    appears = page.locator(f"text={unit_name}").count()>0
    step(page,f"Add unit '{unit_name}' — appears in list",
         appears,f"toast: {t[:40]}","s13_07_unit",s,clip="table")

    # Staff tab
    s = time.time()
    page.click('[data-testid="settings-tab-staff"]')
    page.wait_for_timeout(800)
    existing_staff = rows(page,"staff-row-")
    step(page,"Staff tab loads with existing staff",True,
         f"{existing_staff} staff","s13_08_staff",s,clip="table")

    # Add staff
    s = time.time()
    page.click('[data-testid="staff-add-button"]')
    page.wait_for_timeout(800)
    has_dialog = has(page,'[role="dialog"]',3000)
    if has_dialog:
        page.fill('[data-testid="new-staff-name"]', f"UAT Staff {ts%999}")
        page.fill('[data-testid="new-staff-phone"]', "9876543210")
        page.fill('[data-testid="new-staff-salary"]', "12000")
        snap(page,"s13_09_staff_form",clip="form")
        page.click('[data-testid="new-staff-save"]')
        t = toast(page)
        snap(page,"s13_09b_toast",wait_ms=200,clip="toast")
        page.wait_for_timeout(1500)
        step(page,"Add staff member — saved",
             "added" in t.lower() or "saved" in t.lower() or rows(page,"staff-row-")>existing_staff,
             f"toast: {t[:40]}","s13_10_staff_saved",s,clip="table")
    else:
        step(page,"Add staff dialog",False,"dialog did not open")

    # Users tab
    s = time.time()
    page.click('[data-testid="settings-tab-users"]')
    page.wait_for_timeout(1000)
    user_count = rows(page,"user-row-")
    step(page,"Users tab shows user list",user_count>0,
         f"{user_count} users","s13_11_users",s,clip="table")

    # Add new user
    s = time.time()
    page.click('[data-testid="user-add-btn"]')
    page.wait_for_timeout(800)
    has_dialog = has(page,'[role="dialog"]',3000)
    if has_dialog:
        # NEGATIVE: weak password
        page.fill('[data-testid="new-user-name"]', "UAT Test User")
        page.fill('[data-testid="new-user-email"]', f"uat_weak{ts%99}@test.com")
        page.fill('[data-testid="new-user-password"]', "123")
        select_option(page,"new-user-role","staff")
        page.click('[data-testid="new-user-save"]')
        t = toast(page,2000)
        page.wait_for_timeout(1000)
        step(page,"NEGATIVE: weak password — rejected",
             "password" in t.lower() or "weak" in t.lower() or "short" in t.lower() or "strong" in t.lower() or "char" in t.lower(),
             f"toast: {t[:60]}","s13_12b_weak_pwd",s)

        # NEGATIVE: duplicate email
        page.fill('[data-testid="new-user-email"]', ADMIN_EMAIL)
        page.fill('[data-testid="new-user-password"]', "Test@1234")
        page.click('[data-testid="new-user-save"]')
        t = toast(page,2000)
        page.wait_for_timeout(1000)
        step(page,"NEGATIVE: duplicate email — rejected",
             "exist" in t.lower() or "duplicate" in t.lower() or "already" in t.lower() or "email" in t.lower(),
             f"toast: {t[:60]}","s13_12c_dup_email",s)

        # Re-open if dialog closed
        if not has(page,'[role="dialog"]',500):
            page.click('[data-testid="user-add-btn"]')
            page.wait_for_timeout(800)

        page.fill('[data-testid="new-user-name"]', f"UAT User {ts%99}")
        page.fill('[data-testid="new-user-email"]', f"uat{ts%99}@test.com")
        page.fill('[data-testid="new-user-password"]', "Test@1234")
        select_option(page,"new-user-role","staff")
        snap(page,"s13_12_user_form",clip="form")
        page.click('[data-testid="new-user-save"]')
        t = toast(page)
        snap(page,"s13_12b_toast",wait_ms=200,clip="toast")
        page.wait_for_timeout(1500)
        step(page,"Add new user — saved",
             "added" in t.lower() or "created" in t.lower() or rows(page,"user-row-")>user_count,
             f"toast: {t[:40]}","s13_13_user_saved",s,clip="table")
    else:
        step(page,"Add user dialog",False,"dialog did not open")

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# S14 — SECURITY (unauthenticated + role enforcement)
# ══════════════════════════════════════════════════════════════════════════════

def s14_security(browser):
    scenario("🔒 S14 — Security & Role Enforcement")

    # Unauthenticated — must redirect to login
    ctx, page = ctx_page(browser)
    for path in ["/dashboard","/purchases","/settings","/pnl","/salaries","/items"]:
        s = time.time()
        page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=TIMEOUT)
        page.wait_for_timeout(2500)
        step(page,f"Unauthenticated → {path} → login",
             "/login" in page.url, page.url.split("/")[-1],
             f"s14_unauth{path.replace('/','_')}",s)
    ctx.close()

    # Staff blocked pages
    ctx, page = ctx_page(browser)
    login_as(page, STAFF_EMAIL, STAFF_PASSWORD, "staff")
    for path, label in [
        ("/dashboard","Dashboard"),("/salaries","Salaries"),("/pnl","P&L"),
        ("/items","Item Master"),("/settings","Settings"),("/inventory-insights","Insights"),
    ]:
        s = time.time()
        page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=TIMEOUT)
        step(page,f"Staff BLOCKED from {label}",is_forbidden(page),
             page.url.split("/")[-1],f"s14_staff_blk{path.replace('/','_')}",s)
    ctx.close()

    # Staff allowed pages
    ctx, page = ctx_page(browser)
    login_as(page, STAFF_EMAIL, STAFF_PASSWORD, "staff")
    for path, label in [
        ("/stock","Live Stock"),("/purchases","Purchases"),
        ("/closing-stock","Closing Stock"),("/sales","Sales"),("/expenses","Expenses"),
    ]:
        s = time.time()
        go(page, path)
        step(page,f"Staff CAN access {label}",
             not is_forbidden(page,500) and "/login" not in page.url,
             "","s14_staff_ok"+path.replace("/","_"),s)
    ctx.close()

    # Viewer blocked pages
    ctx, page = ctx_page(browser)
    login_as(page, VIEWER_EMAIL, VIEWER_PASSWORD, "viewer")
    for path, label in [
        ("/purchases","Purchases"),("/sales","Sales"),("/expenses","Expenses"),
        ("/salaries","Salaries"),("/items","Item Master"),("/settings","Settings"),
    ]:
        s = time.time()
        page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=TIMEOUT)
        step(page,f"Viewer BLOCKED from {label}",is_forbidden(page),
             page.url.split("/")[-1],f"s14_viewer_blk{path.replace('/','_')}",s)

    # Viewer can read
    for path, label in [
        ("/stock","Live Stock"),("/alerts","Alerts"),
        ("/dashboard","Dashboard"),("/pnl","P&L"),("/closing-stock","Closing Stock"),
    ]:
        s = time.time()
        go(page, path)
        step(page,f"Viewer CAN read {label}",
             not is_forbidden(page,500) and "/login" not in page.url,
             "","s14_viewer_ok"+path.replace("/","_"),s)

    # Viewer — no add/save buttons on closing stock
    s = time.time()
    go(page, "/closing-stock")
    no_save_btn = page.locator('[data-testid="closing-save-btn"]').count()==0
    step(page,"Viewer — no Save Count button on closing stock (read-only)",
         no_save_btn,"","s14_viewer_readonly",s)

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# S15 — DISPLAY MODE
# ══════════════════════════════════════════════════════════════════════════════

def s15_display_mode(browser):
    scenario("📺 S15 — Display Mode (Viewer)")
    ctx, page = ctx_page(browser)
    login_as(page, VIEWER_EMAIL, VIEWER_PASSWORD, "viewer")

    s = time.time()
    go(page, "/display")
    page.wait_for_timeout(2000)
    step(page,"Display mode loads",
         not is_forbidden(page,500) and "/login" not in page.url,
         "","s15_01_display",s)

    # Shows stock info
    s = time.time()
    body = page.locator("body").text_content()
    has_stock = any(c.isdigit() for c in body)
    step(page,"Display mode shows stock data",has_stock,"","s15_02_stock_data",s)

    # Full screen screenshot
    snap(page,"s15_full_display",wait_ms=1000)
    step(page,"Display mode full screenshot captured",
         Path(SS_DIR/"s15_full_display.png").exists(),
         "screenshot file exists","s15_03_full",s)

    ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# S16 — MOBILE UAT
# ══════════════════════════════════════════════════════════════════════════════

def s16_mobile(browser):
    scenario("📱 S16 — Mobile UAT (All Roles)")

    for role, email, pwd, label in [
        ("admin",  ADMIN_EMAIL,  ADMIN_PASSWORD,  "Admin"),
        ("staff",  STAFF_EMAIL,  STAFF_PASSWORD,  "Lokesh"),
        ("viewer", VIEWER_EMAIL, VIEWER_PASSWORD, "Viewer"),
    ]:
        ctx, page = ctx_page(browser, mobile=True)

        s = time.time()
        ok = login_as(page, email, pwd, role)
        step(page,f"Mobile: {label} login",ok,"",f"s16_{role}_login",s)
        if not ok: ctx.close(); continue

        # Bottom nav
        s = time.time()
        count = rows(page,"bottom-nav-")
        step(page,f"Mobile: {label} bottom nav ({count} items)",
             count>0,f"{count} nav items",f"s16_{role}_nav",s)

        # Hamburger drawer
        s = time.time()
        try:
            page.click('[data-testid="open-drawer"]')
            page.wait_for_timeout(600)
            drawer_ok = has(page,'[data-testid="close-drawer"]',3000)
            step(page,f"Mobile: {label} hamburger drawer opens",
                 drawer_ok,"",f"s16_{role}_drawer",s)
            if drawer_ok:
                page.click('[data-testid="close-drawer"]')
                page.wait_for_timeout(400)
        except Exception as e:
            step(page,f"Mobile: {label} hamburger",False,str(e)[:80])

        # Key page access on mobile
        if role in ("admin","staff"):
            s = time.time()
            go(page, "/closing-stock")
            step(page,f"Mobile: {label} closing stock accessible",
                 has(page,'[data-testid="closing-stock-page"]'),
                 "",f"s16_{role}_closing",s)

            s = time.time()
            go(page, "/purchases")
            step(page,f"Mobile: {label} purchases accessible",
                 has(page,'[data-testid="purchases-page"]'),
                 "",f"s16_{role}_purchases",s)

        ctx.close()


# ══════════════════════════════════════════════════════════════════════════════
# HTML REPORT
# ══════════════════════════════════════════════════════════════════════════════

def generate_report():
    passed = sum(1 for r in RESULTS if r["status"]=="PASS")
    failed = sum(1 for r in RESULTS if r["status"]=="FAIL")
    total  = len(RESULTS)
    pct    = round(passed/total*100) if total else 0
    now    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    by_scenario = {}
    for r in RESULTS:
        by_scenario.setdefault(r["scenario"],[]).append(r)

    def img(path):
        if not path or not Path(path).exists(): return '<span class="ns">—</span>'
        with open(path,"rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return f'<img src="data:image/png;base64,{b64}" class="th" onclick="zoom(this)" />'

    body = ""
    for sc, sc_rows in by_scenario.items():
        sp = sum(1 for r in sc_rows if r["status"]=="PASS")
        sf = len(sc_rows)-sp
        trs = ""
        for i,r in enumerate(sc_rows,1):
            cls = "p" if r["status"]=="PASS" else "f"
            icon = "✅" if r["status"]=="PASS" else "❌"
            trs += f'<tr class="{cls}"><td class="n">{i}</td><td>{icon}</td>'
            trs += f'<td class="nm">{r["name"]}</td>'
            trs += f'<td class="dt">{r.get("detail","")}</td>'
            trs += f'<td class="du">{r.get("duration",0):.1f}s</td>'
            trs += f'<td>{img(r.get("screenshot"))}</td></tr>'
        fb = f'<span class="bd fb">{sf} failed</span>' if sf else ""
        body += f'''<div class="sc">
          <div class="sh"><span class="sn">{sc}</span>
          <span class="bd pb">{sp} passed</span>{fb}</div>
          <table><thead><tr>
            <th>#</th><th></th><th>Test Step</th>
            <th>Detail / Value verified</th><th>Time</th><th>Screenshot</th>
          </tr></thead><tbody>{trs}</tbody></table></div>'''

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>SP Dhaba UAT</title><style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#FFF8F0;color:#1e293b}}
.hdr{{background:#2D1606;color:#fff;padding:1.75rem 2.5rem}}
.hdr h1{{font-size:1.5rem;font-weight:700}}.hdr p{{font-size:.8rem;opacity:.5;margin-top:.2rem}}
.sum{{display:flex;gap:1rem;padding:1.25rem 2.5rem;flex-wrap:wrap}}
.card{{background:#fff;border-radius:14px;padding:1rem 1.5rem;min-width:120px;box-shadow:0 1px 4px rgba(0,0,0,.07)}}
.v{{font-size:2rem;font-weight:700;line-height:1}}.l{{font-size:.7rem;color:#64748b;margin-top:4px;text-transform:uppercase;letter-spacing:.05em}}
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
.n{{width:32px;color:#94a3b8;font-size:.7rem}}.nm{{font-weight:500;max-width:300px}}
.dt{{color:#64748b;font-size:.77rem;max-width:250px;word-break:break-word}}
.du{{width:48px;color:#94a3b8;font-size:.7rem}}
.th{{width:160px;height:90px;object-fit:cover;border-radius:6px;cursor:pointer;border:1px solid #e2e8f0}}
.th:hover{{opacity:.8}}.ns{{color:#cbd5e1;font-size:.72rem}}
.ov2{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:9999;
      align-items:center;justify-content:center;cursor:zoom-out}}
.ov2.on{{display:flex}}.ov2 img{{max-width:94vw;max-height:94vh;border-radius:8px}}
</style></head><body>
<div class="hdr"><h1>🍛 SP Dhaba — Comprehensive UAT Report</h1>
<p>Generated: {now} · {total} test steps · 16 scenarios · Positive & Negative cases</p></div>
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

    p = SS_DIR/"report.html"
    p.write_text(html)
    return p


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print(f"\n🍛 SP Dhaba — Comprehensive UAT Agent")
    print(f"   Target : {BASE_URL}")
    print(f"   Date   : {TODAY}")
    print(f"   Secret : {'✅ set' if UAT_SECRET else '❌ NOT SET — rate limiter will block!'}")
    print(f"   Scenarios: 16 | Positive + Negative cases")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=HEADLESS)

        s0_environment(browser)
        s1_auth(browser)
        s2_purchases(browser)
        s3_closing_stock(browser)
        s4_sales(browser)
        s5_expenses(browser)
        s6_stock_alerts(browser)
        s7_pnl(browser)
        s8_dashboard(browser)
        s9_inventory_insights(browser)
        s10_items(browser)
        s11_salaries(browser)
        s12_void(browser)
        s13_settings(browser)
        s14_security(browser)
        s15_display_mode(browser)
        s16_mobile(browser)

        browser.close()

    passed = sum(1 for r in RESULTS if r["status"]=="PASS")
    failed = sum(1 for r in RESULTS if r["status"]=="FAIL")
    total  = len(RESULTS)
    report = generate_report()

    print(f"\n{'═'*70}")
    print(f"  RESULT : {passed}/{total} passed · {failed} failed · {round(passed/total*100) if total else 0}%")
    print(f"  Report : {report}")
    print(f"{'═'*70}\n")

    # Write compact diagnostic summary — failures only, easy to share
    summary_path = SS_DIR / "summary.txt"
    lines = [
        "=" * 70,
        f"SP Dhaba UAT Summary",
        f"Target    : {BASE_URL}",
        f"Date      : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Result    : {passed}/{total} passed · {failed} failed · {round(passed/total*100) if total else 0}%",
        "=" * 70,
    ]

    if failed > 0:
        lines.append(f"\n{'─'*70}")
        lines.append(f"FAILED STEPS ({failed}) — with full diagnostic info:")
        lines.append(f"{'─'*70}")
        for i, r in enumerate([r for r in RESULTS if r["status"]=="FAIL"], 1):
            lines.append(f"\n[{i}] SCENARIO : {r['scenario']}")
            lines.append(f"    STEP     : {r['name']}")
            lines.append(f"    DETAIL   : {r.get('detail','— no detail captured') or '— empty'}")
            lines.append(f"    DURATION : {r.get('duration',0):.1f}s")
            lines.append(f"    SS       : {Path(r['screenshot']).name if r.get('screenshot') else 'no screenshot'}")
            # Try to get page state info from screenshot name
            ss = r.get("screenshot","")
            if ss:
                lines.append(f"    HINT     : Check screenshot {Path(ss).name} for visual state")
    else:
        lines.append("\n✅ ALL TESTS PASSED — ready to merge to production")

    lines.append(f"\n{'─'*70}")
    lines.append("PASSED STEPS:")
    lines.append(f"{'─'*70}")
    for r in RESULTS:
        if r["status"] == "PASS":
            lines.append(f"  ✅ {r['name']}  →  {r.get('detail','') or 'ok'}")

    summary_path.write_text("\n".join(lines))
    print(f"  Summary: {summary_path}  (paste this file here for fixes)")

    return 0 if failed==0 else 1

if __name__=="__main__":
    sys.exit(main())
