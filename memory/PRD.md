# SP Royal Punjabi Family Dhaba — Operations Manager (PRD)

## Original Problem Statement
Build a production-ready, mobile-first lightweight ERP for an Indian roadside dhaba. Track Items, Purchases, Daily Usage, Sales, Live Stock (color-coded), Alerts, Dashboard, Display Mode, and provide self-service Admin Settings — no developer involvement for ongoing operational changes.

## Stack & Architecture
- **Frontend**: React 19 + Tailwind CSS + shadcn/ui + Recharts + sonner toasts + react-router 7
- **Backend**: FastAPI + Motor (async MongoDB driver)
- **DB**: MongoDB (collections: users, items, purchases, daily_usage, sales, categories, units, business_profile)
- **Auth**: JWT Bearer tokens, 8h expiry, bcrypt password hashing
- **Mobile-first**: Bottom nav on mobile, fixed sidebar on desktop
- **Currency**: INR (₹), Date: DD-MMM-YYYY (IST)

## User Personas & Roles
- **Admin (Jaya Sai)**: Full control. Manages items, categories, units, users, business profile, sees all reports.
- **Staff (Lokesh)**: Adds purchases/usage/sales. Sees only own entries. Cannot edit/delete/access settings.
- **Viewer (Display)**: Read-only for partners; Display Mode for TV wall.

## What's Implemented (31-May-2026)
- JWT auth with seeded demo accounts (admin/staff/viewer) + role-based route guards
- Item Master CRUD with categories/units dropdowns (admin only); deactivate vs hard delete
- Purchases with auto-calc total, running total, filters by date/item
- Daily Usage with multi-item entry per session, stock overuse warning, optional notes
- Sales (lunch + dinner + other), one-per-day enforcement, weekly/monthly totals
- Live Stock with color-coded cards (green/yellow/red), 60s auto-refresh, search + filters
- Alerts page sorted by urgency, celebration empty state, one-tap Log Purchase deep link
- Summary Dashboard: 6 KPIs, 30-day sales trend chart, stock health donut, category spend, top 5 items
- Display Mode (full-screen, live ticking clock, auto refresh)
- Settings: Business profile (with logo upload base64), Category mgmt, Unit mgmt, User mgmt + reset password, Bulk reorder editor
- 33 seeded items + 9 categories + 9 units pre-loaded for instant use

## Test Coverage
- Backend: 34/34 pytest cases pass (auth, RBAC, CRUD, math, filters, isolation)
- Frontend: All pages render without errors. Verified via testing_agent_v3.

## Prioritized Backlog (Deferred)
**P1**
- Forgot-password self-service (currently admin-resets-only)
- CSV export of purchases / usage / sales
- Date-range filter on Dashboard
- Edit purchase/usage entry by Admin (currently no edit after save)

**P2**
- Refresh-token flow (currently single 8h access token)
- Per-meal category split on Sales
- WhatsApp/SMS alert when stock crosses reorder level
- Audit log of who-did-what

**P3**
- Multi-outlet support
- PWA offline mode for unstable rural internet
- i18n (Hindi/Punjabi UI)

## Demo Accounts (also in /app/memory/test_credentials.md)
| Role   | Email                  | Password   |
|--------|------------------------|------------|
| admin  | admin@sprojal.com      | Admin@123  |
| staff  | lokesh@sprojal.com     | Staff@123  |
| viewer | display@sprojal.com    | View@123   |
