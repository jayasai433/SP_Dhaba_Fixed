"""
CSV exports.

Endpoints:
  GET /api/export/sales.csv?start=YYYY-MM-DD&end=YYYY-MM-DD
  GET /api/export/purchases.csv?start=YYYY-MM-DD&end=YYYY-MM-DD
  GET /api/export/pnl.csv?period=today|week|month|all
                          (or  &start=…&end=…)

Roles:
  Admin + Viewer for sales / pnl
  Admin + Staff   for purchases (staff already sees own purchases via list endpoint)
"""
import io
import csv
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from core.db import db
from core.security import require_roles
from core.utils import today_ist
from services.pnl import compute_pnl, _date_range_for_period

router = APIRouter()


def _csv_response(rows, header, filename):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        w.writerow(r)
    out = io.BytesIO(buf.getvalue().encode("utf-8-sig"))  # BOM → Excel friendly
    return StreamingResponse(
        out,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _range_filter(start: Optional[str], end: Optional[str]) -> dict:
    if not (start or end): return {}
    f = {}
    if start: f["$gte"] = start
    if end:   f["$lte"] = end
    return {"date": f}


@router.get("/export/sales.csv")
async def export_sales_csv(
    start: Optional[str] = None,
    end:   Optional[str] = None,
    user=Depends(require_roles("admin", "viewer")),
):
    q = _range_filter(start, end)
    docs = await db.sales.find(q, {"_id": 0}).sort("date", 1).to_list(20000)
    rows = [
        [d.get("date", ""), d.get("lunch_amount", 0), d.get("dinner_amount", 0),
         d.get("other_amount", 0), d.get("total_amount", 0),
         (d.get("notes") or "").replace("\n", " ")]
        for d in docs
    ]
    fname = f"spdhaba-sales-{start or 'all'}_to_{end or today_ist().isoformat()}.csv"
    return _csv_response(
        rows,
        ["Date", "Lunch ₹", "Dinner ₹", "Other ₹", "Total ₹", "Notes"],
        fname,
    )


@router.get("/export/purchases.csv")
async def export_purchases_csv(
    start: Optional[str] = None,
    end:   Optional[str] = None,
    user=Depends(require_roles("admin", "staff", "viewer")),
):
    q = _range_filter(start, end)
    q["is_void"] = {"$ne": True}
    items = {i["id"]: i for i in await db.items.find({}, {"_id": 0}).to_list(2000)}
    docs = await db.purchases.find(q, {"_id": 0}).sort("date", 1).to_list(20000)
    rows = []
    for d in docs:
        it = items.get(d["item_id"], {})
        rows.append([
            d.get("date", ""),
            it.get("name", "Unknown"),
            it.get("category", ""),
            d.get("quantity", 0),
            it.get("unit", ""),
            d.get("price_per_unit", 0),
            d.get("total_cost", 0),
            d.get("created_by_name", ""),
        ])
    fname = f"spdhaba-purchases-{start or 'all'}_to_{end or today_ist().isoformat()}.csv"
    return _csv_response(
        rows,
        ["Date", "Item", "Category", "Qty", "Unit", "Price/unit ₹", "Total ₹", "Recorded by"],
        fname,
    )


@router.get("/export/pnl.csv")
async def export_pnl_csv(
    period: str = "month",
    start:  Optional[str] = None,
    end:    Optional[str] = None,
    user=Depends(require_roles("admin", "viewer")),
):
    if start or end:
        s, e = start, end
    else:
        s, e = _date_range_for_period(period)
    pnl = await compute_pnl(s, e)
    rows = [
        ["Revenue (Sales)",            pnl["revenue"]],
        ["Cost of Goods (Purchases)", -pnl["cogs"]],
        ["Operating Expenses",        -pnl["expenses"]],
        ["Salaries Paid",             -pnl["salaries"]],
        ["Net Profit / (Loss)",        pnl["net_profit"]],
        ["Margin %",                   pnl["margin_pct"]],
    ]
    fname = f"spdhaba-pnl-{s or 'all'}_to_{e or today_ist().isoformat()}.csv"
    return _csv_response(rows, ["Line item", "Amount ₹"], fname)
