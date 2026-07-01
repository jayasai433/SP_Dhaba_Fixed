# Archived Features Reference

Snapshot at time of the July 2025 slim-down. All features listed below were **removed from the live codebase** to reduce scope to Expenses, Sales, Purchases, and Item Master.

This file exists so any of them can be re-introduced quickly without reconstructing intent from scratch. The full git history (`git log`) retains every deleted file if code diving is needed.

## Table of contents
1. [Stock and inventory calculation](#1-stock-and-inventory-calculation)
2. [Alerts (low stock / out of stock)](#2-alerts-low-stock--out-of-stock)
3. [Closing stock (physical daily count)](#3-closing-stock-physical-daily-count)
4. [Daily usage tracking](#4-daily-usage-tracking)
5. [Wastage and suppliers](#5-wastage-and-suppliers)
6. [Salaries and staff master](#6-salaries-and-staff-master)
7. [P&L statement (report + PDF + CSV)](#7-pl-statement-report--pdf--csv)
8. [CSV exports (sales / purchases / pnl)](#8-csv-exports)
9. [Groq AI features: daily digest, smart reorder, anomaly detection](#9-groq-ai-features)
10. [WhatsApp notifications and scheduler](#10-whatsapp-notifications-and-scheduler)
11. [Inventory insights, consumption rate, cost calculator](#11-inventory-insights)
12. [Dashboard (KPI + charts)](#12-dashboard)
13. [Display mode (kitchen TV view)](#13-display-mode)
14. [Anomaly check + duplicate warning dialogs](#14-anomaly-and-duplicate-dialogs)

Every path is relative to `/app` and reflects the state **before** the trim (see `git log --before=2025-07-XX` for the exact snapshot).

---

## 1. Stock and inventory calculation

**Purpose**: Compute per-item live stock from purchases minus daily usage, categorised as `in / low / out` against a reorder threshold. Feeds Alerts, Dashboard, DisplayMode, InventoryInsights.

**Backend files removed**
- `backend/services/stock.py` (compute_stock, get_alerts, aggregate_dashboard_data)
- `backend/routers/stock.py` (GET `/api/stock`, `/api/alerts`, `/api/dashboard`)
- Field `reorder_level` on `items` collection

**Frontend files removed**
- `frontend/src/pages/LiveStock.jsx`
- `frontend/src/pages/Dashboard.jsx` (partial, see #12)
- Stock health pie/kpi cards, low/out counters

**Data schema**: derived at query time, no persisted stock collection.

**Re-introduce**: Stock can be re-derived purely from `purchases` (base_quantity field is now persisted per line) once a `usage` or `sales-line-item` collection exists. No schema migration needed for purchases.

---

## 2. Alerts (low stock / out of stock)

**Purpose**: Real-time out/low-stock badge and page. Chef looked at it before ordering.

**Backend files removed**
- Part of `services/stock.py` (`get_alerts`) and `routers/stock.py` (`GET /api/alerts`)

**Frontend files removed**
- `frontend/src/pages/Alerts.jsx`
- Layout badge on `/alerts` sidebar link

**Status at removal**: Feature had been route-hidden ("chef communicates stock needs manually") but code was live.

---

## 3. Closing stock (physical daily count)

**Purpose**: End-of-day physical shelf count per item, used to compute daily wastage variance against purchases.

**Backend files removed**
- `backend/models/closing_stock.py`
- `backend/routers/closing_stock.py` (`POST /closing-stock`, `GET /closing-stock/{date}`, summary, trend)
- `backend/services/inventory/closing_stock_service.py`

**Frontend files removed**
- `frontend/src/pages/ClosingStock.jsx`

**Data**: collection `closing_stock` was dropped in the Atlas wipe.

---

## 4. Daily usage tracking

**Purpose**: Ingredient consumption input by kitchen staff. Was the predecessor to consumption-rate estimates.

**Backend files removed**
- `backend/routers/usage.py` (`GET/POST /api/usage`, void)
- `UsageIn` in `models/transaction.py`
- `check_duplicate_usage` in `services/duplicate.py`

**Frontend files removed**: none (route hidden already, redirected to closing-stock).

**Data**: collection `daily_usage` was dropped in the Atlas wipe.

---

## 5. Wastage and suppliers

**Purpose**: Track wasted stock with reason codes; supplier master for POs.

**Backend files removed**
- `backend/models/wastage.py`
- `backend/routers/wastage.py`

**Frontend files removed**
- `frontend/src/pages/Wastage.jsx`

**Data**: collections `wastage`, `suppliers` dropped in wipe.

---

## 6. Salaries and staff master

**Purpose**: Monthly salary entry per staff, feeds P&L.

**Backend files removed**
- `backend/routers/salaries.py`
- Salary/staff models (were inline in routers)

**Frontend files removed**
- `frontend/src/pages/Salaries.jsx`

**Data**: collections `salaries`, `staff` dropped.

---

## 7. P&L statement (report + PDF + CSV)

**Purpose**: Revenue minus COGS minus expenses minus salaries. Included PDF export via reportlab, CSV export, and daily trend line chart.

**Backend files removed**
- `backend/services/pnl.py` (compute_pnl, compute_pnl_trend, export_pnl_pdf)
- `backend/routers/pnl.py`

**Frontend files removed**
- `frontend/src/pages/PnL.jsx`

**Dep footprint**: `reportlab` can now come out of `requirements.txt`.

---

## 8. CSV exports

**Purpose**: Download sales / purchases / pnl as UTF-8 BOM CSVs for Excel.

**Backend files removed**
- `backend/routers/exports.py`

**Frontend files removed**: export buttons on Sales, Purchases, PnL pages.

**Re-introduce**: trivial when data model stays clean; see `git log routers/exports.py`.

---

## 9. Groq AI features

Includes daily digest, smart reorder advice, anomaly detection on purchase entries.

**Backend files removed**
- `backend/routers/insights.py`
- Related routes on `server.py` monolith: `/ai-insight`, `/anomaly-check`, `/consumption-rates`, `/smart-reorder`, `/daily-digest`
- `backend/services/consumption.py`
- `backend/services/inventory/analytics.py`
- `backend/services/inventory/alerts.py`
- `backend/services/inventory/recommender.py`
- `backend/services/inventory/cost_calculator.py`

**Frontend files removed**
- `frontend/src/components/DailyDigestCard.jsx`
- `frontend/src/components/SmartReorderCard.jsx`
- `frontend/src/components/AnomalyWarningDialog.jsx`

**External deps**: `GROQ_API_KEY` env var, `httpx` calls to `api.groq.com`. Can be dropped from Railway.

---

## 10. WhatsApp notifications and scheduler

**Purpose**: Push notifications to owner for out-of-stock, large purchase, no-sales reminder, daily loss, morning report. Managed via APScheduler background jobs.

**Backend files removed**
- `backend/services/whatsapp.py` (start_scheduler / stop_scheduler + all notify functions)
- `backend/routers/whatsapp.py`
- `whatsapp_settings` collection

**External integration**: WhatsApp Business API (Meta Cloud). Env vars used: `META_ACCESS_TOKEN`, `META_PHONE_NUMBER_ID`, `OWNER_WHATSAPP`.

**Deps to remove**: `APScheduler`.

---

## 11. Inventory insights

**Purpose**: Analytics dashboard with consumption rate per item, purchase recommendations, ingredient cost trend.

**Backend files removed**
- `backend/routers/inventory_insights.py`
- `backend/services/inventory/*` (whole package)

**Frontend files removed**
- `frontend/src/pages/InventoryInsights.jsx`

---

## 12. Dashboard

**Purpose**: KPI grid (today/week/month sales, expenses, P&L, all-time totals, low/out stock counts) + sales trend line + stock health pie + category spend + top items + Daily Digest + Smart Reorder card.

**Frontend files removed**
- `frontend/src/pages/Dashboard.jsx`

Backend endpoint `/api/dashboard` also removed (was in `routers/stock.py`).

Landing route now redirects to `/sales`.

---

## 13. Display mode

**Purpose**: Full-screen kitchen TV view showing low-stock items in large font, auto-refresh.

**Frontend files removed**
- `frontend/src/pages/DisplayMode.jsx`
- `viewer` role redirect target adjusted to `/sales`.

---

## 14. Anomaly and duplicate dialogs

**Duplicate dialog** retained inline (silently rejects near-duplicate purchase entries by DB, no modal). The 10-second duplicate window in `services/duplicate.py` is retained but simplified.

**Anomaly dialog** removed entirely. Was a Groq-powered check that popped up when an entered price/quantity looked wildly off historical mean.

**Files removed**
- `frontend/src/components/AnomalyWarningDialog.jsx`
- `frontend/src/components/DuplicateWarningDialog.jsx` (folded into inline toast)

---

## Restore checklist (future)

To re-add any of the above:
1. `git log --oneline --all -- <path>` to find the last commit that had the file.
2. `git show <sha>:<path> > <path>` to restore.
3. Re-register router in `backend/main.py`.
4. Re-add page + route in `frontend/src/App.js`.
5. Restore any collection indexes in `backend/services/seed.py`.
6. Add any external env vars back to Railway (Groq, WhatsApp, etc.).

Data schemas of removed collections are preserved in the last version of the corresponding model file in git history.
