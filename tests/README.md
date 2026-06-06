# SP Dhaba — UI Testing Agent

End-to-end tests that run like a real user — clicks, fills forms, takes screenshots.

## Setup (one time)

```bash
pip install playwright
playwright install chromium
```

## Run against staging

```bash
python3 tests/ui_agent.py https://spdhaba-stage.up.railway.app
```

## Run against production

```bash
python3 tests/ui_agent.py https://spdhaba-prd.up.railway.app
```

## Run locally

```bash
python3 tests/ui_agent.py http://localhost:3000
```

## Custom credentials (optional)

```bash
ADMIN_EMAIL=admin@spdhaba.com \
ADMIN_PWD=Admin@123 \
STAFF_EMAIL=lokesh@spdhaba.com \
STAFF_PWD=Staff@123 \
python3 tests/ui_agent.py https://spdhaba-stage.up.railway.app
```

## Output

- `tests/screenshots/report.html` — open in browser, shows all tests with screenshots
- `tests/screenshots/*.png` — individual page screenshots

## What it tests

| Suite | Tests |
|---|---|
| Auth | Login page loads, wrong creds rejected, admin/staff/viewer login |
| Navigation | All 12 pages load without errors |
| Purchases | Item dropdown loads, form fills correctly |
| Closing Stock | Progress bar, form interaction |
| Sales | Page loads |
| P&L | Page loads with data |
| Void Dialog | Opens, validates empty reason, cancels |
| Settings | Page loads, all tabs clickable |
| Staff Role | Cannot access dashboard, can access closing stock |
| Viewer Role | Redirects to display, cannot access purchases |
| Mobile View | Login works, bottom nav visible, hamburger drawer opens |
| Staging Banner | Environment banner visible with correct DB name |

## Exit code

- `0` — all tests passed
- `1` — one or more tests failed
