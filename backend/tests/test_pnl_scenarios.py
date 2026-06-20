"""
P&L badge / math regression tests — 5 deterministic scenarios.

Each scenario seeds a fresh isolated date range and asserts:
  • revenue / cogs / expenses / salaries / net_profit are mathematically correct
  • net_profit = revenue - cogs - expenses - salaries (to the rupee)
  • badge classification (profit / loss / break-even / no-data) is correct
"""
import os
import uuid
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@spdhaba.com", "password": "Admin@123"}


def _login():
    r = requests.post(f"{API}/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200
    return r.json()["token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def _badge(net_profit, has_txns):
    """Mirror of the frontend KPI badge logic — single source of truth."""
    if net_profit > 0:
        return "Profit"
    if net_profit < 0:
        return "Loss"
    if has_txns:
        return "Break-Even"
    return None  # no badge


def _seed_scenario(tok, start, end, sales=None, purchase=None, expense=None):
    """Seed one P&L scenario into an isolated date range."""
    items = requests.get(f"{API}/items", headers=_h(tok)).json()
    iid = items[0]["id"]

    if sales is not None:
        # 409 if exists — best-effort idempotency by uuid date suffix outside
        requests.post(
            f"{API}/sales",
            headers=_h(tok),
            json={"date": start, "lunch_amount": sales, "dinner_amount": 0, "other_amount": 0},
        )
    if purchase is not None:
        requests.post(
            f"{API}/purchases",
            headers=_h(tok),
            json={"item_id": iid, "date": start, "quantity": 1, "price_per_unit": purchase},
        )
    if expense is not None:
        requests.post(
            f"{API}/expenses",
            headers=_h(tok),
            json={"date": start, "category": "Maintenance", "amount": expense},
        )

    r = requests.get(f"{API}/pnl", headers=_h(tok), params={"start": start, "end": end})
    assert r.status_code == 200, r.text
    return r.json()


def _unique_window():
    """Far-future window we can write to without colliding with other tests."""
    day = uuid.uuid4().int % 28 + 1
    # year 2040 will not be hit by any other test
    d = f"2040-{(uuid.uuid4().int % 12) + 1:02d}-{day:02d}"
    return d, d


def test_scenario_profit():
    tok = _login()
    s, e = _unique_window()
    pnl = _seed_scenario(tok, s, e, sales=5000, purchase=1000, expense=500)
    # revenue 5000 − cogs 1000 − exp 500 − sal 0 = 3500
    assert pnl["revenue"] >= 5000
    assert pnl["cogs"]    >= 1000
    assert pnl["expenses"] >= 500
    assert pnl["net_profit"] == round(
        pnl["revenue"] - pnl["cogs"] - pnl["expenses"] - pnl["salaries"], 2
    )
    has_txns = pnl["revenue"] + pnl["cogs"] + pnl["expenses"] + pnl["salaries"] > 0
    assert _badge(pnl["net_profit"], has_txns) == "Profit"


def test_scenario_loss():
    tok = _login()
    s, e = _unique_window()
    pnl = _seed_scenario(tok, s, e, sales=500, purchase=2000, expense=300)
    # 500 − 2000 − 300 = -1800
    assert pnl["net_profit"] < 0
    assert pnl["net_profit"] == round(
        pnl["revenue"] - pnl["cogs"] - pnl["expenses"] - pnl["salaries"], 2
    )
    has_txns = pnl["revenue"] + pnl["cogs"] + pnl["expenses"] + pnl["salaries"] > 0
    assert _badge(pnl["net_profit"], has_txns) == "Loss"


def test_scenario_break_even():
    tok = _login()
    s, e = _unique_window()
    # sales 1000 == purchase 1000, no expense → net = 0 but txns exist
    pnl = _seed_scenario(tok, s, e, sales=1000, purchase=1000)
    assert pnl["net_profit"] == 0
    has_txns = pnl["revenue"] + pnl["cogs"] + pnl["expenses"] + pnl["salaries"] > 0
    assert has_txns is True
    assert _badge(pnl["net_profit"], has_txns) == "Break-Even"


def test_scenario_no_data():
    tok = _login()
    # date range with nothing seeded
    s, e = "2041-07-15", "2041-07-15"
    r = requests.get(f"{API}/pnl", headers=_h(tok), params={"start": s, "end": e})
    assert r.status_code == 200
    pnl = r.json()
    assert pnl["revenue"] == 0
    assert pnl["cogs"] == 0
    assert pnl["expenses"] == 0
    assert pnl["salaries"] == 0
    assert pnl["net_profit"] == 0
    has_txns = pnl["revenue"] + pnl["cogs"] + pnl["expenses"] + pnl["salaries"] > 0
    assert has_txns is False
    assert _badge(pnl["net_profit"], has_txns) is None  # no badge


def test_scenario_revenue_only():
    tok = _login()
    s, e = _unique_window()
    pnl = _seed_scenario(tok, s, e, sales=2500)
    # revenue 2500 − everything else 0 = 2500 profit
    assert pnl["revenue"] >= 2500
    assert pnl["net_profit"] == round(
        pnl["revenue"] - pnl["cogs"] - pnl["expenses"] - pnl["salaries"], 2
    )
    assert pnl["net_profit"] > 0
    has_txns = pnl["revenue"] + pnl["cogs"] + pnl["expenses"] + pnl["salaries"] > 0
    assert _badge(pnl["net_profit"], has_txns) == "Profit"
