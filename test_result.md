#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

user_problem_statement: |
  Deploy a slim, mobile-first ops app to Railway with only Expenses, Sales,
  Purchases, and a lightweight Item Master (multi-unit conversion). Wipe Atlas
  and re-seed. Archive everything removed. Support a custom GoDaddy domain.

backend:
  - task: "Auth: login/logout/me, 3-role users"
    implemented: true
    working: true
    file: "backend/routers/auth.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "Rate limit now awaited (was fire-and-forget). Seeded admin/staff/viewer verified via curl on local Mongo."
        -working: true
        -agent: "testing"
        -comment: "✅ ALL AUTH TESTS PASSED (5/5): Admin login returns 200 with token+user. GET /me with Bearer token returns correct user object. Wrong password returns 401. Staff and viewer logins successful. Rate limiter tracking login attempts correctly without blocking valid logins."
  - task: "Item Master with multi-unit conversion"
    implemented: true
    working: true
    file: "backend/routers/items.py, backend/models/item.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "New schema: base_unit + units[{name,conversion_factor,is_default}] + default_price. GET /items?q= supports search. Staff can create items on the fly."
        -working: true
        -agent: "testing"
        -comment: "✅ ALL ITEMS TESTS PASSED (8/8): GET /items returns 9 seed items with correct multi-unit schema (base_unit, units[], default_price). Search ?q=egg works. Egg has correct units: piece(1), dozen(12), tray(30). Admin and staff can create multi-unit items. Duplicate name returns 400. PATCH updates item. DELETE soft-deletes (is_active=false, excluded from default list, included with include_inactive=true)."
  - task: "Purchases with per-line unit override + base_quantity"
    implemented: true
    working: true
    file: "backend/routers/purchases.py, backend/models/transaction.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "POST /purchases validates unit is one of item.units, persists unit_conversion_factor and base_quantity for future stock aggregation. Verified end-to-end via UI screenshot flow."
        -working: true
        -agent: "testing"
        -comment: "✅ ALL PURCHASES TESTS PASSED (5/5): Multi-unit purchase correctly calculates base_quantity (2 dozen = 24 pieces, total_cost=180). Invalid unit 'litre' for Egg returns 400. Duplicate within 10s returns 409. GET /purchases returns list with item_name populated. PATCH /void by admin succeeds, voided purchase excluded from default list."
  - task: "Sales daily aggregate (lunch/dinner/other)"
    implemented: true
    working: true
    file: "backend/routers/sales.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "Unchanged model. One-entry-per-date unique index. Admin PATCH for corrections."
        -working: true
        -agent: "testing"
        -comment: "✅ ALL SALES TESTS PASSED (5/5): POST /sales creates entry with total_amount=3000 (1000+2000+0). Duplicate date returns 409. GET /sales/check/{date} returns exists=true with entry. Admin PATCH succeeds. Staff PATCH returns 403 (admin-only correction path working)."
  - task: "Expenses with duplicate window + void"
    implemented: true
    working: true
    file: "backend/routers/expenses.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "Only expense_categories that exist are accepted. Duplicate window guard retained."
        -working: true
        -agent: "testing"
        -comment: "✅ ALL EXPENSES TESTS PASSED (6/6): GET /expense-categories returns 6 seeded categories (Maintenance, Utilities, Rent, Transport, Equipment, Others). POST with valid category succeeds. Invalid category 'ThisDoesNotExist' returns 400. Duplicate within 10s returns 409. Admin void succeeds. Viewer void returns 403."
  - task: "Seed script: users, categories, items, indexes"
    implemented: true
    working: true
    file: "backend/services/seed.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "Trimmed to only the collections in scope. Multi-unit seed items include Egg (piece/dozen/tray), Onion (kg/g/bag), etc."
        -working: true
        -agent: "testing"
        -comment: "✅ SEED VERIFIED: All 3 users seeded correctly (admin@spdhaba.com, lokesh@spdhaba.com, display@spdhaba.com). 9 items with multi-unit schema. 6 expense categories. All credentials working."

frontend:
  - task: "Mobile-first Layout with 4 bottom-nav tabs"
    implemented: true
    working: true
    file: "frontend/src/components/Layout.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "Sales/Purchases/Expenses/Items. Thumb-friendly bottom nav on mobile, sidebar on md+. Verified via mobile screenshot."
  - task: "Sales page (aggregate totals, KPI header)"
    implemented: true
    working: true
    file: "frontend/src/pages/Sales.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "Today/Week/Month/AllTime KPIs above the fold. Empty state present. Admin edit path via duplicate detection banner."
  - task: "Purchases page with item picker + on-the-fly item add + unit override"
    implemented: true
    working: true
    file: "frontend/src/pages/Purchases.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "Verified via UI flow: search 'egg' -> selects -> switch unit piece->dozen -> save -> row appears. Total shows base conversion inline."
  - task: "Items page with multi-unit dialog"
    implemented: true
    working: true
    file: "frontend/src/pages/Items.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "Add/edit dialog lets you add multiple units with conversion factor. Search bar over name/category. ItemDialog is exported so Purchases can reuse it."
  - task: "Expenses page"
    implemented: true
    working: true
    file: "frontend/src/pages/Expenses.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: true
        -agent: "main"
        -comment: "Day/Week/Month KPI. Category dropdown. Void supported via VoidDialog."

metadata:
  created_by: "main_agent"
  version: "2.0-slim"
  test_sequence: 1
  run_ui: false

test_plan:
  current_focus: []
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
    -agent: "main"
    -message: |
        Slim-down complete. Backend running on main:app (server.py is a one-line shim
        for supervisor compatibility). Frontend rebuilt around 4 mobile-first pages.
        Atlas both prod (sp_dhaba) and staging (sp_dhaba_staging) DBs wiped via
        db.drop_database(). Seed script recreates users + starter items + categories
        on first backend boot against fresh DB.
        
        Test scenarios of interest for backend:
        1. POST /api/auth/login with admin@spdhaba.com/Admin@123 succeeds; returns
           token and user; sets sp_token httpOnly cookie.
        2. Repeated bad logins from same IP > 10 in 5 min -> 429.
        3. GET /api/items lists seeded items; GET /api/items?q=egg filters.
        4. POST /api/items creates a new item with multi-unit list and rejects
           duplicate name.
        5. PATCH /api/items/{id} updates unit list.
        6. POST /api/purchases with unit=dozen for Egg (which has piece as base)
           persists base_quantity = quantity * 12 automatically.
        7. POST /api/purchases with an invalid unit for the item -> 400.
        8. Same POST /api/purchases twice within 10s -> 409 duplicate.
        9. POST /api/sales for today succeeds; second POST for the same date -> 409.
        10. POST /api/expenses with unknown category -> 400.
        11. PATCH /api/expenses/{id}/void by admin succeeds; by viewer -> 403.
        
        Test credentials in /app/memory/test_credentials.md. All 3 seeded on boot.
    -agent: "testing"
    -message: |
        🎉 COMPREHENSIVE BACKEND TESTING COMPLETE - ALL 30 TESTS PASSED
        
        Executed full test suite covering all 5 routers (auth, items, purchases, sales, expenses).
        Base URL: https://bottleneck-finder-6.preview.emergentagent.com/api
        Test Date: 2026-07-01 (IST)
        
        ✅ AUTH (5/5 tests passed):
        - Admin/staff/viewer login returns 200 with token+user
        - GET /me with Bearer token works
        - Wrong password returns 401
        - Rate limiter tracking attempts without blocking valid logins
        
        ✅ ITEMS (8/8 tests passed):
        - GET /items returns 9 seed items with multi-unit schema
        - Search ?q=egg returns Egg item
        - Egg has correct units: piece(1), dozen(12), tray(30)
        - Admin and staff can create multi-unit items
        - Duplicate name returns 400
        - PATCH updates item
        - DELETE soft-deletes (is_active=false)
        
        ✅ PURCHASES (5/5 tests passed):
        - Multi-unit: 2 dozen = 24 pieces, base_quantity calculated correctly
        - Invalid unit returns 400
        - Duplicate within 10s returns 409
        - GET /purchases populates item_name
        - Admin void works, voided entries excluded from default list
        
        ✅ SALES (5/5 tests passed):
        - POST creates entry with total_amount=3000
        - Duplicate date returns 409
        - GET /sales/check/{date} works
        - Admin PATCH succeeds
        - Staff PATCH returns 403 (admin-only)
        
        ✅ EXPENSES (6/6 tests passed):
        - GET /expense-categories returns 6 seeded categories
        - POST with valid category succeeds
        - Invalid category returns 400
        - Duplicate within 10s returns 409
        - Admin void succeeds
        - Viewer void returns 403
        
        ✅ SEED (verified):
        - All 3 users seeded with correct credentials
        - 9 items with multi-unit schema
        - 6 expense categories
        
        NO ISSUES FOUND. All responses are valid JSON (no ObjectId serialization issues).
        All date handling is IST-based (passing today's IST date succeeds).
        All role-based permissions working correctly.
        All duplicate detection and validation working as expected.
