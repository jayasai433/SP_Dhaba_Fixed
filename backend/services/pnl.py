import io
import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi.responses import StreamingResponse

from core.db import db
from core.config import IST

def _date_range_for_period(period: str):
    today = datetime.now(IST).date()
    if period == "today":
        return today.isoformat(), today.isoformat()
    if period == "week":
        start = today - timedelta(days=6)
        return start.isoformat(), today.isoformat()
    if period == "month":
        start = today.replace(day=1)
        return start.isoformat(), today.isoformat()
    if period == "all":
        return None, None
    return today.isoformat(), today.isoformat()

async def compute_pnl(start: Optional[str], end: Optional[str]) -> dict:
    import asyncio
    # Build date filter
    date_match: dict = {}
    if start: date_match["$gte"] = start
    if end:   date_match["$lte"] = end

    purchase_match  = {"is_void": {"$ne": True}}
    sales_match: dict     = {}
    expenses_match  = {"is_void": {"$ne": True}}
    salaries_match  = {"paid_date": {"$exists": True, "$ne": None}}

    if date_match:
        purchase_match["date"]  = date_match
        sales_match["date"]     = date_match
        expenses_match["date"]  = date_match
        salaries_match["paid_date"] = date_match

    # All aggregations in parallel — scalable to any data volume
    pur_agg, sal_agg, exp_agg, salary_agg = await asyncio.gather(
        db.purchases.aggregate([
            {"$match": purchase_match},
            {"$group": {"_id": None, "total": {"$sum": "$total_cost"}}}
        ]).to_list(1),
        db.sales.aggregate([
            {"$match": sales_match},
            {"$group": {"_id": None, "total": {"$sum": "$total_amount"}}}
        ]).to_list(1),
        db.expenses.aggregate([
            {"$match": expenses_match},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]).to_list(1),
        db.salaries.aggregate([
            {"$match": salaries_match},
            {"$group": {"_id": None, "total": {"$sum": "$net_payable"}}}
        ]).to_list(1),
    )

    rev  = round(sal_agg[0]["total"]    if sal_agg    else 0, 2)
    cogs = round(pur_agg[0]["total"]    if pur_agg    else 0, 2)
    exp  = round(exp_agg[0]["total"]    if exp_agg    else 0, 2)
    sal  = round(salary_agg[0]["total"] if salary_agg else 0, 2)
    net  = round(rev - cogs - exp - sal, 2)

    return {"start": start, "end": end, "revenue": rev, "cogs": cogs,
            "expenses": exp, "salaries": sal, "net_profit": net,
            "margin_pct": round((net / rev * 100) if rev else 0, 1)}

async def compute_pnl_trend(days: int) -> list:
    """
    Build a daily P&L trend using MongoDB $group aggregations — O(1) data transfer
    regardless of document count. Previously fetched up to 14,000 docs into memory
    and looped in Python; now each collection does one aggregation in the DB.
    """
    import asyncio

    end_dt   = datetime.now(IST).date()
    start_dt = end_dt - timedelta(days=days - 1)
    start_s  = start_dt.isoformat()
    end_s    = end_dt.isoformat()

    # Run all four aggregations concurrently
    sales_agg, pur_agg, exp_agg, sal_agg = await asyncio.gather(
        db.sales.aggregate([
            {"$match": {"date": {"$gte": start_s, "$lte": end_s}}},
            {"$group": {"_id": "$date", "revenue": {"$sum": "$total_amount"}}},
        ]).to_list(days + 5),

        db.purchases.aggregate([
            {"$match": {"is_void": {"$ne": True}, "date": {"$gte": start_s, "$lte": end_s}}},
            {"$group": {"_id": "$date", "cogs": {"$sum": "$total_cost"}}},
        ]).to_list(days + 5),

        db.expenses.aggregate([
            {"$match": {"is_void": {"$ne": True}, "date": {"$gte": start_s, "$lte": end_s}}},
            {"$group": {"_id": "$date", "expenses": {"$sum": "$amount"}}},
        ]).to_list(days + 5),

        db.salaries.aggregate([
            {"$match": {"paid_date": {"$gte": start_s, "$lte": end_s, "$exists": True, "$ne": None}}},
            {"$group": {"_id": "$paid_date", "salaries": {"$sum": "$net_payable"}}},
        ]).to_list(days + 5),
    )

    # Index results by date for O(1) lookup — no Python-level looping over raw docs
    rev_map = {r["_id"]: r["revenue"]  for r in sales_agg}
    cog_map = {r["_id"]: r["cogs"]     for r in pur_agg}
    exp_map = {r["_id"]: r["expenses"] for r in exp_agg}
    sal_map = {r["_id"]: r["salaries"] for r in sal_agg}

    trend = []
    for i in range(days):
        d   = (start_dt + timedelta(days=i)).isoformat()
        rev = rev_map.get(d, 0)
        cog = cog_map.get(d, 0)
        exp = exp_map.get(d, 0)
        sal = sal_map.get(d, 0)
        trend.append({
            "date":     d,
            "revenue":  round(rev, 2),
            "cogs":     round(cog, 2),
            "expenses": round(exp, 2),
            "salaries": round(sal, 2),
            "net":      round(rev - cog - exp - sal, 2),
        })
    return trend

async def export_pnl_pdf(period: str) -> StreamingResponse:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.units import cm

    s, e  = _date_range_for_period(period)
    pnl   = await compute_pnl(s, e)
    biz   = await db.business_profile.find_one({"key": "main"}, {"_id": 0}) or {}

    buf    = io.BytesIO()
    doc    = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm,
                               topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    h_style = ParagraphStyle("h", parent=styles["Heading1"],
                             textColor=colors.HexColor("#E65C00"))
    elements = []
    elements.append(Paragraph(biz.get("name", "SP Royal Punjabi Family Dhaba"), h_style))
    elements.append(Paragraph(f"Profit & Loss Statement — {period.title()}", styles["Heading2"]))
    elements.append(Paragraph(
        f"Period: {pnl.get('start') or 'All time'} to {pnl.get('end') or 'today'}",
        styles["Normal"]))
    elements.append(Spacer(1, 0.5*cm))

    data = [
        ["Item", "Amount (INR)"],
        ["Revenue (Sales)",             f"₹{pnl['revenue']:,.2f}"],
        ["Cost of Goods (Purchases)",   f"-₹{pnl['cogs']:,.2f}"],
        ["Operating Expenses",          f"-₹{pnl['expenses']:,.2f}"],
        ["Salaries Paid",               f"-₹{pnl['salaries']:,.2f}"],
        ["Net Profit / (Loss)",         f"₹{pnl['net_profit']:,.2f}"],
    ]
    t = Table(data, colWidths=[10*cm, 6*cm])
    is_profit = pnl["net_profit"] >= 0
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0),  colors.HexColor("#E65C00")),
        ("TEXTCOLOR",  (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",   (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, -1), (-1, -1),
         colors.HexColor("#E8F5E9") if is_profit else colors.HexColor("#FFEBEE")),
        ("FONTNAME",   (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",   (0, -1), (-1, -1), 12),
        ("ALIGN",      (1, 0),  (1, -1),  "RIGHT"),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph(
        f"<i>Generated on {datetime.now(IST).strftime('%d-%b-%Y %H:%M IST')}</i>",
        styles["Normal"]))
    doc.build(elements)
    buf.seek(0)

    return StreamingResponse(
        buf, media_type="application/pdf",
        headers={"Content-Disposition":
                 f'attachment; filename="pnl-{period}-{datetime.now(IST).strftime("%Y%m%d")}.pdf"'},
    )
