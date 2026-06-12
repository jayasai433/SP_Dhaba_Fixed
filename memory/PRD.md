# SP Royal Punjabi Family Dhaba — Operations Manager (PRD)

## Original Problem Statement
Production-ready, mobile-first lightweight ERP for an Indian roadside dhaba with operations + financial features and self-service admin. Phase 2 enhancement adds Expenses, Salary, P&L, and WhatsApp notifications.

## Stack
- **Frontend**: React 19, Tailwind, shadcn/ui, Recharts, sonner, react-router 7
- **Backend**: FastAPI + Motor (async MongoDB) + APScheduler (IST cron jobs) + httpx + reportlab (PDF)
- **DB**: MongoDB (collections: users, items, purchases, daily_usage, sales, categories, units, business_profile, expenses, expense_categories, staff, salaries, whatsapp_numbers, whatsapp_settings, notifications)
- **Auth**: JWT Bearer (8h expiry, bcrypt)
- **Locale**: INR (₹), DD-MMM-YYYY, IST (Asia/Kolkata)

## Roles
- **Admin (Jaya Sai)**: Full access including Item Master, Settings (Business, Categories, Expense Cats, Units, Users, Payroll Staff, WhatsApp, Reorder Levels), Salary Tracker, P&L
- **Staff (Lokesh)**: Purchases, Daily Usage, Sales, Expenses. Sees only own entries
- **Viewer (Display)**: Read-only Dashboard, P&L, Live Stock, Alerts, Display Mode

## Implementation Log
### MVP — 31-May-2026
- JWT auth + 3 seeded accounts (admin@spdhaba.com, lokesh@spdhaba.com, display@spdhaba.com)
- Item Master, Purchases, Daily Usage, Sales, Live Stock (color-coded), Alerts, Dashboard, Display Mode, Settings (Business, Categories, Units, Users, Reorder Bulk Edit)
- 33 items + 9 categories + 9 units seeded

### Phase 2 Enhancement — 31-May-2026
- **Expense Tracker** with 6 pre-seeded categories (Maintenance, Utilities, Rent, Transport, Equipment, Others)
- **Salary Tracker** with separate `db.staff` payroll roster (Lokesh seeded; owner not in payroll). Monthly entries with basic-advance=net, mark-as-paid flow
- **Full P&L Statement** (Today/Week/Month/All) with PDF export via reportlab; 30-day daily P&L trend chart
- **WhatsApp Notifications** in **LOG-ONLY mode** (blank credentials). Real send activates by adding `WHATSAPP_ACCESS_TOKEN` + `WHATSAPP_PHONE_NUMBER_ID` to `/app/backend/.env`. Triggers: out-of-stock, low-stock, large-purchase (₹5000 threshold), morning 8 AM IST report, daily 10 PM IST report, 11 PM IST no-sales reminder, daily loss alert. Notification log with retry support
- **APScheduler** with IST cron jobs (morning_report 8AM, daily_report 10PM, no_sales_reminder 11PM)
- **Enhanced Settings** with 3 new tabs: Expense Cats, Payroll Staff, WhatsApp Configuration
- **Enhanced Dashboard** with Today's Expenses, Today's P&L (green/red), Overall P&L, Operating Expense Breakdown panel
- **Expense category validation** at backend on create

## Test Coverage
- Iteration 1 (MVP): 34/34 backend, frontend pass
- Iteration 2: Frontend re-test pass
- Iteration 3 (Phase 2): **28/28 new backend tests pass, frontend smoke 100%**

## UX Audit (12-Feb-2026) — see [`UX_REVIEW_PRD.md`](./UX_REVIEW_PRD.md)
Product score: **5.5 / 10**. Three P0 production-credibility blockers identified:
- P0-1: Remove "Unknown environment / Railway" warning banner from production UI.
- P0-2: Fix dashboard date (currently shows `12-Jun-2026` — TZ/clock issue corrupts every "Today" KPI).
- P0-3: "PROFIT" badge incorrectly shown on ₹0 P&L (Today + Overall).
Full PRD with P0/P1/P2/P3 backlog, acceptance criteria, and 4-week rollout plan in `UX_REVIEW_PRD.md`.

## Prioritized Backlog
**P1**
- WhatsApp real-sending: user provides `WHATSAPP_ACCESS_TOKEN` + `WHATSAPP_PHONE_NUMBER_ID` → flip from LOG-ONLY to live
- WhatsApp webhook for delivery receipts (sent → delivered → read updates)
- Edit purchases/usage/expense entries by admin
- CSV export of expenses + salaries + transactions

**P2**
- Refresh-token flow (currently single 8h access token)
- Shadcn Calendar / MonthPicker (instead of native HTML date inputs)
- Audit log
- Per-month P&L PDF schedule auto-email/WhatsApp

**P3**
- Multi-outlet, PWA offline, i18n (Hindi/Punjabi)
- Recharts width(-1) cosmetic warning fix (use inline `style={{height:256}}` instead of Tailwind `h-64` on chart parents)
- Refactor server.py into modules once it exceeds ~1500 lines

## Demo Accounts (also in /app/memory/test_credentials.md)
| Role   | Email                  | Password   |
|--------|------------------------|------------|
| admin  | admin@spdhaba.com      | Admin@123  |
| staff  | lokesh@spdhaba.com     | Staff@123  |
| viewer | display@spdhaba.com    | View@123   |
