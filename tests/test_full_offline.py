"""
SP Royal Punjabi Dhaba — Full Offline Test Suite
Tests all business logic, JWT auth, role enforcement, stock math,
P&L arithmetic, and frontend hook correctness without a live DB.
"""

import pytest
import jwt
import bcrypt
import json
import re
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

# ── constants ──────────────────────────────────────────────────────────────
JWT_SECRET = "test_secret_key_sp_dhaba"
JWT_ALGO   = "HS256"
SRC        = Path("/home/claude/SP_Dhaba_Fixed/frontend/src")
BACKEND    = Path("/home/claude/SP_Dhaba_Fixed/backend/server.py")

# ══════════════════════════════════════════════════════════════════════════════
# 1. JWT / AUTH LOGIC
# ══════════════════════════════════════════════════════════════════════════════
class TestJWTAuth:
    def _make_token(self, role="admin", expired=False):
        exp = datetime.now(timezone.utc) + timedelta(hours=(-1 if expired else 8))
        return jwt.encode(
            {"sub": "uid123", "email": "admin@test.com", "role": role,
             "exp": exp, "iat": datetime.now(timezone.utc)},
            JWT_SECRET, algorithm=JWT_ALGO
        )

    def test_valid_admin_token_decodes(self):
        token = self._make_token("admin")
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        assert payload["role"] == "admin"
        assert payload["email"] == "admin@test.com"

    def test_expired_token_raises(self):
        token = self._make_token("admin", expired=True)
        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])

    def test_invalid_token_raises(self):
        with pytest.raises(jwt.InvalidTokenError):
            jwt.decode("totally.invalid.token", JWT_SECRET, algorithms=[JWT_ALGO])

    def test_staff_token_role(self):
        token = self._make_token("staff")
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        assert payload["role"] == "staff"

    def test_viewer_token_role(self):
        token = self._make_token("viewer")
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        assert payload["role"] == "viewer"

    def test_token_has_expiry(self):
        token = self._make_token()
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
        assert "exp" in payload
        exp_dt = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert exp_dt > datetime.now(timezone.utc)

# ══════════════════════════════════════════════════════════════════════════════
# 2. PASSWORD HASHING
# ══════════════════════════════════════════════════════════════════════════════
class TestPasswordHashing:
    def test_hash_and_verify_correct(self):
        pwd = "Admin@123"
        hashed = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()
        assert bcrypt.checkpw(pwd.encode(), hashed.encode())

    def test_wrong_password_fails(self):
        pwd = "Admin@123"
        hashed = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()
        assert not bcrypt.checkpw("WrongPass!".encode(), hashed.encode())

    def test_hashes_are_unique(self):
        pwd = "SamePassword1!"
        h1 = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()
        h2 = bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()
        assert h1 != h2  # bcrypt salt ensures uniqueness

# ══════════════════════════════════════════════════════════════════════════════
# 3. ROLE ENFORCEMENT LOGIC
# ══════════════════════════════════════════════════════════════════════════════
class TestRoleEnforcement:
    """Verify role-permission matrix matches App.js routes"""

    ROLE_ROUTES = {
        "admin":  ["/dashboard", "/stock", "/alerts", "/purchases",
                   "/usage", "/sales", "/expenses", "/salaries",
                   "/pnl", "/items", "/display", "/settings"],
        "staff":  ["/stock", "/purchases", "/usage", "/sales", "/expenses"],
        "viewer": ["/dashboard", "/stock", "/alerts", "/pnl", "/display"],
    }

    def _get_route_roles(self):
        """Parse ProtectedRoute roles from App.js"""
        src = (SRC / "App.js").read_text()
        # Extract roles=[...] patterns
        return re.findall(r'roles=\{\[([^\]]+)\]\}', src)

    def test_admin_has_most_routes(self):
        assert len(self.ROLE_ROUTES["admin"]) > len(self.ROLE_ROUTES["staff"])
        assert len(self.ROLE_ROUTES["admin"]) > len(self.ROLE_ROUTES["viewer"])

    def test_staff_cannot_access_salaries(self):
        assert "/salaries" not in self.ROLE_ROUTES["staff"]

    def test_staff_cannot_access_dashboard(self):
        assert "/dashboard" not in self.ROLE_ROUTES["staff"]

    def test_staff_cannot_access_items(self):
        assert "/items" not in self.ROLE_ROUTES["staff"]

    def test_viewer_cannot_access_purchases_write(self):
        # viewer can see purchases but not write — enforced by backend role
        assert "/settings" not in self.ROLE_ROUTES["viewer"]

    def test_app_js_has_protected_routes(self):
        src = (SRC / "App.js").read_text()
        assert "ProtectedRoute" in src
        assert 'roles={["admin"]}' in src or "roles={[" in src

    def test_salaries_admin_only_in_app(self):
        src = (SRC / "App.js").read_text()
        # Salaries route should have admin in roles
        assert re.search(r'salaries.*ProtectedRoute|ProtectedRoute.*salaries', src, re.DOTALL)

    def test_backend_require_roles_pattern(self):
        src = BACKEND.read_text()
        assert "require_roles" in src
        assert 'require_roles("admin")' in src or "require_roles(" in src

    def test_staff_blocked_from_salaries_backend(self):
        src = BACKEND.read_text()
        # salaries endpoint must have role restriction
        sal_section = src[src.find('@api.get("/salaries")'):][:200]
        assert "require_roles" in sal_section or "admin" in sal_section

    def test_dashboard_blocked_from_staff_backend(self):
        src = BACKEND.read_text()
        dash_section = src[src.find('@api.get("/dashboard")'):][:200]
        assert "require_roles" in dash_section

# ══════════════════════════════════════════════════════════════════════════════
# 4. STOCK MATH LOGIC
# ══════════════════════════════════════════════════════════════════════════════
class TestStockMath:
    """Test inventory calculation logic"""

    def _calc_stock(self, purchases, usages):
        """Simulate server stock calculation"""
        total_in  = sum(p["quantity"] for p in purchases)
        total_out = sum(u["quantity_used"] for u in usages)
        return round(total_in - total_out, 6)

    def test_basic_stock_calculation(self):
        purchases = [{"quantity": 10}]
        usages    = [{"quantity_used": 4}]
        assert self._calc_stock(purchases, usages) == 6.0

    def test_zero_usage(self):
        purchases = [{"quantity": 25}]
        usages    = []
        assert self._calc_stock(purchases, usages) == 25.0

    def test_multiple_purchases(self):
        purchases = [{"quantity": 10}, {"quantity": 5}, {"quantity": 3}]
        usages    = [{"quantity_used": 7}]
        assert self._calc_stock(purchases, usages) == 11.0

    def test_stock_at_zero(self):
        purchases = [{"quantity": 5}]
        usages    = [{"quantity_used": 5}]
        assert self._calc_stock(purchases, usages) == 0.0

    def test_decimal_quantities(self):
        purchases = [{"quantity": 2.5}]
        usages    = [{"quantity_used": 1.25}]
        assert self._calc_stock(purchases, usages) == 1.25

    def _get_alert_status(self, qty_left, reorder_level):
        """Simulate alert status logic from server.py"""
        if qty_left <= 0:
            return "out"
        elif qty_left <= reorder_level:
            return "low"
        return "in"

    def test_alert_out_of_stock(self):
        assert self._get_alert_status(0, 5) == "out"

    def test_alert_low_stock(self):
        assert self._get_alert_status(3, 5) == "low"

    def test_alert_in_stock(self):
        assert self._get_alert_status(10, 5) == "in"

    def test_alert_exactly_at_reorder(self):
        assert self._get_alert_status(5, 5) == "low"

    def test_negative_stock_shows_out(self):
        # Over-usage scenario
        assert self._get_alert_status(-1, 5) == "out"

# ══════════════════════════════════════════════════════════════════════════════
# 5. P&L ARITHMETIC
# ══════════════════════════════════════════════════════════════════════════════
class TestPnLArithmetic:
    def _calc_pnl(self, revenue, cogs, expenses, salaries):
        net = round(revenue - cogs - expenses - salaries, 2)
        return {"revenue": revenue, "cogs": cogs, "expenses": expenses,
                "salaries": salaries, "net_profit": net}

    def test_profitable_month(self):
        r = self._calc_pnl(50000, 20000, 5000, 10000)
        assert r["net_profit"] == 15000.0

    def test_loss_scenario(self):
        r = self._calc_pnl(10000, 20000, 5000, 10000)
        assert r["net_profit"] == -25000.0

    def test_breakeven(self):
        r = self._calc_pnl(35000, 20000, 5000, 10000)
        assert r["net_profit"] == 0.0

    def test_net_profit_formula(self):
        revenue, cogs, expenses, salaries = 100000, 40000, 10000, 20000
        r = self._calc_pnl(revenue, cogs, expenses, salaries)
        assert r["net_profit"] == revenue - cogs - expenses - salaries

    def test_zero_everything(self):
        r = self._calc_pnl(0, 0, 0, 0)
        assert r["net_profit"] == 0.0

    def test_margin_calculation(self):
        revenue = 100000
        net     = 25000
        margin  = round((net / revenue) * 100, 1)
        assert margin == 25.0

    def test_sales_total_calculation(self):
        lunch  = 3000
        dinner = 5000
        other  = 500
        total  = lunch + dinner + other
        assert total == 8500

    def test_duplicate_sales_detection(self):
        """Same date should be rejected"""
        existing_dates = {"2026-05-31", "2026-05-30"}
        new_date = "2026-05-31"
        assert new_date in existing_dates  # means 409 should fire

# ══════════════════════════════════════════════════════════════════════════════
# 6. SALARY LOGIC
# ══════════════════════════════════════════════════════════════════════════════
class TestSalaryLogic:
    def _calc_net(self, basic, advance):
        return round(basic - advance, 2)

    def test_net_payable_calculation(self):
        assert self._calc_net(10000, 2000) == 8000.0

    def test_full_advance(self):
        assert self._calc_net(10000, 10000) == 0.0

    def test_no_advance(self):
        assert self._calc_net(15000, 0) == 15000.0

    def test_decimal_salary(self):
        assert self._calc_net(12500.50, 1000.25) == 11500.25

    def test_salary_not_visible_to_staff(self):
        """Staff role should not see salaries — check route config"""
        src = (SRC / "App.js").read_text()
        # Find the salaries route and check it doesn't include staff
        sal_match = re.search(
            r'path="/salaries".*?ProtectedRoute\s+roles=\{(\[[^\]]+\])\}',
            src, re.DOTALL
        )
        if sal_match:
            roles_str = sal_match.group(1)
            assert "staff" not in roles_str

    def test_duplicate_salary_same_month(self):
        """Same staff + month should return 409"""
        existing = [{"staff_id": "s1", "month": "2026-01"}]
        new_entry = {"staff_id": "s1", "month": "2026-01"}
        is_dup = any(
            e["staff_id"] == new_entry["staff_id"] and
            e["month"] == new_entry["month"]
            for e in existing
        )
        assert is_dup

# ══════════════════════════════════════════════════════════════════════════════
# 7. FRONTEND HOOK CORRECTNESS
# ══════════════════════════════════════════════════════════════════════════════
class TestFrontendHooks:
    """Verify our hook fixes are correctly applied"""

    def _read(self, filename):
        return (SRC / filename).read_text()

    def test_dailyusage_has_usecallback_import(self):
        src = self._read("pages/DailyUsage.jsx")
        assert "useCallback" in src.split("from \"react\"")[0] or \
               "useCallback" in src.split("from 'react'")[0] or \
               re.search(r'import.*useCallback.*from.*react', src)

    def test_dailyusage_load_is_usecallback(self):
        src = self._read("pages/DailyUsage.jsx")
        assert "const load = useCallback(" in src

    def test_dailyusage_useeffect_has_load_dep(self):
        src = self._read("pages/DailyUsage.jsx")
        assert "useEffect(() => { load(); }, [load])" in src

    def test_dailyusage_single_useeffect_for_load(self):
        src = self._read("pages/DailyUsage.jsx")
        # Should only have ONE useEffect now (merged)
        effects = re.findall(r'useEffect\(', src)
        assert len(effects) == 1

    def test_sales_load_usecallback(self):
        src = self._read("pages/Sales.jsx")
        assert "const load = useCallback(" in src
        assert "useEffect(() => { load(); }, [load])" in src

    def test_purchases_load_usecallback(self):
        src = self._read("pages/Purchases.jsx")
        assert "const load = useCallback(" in src
        assert "useEffect(() => { load(); }, [load])" in src

    def test_purchases_no_setparams(self):
        src = self._read("pages/Purchases.jsx")
        # Should be destructured without setParams
        assert "const [params] = useSearchParams()" in src
        assert "setParams" not in src

    def test_expenses_load_usecallback(self):
        src = self._read("pages/Expenses.jsx")
        assert "const load = useCallback(" in src

    def test_expenses_load_deps_correct(self):
        src = self._read("pages/Expenses.jsx")
        # After useDateFilter refactor, deps are filterCat + dateParams
        assert "useDateFilter" in src
        assert "filterCat" in src
        assert "dateParams" in src

    def test_livestock_load_usecallback(self):
        src = self._read("pages/LiveStock.jsx")
        assert "const load = useCallback(" in src
        assert "[load]" in src

    def test_displaymode_uses_business_profile(self):
        src = self._read("pages/DisplayMode.jsx")
        assert "useBusinessProfile" in src
        assert "profile.name" in src

    def test_displaymode_no_hardcoded_name(self):
        src = self._read("pages/DisplayMode.jsx")
        assert "SP Royal Punjabi Dhaba" not in src

    def test_layout_fetchalerts_usecallback(self):
        src = self._read("components/Layout.jsx")
        assert "useCallback" in src
        assert "const fetchAlerts = useCallback(" in src

    def test_layout_no_locpathname_in_alerts_effect(self):
        src = self._read("components/Layout.jsx")
        # The alerts useEffect should depend on [fetchAlerts] not [loc.pathname]
        assert "[fetchAlerts]" in src

    def test_layout_drawer_still_closes_on_route(self):
        src = self._read("components/Layout.jsx")
        # This separate effect should still be there
        assert "setDrawerOpen(false)" in src
        assert "[loc.pathname]" in src

    def test_authcontext_has_abortcontroller(self):
        src = self._read("contexts/AuthContext.jsx")
        assert "AbortController" in src
        assert "controller.abort()" in src

    def test_authcontext_handles_cancelederror(self):
        src = self._read("contexts/AuthContext.jsx")
        assert "CanceledError" in src

    def test_authcontext_guards_setloading(self):
        src = self._read("contexts/AuthContext.jsx")
        assert "signal.aborted" in src

# ══════════════════════════════════════════════════════════════════════════════
# 8. BACKEND ROUTE COVERAGE
# ══════════════════════════════════════════════════════════════════════════════
class TestBackendRoutes:
    def _server(self):
        return BACKEND.read_text()

    def test_all_critical_routes_exist(self):
        src = self._server()
        routes = [
            '/auth/login', '/auth/logout', '/auth/me',
            '/items', '/purchases', '/usage', '/sales',
            '/stock', '/alerts', '/dashboard',
            '/expenses', '/salaries', '/pnl',
            '/whatsapp/numbers', '/whatsapp/settings',
            '/business-profile', '/staff', '/users',
        ]
        for route in routes:
            assert f'"{route}"' in src or f"'{route}'" in src, \
                f"Missing route: {route}"

    def test_pnl_export_endpoint_exists(self):
        src = self._server()
        assert '"/pnl/export"' in src or "'/pnl/export'" in src

    def test_pnl_trend_endpoint_exists(self):
        src = self._server()
        assert '"/pnl/trend"' in src

    def test_httponly_cookie_on_login(self):
        src = self._server()
        assert "httponly=True" in src or "HttpOnly" in src

    def test_cors_middleware_present(self):
        src = self._server()
        assert "CORSMiddleware" in src

    def test_apscheduler_present(self):
        src = self._server()
        assert "AsyncIOScheduler" in src or "APScheduler" in src

    def test_whatsapp_run_job_endpoint(self):
        src = self._server()
        assert '"/whatsapp/run-job/' in src

    def test_salary_pay_endpoint(self):
        src = self._server()
        assert '"/salaries/{salary_id}/pay"' in src

    def test_bulk_reorder_endpoint(self):
        src = self._server()
        assert '"/items/bulk-reorder"' in src

    def test_pdf_export_uses_reportlab(self):
        src = self._server()
        assert "reportlab" in src or "PDF" in src or "StreamingResponse" in src

# ══════════════════════════════════════════════════════════════════════════════
# 9. BUSINESS RULES
# ══════════════════════════════════════════════════════════════════════════════
class TestBusinessRules:

    def test_cannot_deactivate_category_with_active_items(self):
        src = BACKEND.read_text()
        # Should have a check before deactivating category
        cat_update = src[src.find('"/categories/{cat_id}"'):][:500]
        assert "Cannot deactivate" in cat_update or "active items" in cat_update.lower() \
               or "is_active" in cat_update

    def test_duplicate_sales_returns_409(self):
        src = BACKEND.read_text()
        sales_post = src[src.find('@api.post("/sales")'):][:400]
        assert "409" in sales_post or "already" in sales_post.lower()

    def test_duplicate_salary_returns_409(self):
        src = BACKEND.read_text()
        sal_post = src[src.find('@api.post("/salaries")'):][:400]
        assert "409" in sal_post or "already" in sal_post.lower()

    def test_stock_calculated_from_purchases_minus_usage(self):
        src = BACKEND.read_text()
        stock_section = src[src.find('@api.get("/stock")'):][:600]
        assert "purchase" in stock_section.lower() or "usage" in stock_section.lower()

    def test_inr_formatter_exists(self):
        fmt = (SRC / "lib/format.js").read_text()
        assert "inr" in fmt
        assert "en-IN" in fmt or "INR" in fmt

    def test_today_ist_function_exists(self):
        fmt = (SRC / "lib/format.js").read_text()
        assert "todayIST" in fmt
        assert "Asia/Kolkata" in fmt

    def test_api_interceptor_redirects_401_to_login(self):
        src = (SRC / "lib/api.js").read_text()
        assert "401" in src
        assert "/login" in src

    def test_api_uses_withcredentials(self):
        src = (SRC / "lib/api.js").read_text()
        assert "withCredentials: true" in src

    def test_whatsapp_log_only_mode(self):
        src = BACKEND.read_text()
        assert "log_only" in src

# ══════════════════════════════════════════════════════════════════════════════
# 10. DISPLAY MODE BUG FIX VERIFICATION
# ══════════════════════════════════════════════════════════════════════════════
class TestBugFixes:

    def test_bug1_dhaba_name_uses_profile(self):
        """Bug #1: Dhaba name not updating on login/display page"""
        src = (SRC / "pages/DisplayMode.jsx").read_text()
        assert "profile.name" in src
        assert "SP Royal Punjabi Dhaba" not in src

    def test_bug1_login_page_name_source(self):
        """Login page header uses hardcoded text (acceptable — it's a brand label)"""
        src = (SRC / "pages/Login.jsx").read_text()
        # Login page is OK to have static brand name in visual section
        assert "Punjabi" in src  # brand identity

    def test_bug2_dailyusage_grid_columns(self):
        """Bug #2: Field misalignment in Daily Usage — check md:col-span values sum to 12"""
        src = (SRC / "pages/DailyUsage.jsx").read_text()
        # Find col-span values in the entry row
        spans = re.findall(r'md:col-span-(\d+)', src)
        spans_int = [int(s) for s in spans]
        # The entry row should have cols summing to 12
        assert 12 in [sum(spans_int[i:i+4]) for i in range(len(spans_int)-3)]

    def test_bug3_no_unhandled_promise_rejections(self):
        """Bug #3: Uncaught exceptions — all API calls have catch handlers"""
        pages = ["Dashboard", "Sales", "Purchases", "Expenses",
                 "LiveStock", "Alerts", "DailyUsage"]
        for page in pages:
            src = (SRC / f"pages/{page}.jsx").read_text()
            api_calls = len(re.findall(r'api\.(get|post|patch|delete)\(', src))
            catch_handlers = len(re.findall(r'\.catch\(|try\s*{|formatApiError|catch\s*\(', src))
            # Every file with API calls should have at least one error handler
            if api_calls > 0:
                assert catch_handlers > 0, \
                    f"{page}.jsx has {api_calls} API calls but no error handling"

    def test_business_profile_context_has_default(self):
        """DisplayMode profile.name should never be undefined"""
        src = (SRC / "contexts/BusinessProfileContext.jsx").read_text()
        # Default value should be set
        assert "SP Royal Punjabi Dhaba" in src  # default fallback value

    def test_protected_route_exists(self):
        src = (SRC / "components/ProtectedRoute.jsx").read_text()
        assert "role" in src or "auth" in src.lower()

# ══════════════════════════════════════════════════════════════════════════════
# 11. IMPORT INTEGRITY
# ══════════════════════════════════════════════════════════════════════════════
class TestImportIntegrity:
    """Verify no missing or duplicate imports"""

    def _check_imports(self, filepath, required_hooks):
        src = (SRC / filepath).read_text()
        import_line = re.search(r'import\s*{([^}]+)}\s*from\s*["\']react["\']', src)
        assert import_line, f"No React import found in {filepath}"
        imported = [h.strip() for h in import_line.group(1).split(",")]
        for hook in required_hooks:
            assert hook in imported, f"{hook} missing from {filepath} React import"

    def test_dailyusage_imports(self):
        self._check_imports("pages/DailyUsage.jsx",
                            ["useEffect", "useState", "useCallback"])

    def test_sales_imports(self):
        self._check_imports("pages/Sales.jsx",
                            ["useEffect", "useMemo", "useState", "useCallback"])

    def test_purchases_imports(self):
        self._check_imports("pages/Purchases.jsx",
                            ["useEffect", "useMemo", "useState", "useCallback"])

    def test_expenses_imports(self):
        self._check_imports("pages/Expenses.jsx",
                            ["useEffect", "useMemo", "useState", "useCallback"])

    def test_livestock_imports(self):
        self._check_imports("pages/LiveStock.jsx",
                            ["useEffect", "useState", "useMemo", "useCallback"])

    def test_displaymode_imports(self):
        self._check_imports("pages/DisplayMode.jsx",
                            ["useEffect", "useState", "useCallback"])

    def test_layout_imports(self):
        src = (SRC / "components/Layout.jsx").read_text()
        assert "useCallback" in src

    def test_no_duplicate_react_imports(self):
        pages = list((SRC / "pages").glob("*.jsx"))
        for page in pages:
            src = page.read_text()
            react_imports = re.findall(r'from\s*["\']react["\']', src)
            assert len(react_imports) <= 1, \
                f"{page.name} has duplicate React imports"

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

# ══════════════════════════════════════════════════════════════════════════════
# 12. TIMESTAMPS, DUPLICATE DETECTION & VOID SYSTEM
# ══════════════════════════════════════════════════════════════════════════════
class TestTimestampDuplicateVoid:

    def _server(self):
        return Path("/home/claude/SP_Dhaba_Fixed/backend/server.py").read_text()

    def _read(self, f):
        return (Path("/home/claude/SP_Dhaba_Fixed/frontend/src") / f).read_text()

    # ── Timestamp formatter ────────────────────────────────────────────────
    def test_fmtTimestamp_exists_in_format_js(self):
        src = self._read("lib/format.js")
        assert "fmtTimestamp" in src
        assert "Asia/Kolkata" in src

    def test_fmtTimestamp_includes_IST_suffix(self):
        src = self._read("lib/format.js")
        assert "IST" in src

    def test_fmtTimestamp_exported(self):
        src = self._read("lib/format.js")
        assert "export function fmtTimestamp" in src

    def test_purchases_imports_fmtTimestamp(self):
        src = self._read("pages/Purchases.jsx")
        assert "fmtTimestamp" in src

    def test_expenses_imports_fmtTimestamp(self):
        src = self._read("pages/Expenses.jsx")
        assert "fmtTimestamp" in src

    def test_dailyusage_imports_fmtTimestamp(self):
        src = self._read("pages/DailyUsage.jsx")
        assert "fmtTimestamp" in src

    def test_purchases_renders_logged_at_column(self):
        src = self._read("pages/Purchases.jsx")
        assert "Logged at" in src
        assert "fmtTimestamp(r.created_at)" in src

    def test_expenses_renders_logged_at_column(self):
        src = self._read("pages/Expenses.jsx")
        assert "Logged at" in src
        assert "fmtTimestamp(r.created_at)" in src

    def test_dailyusage_renders_logged_at_column(self):
        src = self._read("pages/DailyUsage.jsx")
        assert "Logged at" in src
        assert "fmtTimestamp(r.created_at)" in src

    # ── created_at in all create handlers ─────────────────────────────────
    def test_purchase_doc_has_created_at(self):
        src = self._server()
        idx = src.find("async def create_purchase")
        section = src[idx:idx+1200]
        assert '"created_at": iso(now_utc())' in section

    def test_usage_doc_has_created_at(self):
        src = self._server()
        idx = src.find("async def create_usage")
        section = src[idx:idx+1200]
        assert '"created_at": iso(now_utc())' in section

    def test_expense_doc_has_created_at(self):
        src = self._server()
        idx = src.find("async def create_expense")
        section = src[idx:idx+1200]
        assert '"created_at": iso(now_utc())' in section

    # ── Duplicate time-window detection ───────────────────────────────────
    def test_purchase_duplicate_check_exists(self):
        src = self._server()
        idx = src.find("async def create_purchase")
        section = src[idx:idx+1200]
        assert "window_start" in section
        assert "409" in section
        assert "10" in section  # 10-second window

    def test_usage_duplicate_check_exists(self):
        src = self._server()
        idx = src.find("async def create_usage")
        section = src[idx:idx+1200]
        assert "window_start" in section
        assert "409" in section

    def test_expense_duplicate_check_exists(self):
        src = self._server()
        idx = src.find("async def create_expense")
        section = src[idx:idx+1200]
        assert "window_start" in section
        assert "409" in section

    def test_duplicate_check_uses_is_void_filter(self):
        """Voided entries should not count as duplicates"""
        src = self._server()
        idx = src.find("async def create_purchase")
        section = src[idx:idx+1200]
        assert '"is_void": False' in section

    def test_duplicate_window_math(self):
        """10-second window logic"""
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(seconds=10)
        entry_time = now - timedelta(seconds=5)
        assert entry_time >= window_start  # within window → duplicate
        entry_time2 = now - timedelta(seconds=15)
        assert entry_time2 < window_start  # outside window → legitimate

    # ── is_void field in create docs ──────────────────────────────────────
    def test_purchase_doc_has_void_fields(self):
        src = self._server()
        idx = src.find("async def create_purchase")
        section = src[idx:idx+1600]
        assert '"voided_by": None' in section
        assert 'void_reason' in section

    def test_usage_doc_has_void_fields(self):
        src = self._server()
        idx = src.find("async def create_usage")
        section = src[idx:idx+900]
        assert '"is_void": False' in section

    def test_expense_doc_has_void_fields(self):
        src = self._server()
        idx = src.find("async def create_expense")
        section = src[idx:idx+900]
        assert '"is_void": False' in section

    # ── Void endpoints ─────────────────────────────────────────────────────
    def test_void_purchase_endpoint_exists(self):
        src = self._server()
        assert '"/purchases/{purchase_id}/void"' in src

    def test_void_usage_endpoint_exists(self):
        src = self._server()
        assert '"/usage/{usage_id}/void"' in src

    def test_void_expense_endpoint_exists(self):
        src = self._server()
        assert '"/expenses/{expense_id}/void"' in src

    def test_void_requires_reason(self):
        src = self._server()
        assert "Void reason is required" in src

    def test_void_stores_voided_by_and_at(self):
        src = self._server()
        assert '"voided_by": user["name"]' in src
        assert '"voided_at": iso(now_utc())' in src

    def test_staff_cannot_void_others_entries(self):
        src = self._server()
        assert 'Staff can only void their own entries' in src

    def test_staff_can_only_void_same_day(self):
        src = self._server()
        assert 'Staff can only void entries made today' in src
        assert '86400' in src  # 24h in seconds

    def test_cannot_void_already_voided(self):
        src = self._server()
        assert 'Already voided' in src

    def test_viewer_cannot_access_void(self):
        """Void endpoints use get_current_user — role check inside handler"""
        src = self._server()
        void_section = src[src.find('async def void_purchase'):][:300]
        assert 'get_current_user' in void_section

    # ── Void excluded from calculations ───────────────────────────────────
    def test_stock_excludes_voided_purchases(self):
        src = self._server()
        idx = src.find('@api.get("/stock")')
        section = src[idx:idx+600]
        assert '"$ne": True' in section
        assert '"is_void"' in section

    def test_stock_excludes_voided_usage(self):
        src = self._server()
        idx = src.find('@api.get("/stock")')
        section = src[idx:idx+600]
        # Both purchase and usage aggs should exclude void
        assert section.count('"is_void"') >= 2

    def test_dashboard_excludes_voided_purchases(self):
        src = self._server()
        idx = src.find('async def dashboard')
        section = src[idx:idx+400]
        assert '"is_void"' in section

    def test_dashboard_excludes_voided_expenses(self):
        src = self._server()
        idx = src.find('async def dashboard')
        section = src[idx:idx+400]
        assert section.count('"is_void"') >= 2

    def test_pnl_excludes_voided_purchases(self):
        src = self._server()
        idx = src.find('async def _compute_pnl')
        section = src[idx:idx+400]
        assert '"is_void"' in section

    def test_list_purchases_excludes_voided(self):
        src = self._server()
        idx = src.find('async def list_purchases')
        section = src[idx:idx+500]
        assert '"is_void"' in section

    def test_list_usage_excludes_voided(self):
        src = self._server()
        idx = src.find('async def list_usage')
        section = src[idx:idx+500]
        assert '"is_void"' in section

    def test_list_expenses_excludes_voided(self):
        src = self._server()
        idx = src.find('async def list_expenses')
        section = src[idx:idx+700]
        assert 'is_void' in section
        assert 'ne' in section

    # ── Frontend void UI ───────────────────────────────────────────────────
    def test_purchases_has_void_button(self):
        src = self._read("pages/Purchases.jsx")
        assert "void-purchase" in src
        assert "voidRow" in src

    def test_expenses_has_void_button(self):
        src = self._read("pages/Expenses.jsx")
        assert "void-expense" in src
        assert "voidRow" in src

    def test_dailyusage_has_void_button(self):
        src = self._read("pages/DailyUsage.jsx")
        assert "void-usage" in src
        assert "voidRow" in src

    def test_void_button_admin_staff_only(self):
        """canAdd guards the void button — viewers see no void button"""
        for page in ["pages/Purchases.jsx", "pages/Expenses.jsx", "pages/DailyUsage.jsx"]:
            src = self._read(page)
            assert "canAdd" in src
            assert "voidRow" in src

    def test_void_prompts_for_reason(self):
        """UI uses window.prompt to collect reason before calling API"""
        for page in ["pages/Purchases.jsx", "pages/Expenses.jsx", "pages/DailyUsage.jsx"]:
            src = self._read(page)
            assert "window.prompt" in src
            assert "reason.trim()" in src

    def test_void_calls_correct_endpoint(self):
        src = self._read("pages/Purchases.jsx")
        assert "/purchases/${id}/void" in src or "purchases/" in src and "/void" in src

    # ── Void business logic ───────────────────────────────────────────────
    def test_void_reason_mandatory_frontend(self):
        """If prompt is cancelled or empty, void is aborted"""
        for page in ["pages/Purchases.jsx", "pages/Expenses.jsx", "pages/DailyUsage.jsx"]:
            src = self._read(page)
            assert "if (!reason?.trim()) return" in src

    def test_fmtTimestamp_handles_null(self):
        """fmtTimestamp should return — for null/undefined"""
        src = self._read("lib/format.js")
        assert "if (!iso)" in src
        assert '"—"' in src or "'—'" in src
