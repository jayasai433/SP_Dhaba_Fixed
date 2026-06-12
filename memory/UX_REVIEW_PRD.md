# SP Royal Punjabi Family Dhaba — UX Review PRD
**Document type:** Product Requirements Document (PRD) derived from UX audit
**Author:** Product / UX Review
**Date:** 12-Feb-2026
**Status:** Ready for engineering pickup
**Source review:** Brutally honest UX audit of live production build (Admin/Staff/Viewer roles, desktop + mobile 390×844)
**Current product score:** 5.5 / 10 → **Target after this PRD:** 8.0 / 10

---

## 0. Executive Summary

The Operations Manager is architecturally sound but three small bugs and a handful of UX gaps make it feel like a half-finished demo to non-technical staff (Lokesh). This PRD lists the **exact items to fix, in priority order, with acceptance criteria**. Everything below is scoped so a single engineer can execute the P0 block in one working day.

### Priority distribution
| Priority | Count | ETA (engineer-days) |
|---|---|---|
| P0 — Production credibility blockers | 3 | 0.5 |
| P1 — High-impact polish + data trust | 7 | 2 |
| P2 — Missing operational features | 6 | 4 |
| P3 — Nice-to-have, future quarters | 5 | — |

### Success metrics (post-launch)
- **0** "this looks broken" support pings from Jaya Sai or Lokesh in the first 2 weeks.
- **100%** of "Today" KPIs match an independently-computed value for a manually-seeded day.
- **<2 s** time-to-first-meaningful-paint on the Dashboard on a mid-range Android (3G throttle).
- **Lokesh can complete** "record a purchase → see live stock decrement → record sale → see P&L update" without asking for help. (Manual user test.)

---

## 1. Scope

### In scope
Frontend (React 19 + shadcn) + backend (FastAPI + Motor) changes that improve credibility, data accuracy, and mobile usability. All changes are non-breaking to existing schema except where explicitly noted (Wastage requires a new field on `daily_usage`).

### Out of scope (for this PRD)
- Multi-outlet support, PWA offline, i18n (Hindi/Punjabi) — punted to a separate v2 PRD.
- Recipe-to-ingredient auto-decrement — separate PRD (significant data modelling).
- Refresh-token flow rewrite (existing 8h token acceptable for v1).

---

## 2. P0 — Production Credibility Blockers (ship this week)

These three together are dropping the perceived quality of the product by ~30%. All three are <2 hours each.

### P0-1 — Remove "Unknown environment / Railway" warning banner from production UI
**Problem:** A red banner reading *"Unknown environment — DB: unknown — Check your Railway environment variables"* renders on **every page including the login screen** in production. First-time users assume the app is broken.

**User story:** As any user, when I open the app, I should not see internal infrastructure warnings.

**Acceptance criteria:**
- The banner is **never** visible when `process.env.NODE_ENV === 'production'`.
- In dev/preview environments, banner only renders when at least one of `RAILWAY_ENVIRONMENT` / `DB_NAME` / `MONGO_URL` is genuinely missing or returns the literal string `"unknown"`.
- A targeted Playwright test asserts the banner has 0 occurrences in the production build's login + dashboard DOM.

**Files (likely):** `frontend/src/App.js`, or a layout wrapper / `EnvBanner.jsx` (grep for `"Unknown environment"` or `"Railway"`).

**Effort:** 15–30 min.

---

### P0-2 — Fix the Dashboard date (currently shows future date `12-Jun-2026`)
**Problem:** Dashboard header reads `12-Jun-2026` on a system whose actual today is `12-Feb-2026`. Every "Today" KPI, every APScheduler cron job (8AM/10PM IST), and every P&L filter is keyed on this date — so **every "Today" number in the app is currently computed against the wrong day.**

**User story:** As an admin/staff member, I trust that "Today" means today in India.

**Acceptance criteria:**
- Railway deployment env contains `TZ=Asia/Kolkata`.
- All backend `datetime.now()` calls are `datetime.now(timezone.utc)` and converted to IST at the API boundary (per existing `<MongoDB adherence>` rule).
- Dashboard header date matches `date('Asia/Kolkata')` to within 24h on the day the user opens the app.
- APScheduler cron triggers fire at correct IST times (verifiable via notification log timestamps after 1 day in prod).
- Backend test `/app/backend/tests/test_timezone.py` asserts `today_ist()` matches `date.today()` when machine TZ=`Asia/Kolkata`.

**Files (likely):** `backend/core/datetime_utils.py` (create if missing), every router calling `datetime.now()`, Railway env config.

**Effort:** 1–2 hrs (plus 1 deploy cycle to verify).

---

### P0-3 — "PROFIT" badge must not appear on ₹0 P&L
**Problem:** Today P&L card and Overall P&L card both show a green "PROFIT" pill when value === ₹0. Mathematically and semantically wrong — ₹0 is break-even.

**User story:** As an admin viewing P&L, the badge accurately reflects whether the business is in profit, loss, or break-even.

**Acceptance criteria:**
- If `pnl > 0` → green `PROFIT` badge.
- If `pnl < 0` → red `LOSS` badge.
- If `pnl === 0` **and** there has been at least one revenue or expense transaction in the period → neutral grey `BREAK-EVEN` badge.
- If `pnl === 0` **and** no transactions in the period → no badge at all (zero state).
- Same rule applied to Today P&L, Overall P&L, and any future P&L card.

**Files (likely):** `frontend/src/components/Dashboard/` KPI card; centralise into a `<PnLBadge value={...} hasTransactions={...} />` component.

**Effort:** 30 min.

---

## 3. P1 — High-Impact Polish + Data Trust (next week)

### P1-1 — Replace native logo upload with shadcn-styled control
**Acceptance:** Settings → Business Profile logo upload uses a shadcn Button + hidden `<input type=file>` (or a dropzone). Drag-and-drop optional. Preview thumbnail after select. Matches the visual weight of all other form controls.
**File:** `Settings.jsx` business profile tab. **Effort:** 30 min.

### P1-2 — Mobile KPI cards: stop truncating titles
**Acceptance:** No card title is truncated with `…` at 375px viewport. Either (a) shorter mobile copy (`"Total Sales"` instead of `"Total Sales (All Time)"`) with `(All Time)` shown as subtitle, or (b) `truncate` removed and 2-line wrap allowed with `line-clamp-2`.
**File:** KPI card component. **Effort:** 30 min.

### P1-3 — Settings tab strip overflow on mobile
**Acceptance:** Settings tab strip is horizontally scrollable on mobile with a fade indicator. "WhatsApp" tab is fully readable. No tab gets truncated. Use shadcn `ScrollArea` wrapping `Tabs`.
**File:** `Settings.jsx`. **Effort:** 30 min.

### P1-4 — Mobile hamburger drawer click misfire
**Problem:** Earlier testing hit a 3000 ms timeout when tapping "Closing Stock" inside the mobile drawer.
**Hypothesis:** Drawer overlay z-index is below the bottom tab bar, or animation duration prevents the click target from being hit during transition.
**Acceptance:**
- Drawer opens in <300 ms.
- All drawer links are independently tappable (Playwright test taps each and asserts navigation).
- Drawer z-index > bottom tab bar z-index.
**File:** `MobileNav.jsx` / `Sidebar.jsx`. **Effort:** 1 hr.

### P1-5 — Add Alerts to the mobile bottom tab bar
**Rationale:** For a stock-management app, the Alerts (33!) count being one tap away is the entire value prop. Currently buried in the hamburger.
**Acceptance:**
- Bottom tab order: Dashboard · Live Stock · Purchases · **Alerts** · Sales.
- Closing Stock moves to the hamburger drawer.
- Alerts tab shows a numeric badge equal to current alert count.
**File:** `MobileNav.jsx` bottom bar config. **Effort:** 30 min.

### P1-6 — Empty-state for Dashboard charts + Stock Health donut
**Problem:** On day-one with no purchases, the user sees a screaming red donut (33 OOS) and a ghostly empty chart grid. Looks broken.
**Acceptance:**
- If 0 purchases recorded ever → Stock Health donut renders in neutral grey with message "Record your first purchase to see stock health".
- If 0 sales in last 30 days → Daily Sales chart shows empty-state illustration + CTA `Record a sale →`.
- KPI cards with ₹0 and zero transactions show a subtle "—" instead of `₹0` to differentiate "no data" from "zero data".
**File:** `Dashboard.jsx`. **Effort:** 1.5 hrs.

### P1-7 — Edit / undo for purchases, daily usage, expenses
**Rationale:** Lokesh will fat-finger quantities. Currently there is no recovery without DB surgery.
**Acceptance:**
- Each line item in Purchases / Daily Usage / Expenses has an "Edit" and "Delete" action.
- Edit is admin-only; staff can edit only their own entries from the same day; otherwise read-only.
- All edits are logged in an `audit_log` collection (`user_id`, `entity`, `entity_id`, `before`, `after`, `at`).
- A backend test asserts that editing a purchase correctly reverses the stock increment and re-applies the new one.
**Files:** `routers/purchases.py`, `routers/usage.py`, `routers/expenses.py`, corresponding frontend list views. **Effort:** 1 day.

---

## 4. P2 — Missing Operational Features (this month)

### P2-1 — Wastage / spoilage tracking
**Rationale:** Vegetables and dairy spoil. Without a wastage field, COGS is artificially low and live stock is wrong.
**Schema:** Add `wastage_qty` (float, default 0) to `daily_usage` documents. Add `wastage_value_inr` computed at write time using the latest purchase price (or weighted-avg cost) of that item.
**UI:**
- Daily Usage form: add optional "Wastage (qty)" input next to "Qty Used".
- P&L breakdown adds a "Wastage" line under COGS.
- Dashboard adds "Today's Wastage ₹" KPI (collapsible if 0).
**Acceptance:** Backend test seeds 1 purchase + 1 usage with wastage; asserts stock = purchased − used − wastage, and that P&L reflects wastage in COGS.
**Effort:** 1 day.

### P2-2 — CSV / Excel export
**Acceptance:** "Export CSV" button on Purchases, Sales, Expenses, Salaries, and a combined "Export All" on P&L. Server returns `text/csv` with IST-formatted dates. Filename pattern: `spdhaba-{entity}-{YYYY-MM-DD}.csv`.
**Effort:** 3 hrs.

### P2-3 — Daily cash reconciliation screen
**Rationale:** Single biggest fraud/leak point in a dhaba.
**Schema:** New collection `cash_reconciliations` (`date`, `opening_cash`, `closing_cash`, `recorded_sales`, `difference`, `note`, `recorded_by`).
**UI:** New page `Cash Reconciliation` (admin + staff). Form: opening cash, closing cash. Auto-fetches recorded sales for the day. Computes and stores difference. Difference > ₹500 triggers a yellow WhatsApp alert.
**Effort:** 1 day.

### P2-4 — Supplier directory + per-supplier purchase history
**Schema:** New collection `suppliers` (`name`, `phone`, `address`, `payment_terms_days`, `notes`). Add `supplier_id` (optional) to `purchases`.
**UI:** Settings → Suppliers tab (admin). Purchases form gets a Supplier combobox (free-text fallback so existing flow doesn't break). New report: "Pending payable by supplier".
**Effort:** 1 day.

### P2-5 — In-app notification inbox
**Rationale:** WhatsApp logs exist on backend but invisible in UI. Surface them.
**Acceptance:**
- Bell icon in header (desktop + mobile) with unread count.
- Click → sheet/dropdown showing last 20 notifications (low-stock, large-purchase, daily report sent, etc.).
- "Mark all read" action.
- "Retry" action on failed sends (existing backend endpoint).
**File:** `Header.jsx`, new `NotificationInbox.jsx` consuming existing `/api/notifications` endpoint.
**Effort:** 4 hrs.

### P2-6 — Item-level low-stock threshold UI
**Rationale:** Currently global reorder rule. Tomatoes and basmati rice don't have the same threshold.
**Acceptance:** Item Master row has an editable "Reorder Level" field. Live Stock + Alerts honour per-item threshold. Global default stays as fallback.
**Effort:** 3 hrs.

---

## 5. P3 — Future Backlog (next quarter, not committed)

- Hindi/Punjabi UI (i18n) — high impact for Lokesh; bumped from existing P3 backlog to P1 candidate next quarter.
- Recipe-to-ingredient auto-decrement (sell 1 dal → decrement 100g dal, 20g ghee).
- GST / tax toggle on sales (composition scheme).
- Multi-outlet support.
- PWA offline mode.

---

## 6. Cross-cutting requirements

### 6.1 Testing
- Every P0 + P1 item ships with at least one backend test (`/app/backend/tests/`) or Playwright test (`/app/tests/e2e/`).
- A new test file `test_dashboard_math.py` seeds 1 purchase, 1 usage with wastage, 1 sale, 1 expense, 1 salary, and asserts every KPI returns the expected value. **This is the regression net.**

### 6.2 Accessibility
- Every interactive element gets a unique `data-testid` (already a project rule — currently underused).
- Color is never the sole signal — every P&L badge has both color and text label.
- Tap targets on mobile are ≥44×44px (audit bottom tab bar + drawer links).

### 6.3 Performance
- Add shadcn `Skeleton` to all KPI cards and charts so empty paint is never a flash of blank cards.
- Cache `/api/dashboard` server-side for 60 s.

### 6.4 Telemetry (new)
- Add a minimal client-side event log (page_view, action, error) to a `client_events` collection. Required to measure success metrics in §0.

---

## 7. Rollout Plan

| Week | Block | What ships |
|---|---|---|
| W1 | P0 (1–3) + P1-1 + P1-2 + P1-3 | Banner gone, dates correct, P&L badge correct, mobile cards readable, settings tabs scrollable, logo upload styled. |
| W2 | P1-4 + P1-5 + P1-6 + P1-7 | Mobile nav reliable, Alerts in bottom bar, empty states polished, Edit/Undo live. |
| W3 | P2-1 (Wastage) + P2-2 (CSV) + P2-5 (Inbox) | Operational depth + accountability. |
| W4 | P2-3 (Cash recon) + P2-4 (Suppliers) + P2-6 (Per-item reorder) | Fraud-leak closure + vendor mgmt. |

Total: ~4 weeks of one engineer for the entire backlog.

---

## 8. Done definition
A feature is "done" only when:
1. Code merged + deployed to Railway production.
2. Backend test (if applicable) green in CI.
3. Manually verified on a real mobile device (Lokesh's phone if possible).
4. Acceptance criteria in this PRD ticked off.
5. PRD.md updated under "Implementation Log".

---

## 9. Open questions for product owner (Jaya Sai)
1. **Per-item reorder levels (P2-6)** — do we keep the global fallback, or move fully to per-item?
2. **Edit/Undo (P1-7)** — do you want a hard time window (e.g. only edit entries from today) or unlimited edit-back for admin?
3. **Wastage (P2-1)** — should wastage value be costed at last purchase price, or weighted average? (Weighted average is fairer but more compute.)
4. **Cash reconciliation (P2-3)** — daily mandatory close, or optional?
5. **Hindi UI (P3)** — promote to P1? If yes, who owns the translation strings?

---

## 10. Appendix — Source UX audit scores
| Dimension | Current | Target after this PRD |
|---|---|---|
| UX & Usability | 6.0 | 8.5 |
| UI Design | 6.5 | 8.5 |
| Mobile Experience | 5.0 | 8.5 |
| Data Accuracy | 4.5 | 9.0 |
| Missing Features | 5.5 | 8.0 |
| Bugs / Broken UI | 4.0 | 9.0 |
| Performance Feel | 7.0 | 8.0 |
| **Overall** | **5.5** | **8.5** |
