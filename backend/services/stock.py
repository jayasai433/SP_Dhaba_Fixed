from datetime import datetime, timedelta
from core.db import db
from core.config import IST

# ── Stock calculation ─────────────────────────────────────────────────────
async def compute_stock() -> list:
    items = await db.items.find({}, {"_id": 0}).to_list(2000)
    p_agg = await db.purchases.aggregate([
        {"$match": {"is_void": {"$ne": True}}},
        {"$group": {"_id": "$item_id", "total": {"$sum": "$quantity"}}}
    ]).to_list(5000)
    u_agg = await db.daily_usage.aggregate([
        {"$match": {"is_void": {"$ne": True}}},
        {"$group": {"_id": "$item_id", "total": {"$sum": "$quantity_used"}}}
    ]).to_list(5000)
    p_map = {x["_id"]: x["total"] for x in p_agg}
    u_map = {x["_id"]: x["total"] for x in u_agg}
    out = []
    for it in items:
        bought  = float(p_map.get(it["id"], 0))
        used    = float(u_map.get(it["id"], 0))
        left    = round(bought - used, 3)
        reorder = float(it.get("reorder_level", 0))
        if left <= 0:
            stat = "out"
        elif left <= reorder:
            stat = "low"
        else:
            stat = "in"
        out.append({
            "item_id": it["id"], "name": it["name"], "category": it["category"],
            "unit": it["unit"], "reorder_level": reorder,
            "total_bought": round(bought, 3), "total_used": round(used, 3),
            "qty_left": left, "status": stat, "is_active": it.get("is_active", True),
        })
    return out

# ── Alerts ────────────────────────────────────────────────────────────────
async def get_alerts() -> list:
    stock  = await compute_stock()
    alerts = [s for s in stock if s["status"] in ("low", "out") and s["is_active"]]
    alerts.sort(key=lambda x: (0 if x["status"] == "out" else 1, x["name"]))
    return alerts

# ── Dashboard aggregation ─────────────────────────────────────────────────
async def aggregate_dashboard_data() -> dict:
    purchases     = await db.purchases.find({"is_void": {"$ne": True}}, {"_id": 0}).to_list(5000)
    sales         = await db.sales.find({}, {"_id": 0}).to_list(5000)
    expenses_docs = await db.expenses.find({"is_void": {"$ne": True}}, {"_id": 0}).to_list(5000)
    salary_docs   = await db.salaries.find({}, {"_id": 0}).to_list(5000)
    items         = {i["id"]: i for i in await db.items.find({}, {"_id": 0}).to_list(2000)}

    total_spent    = round(sum(p["total_cost"]  for p in purchases), 2)
    total_sales    = round(sum(s["total_amount"] for s in sales), 2)
    total_expenses = round(sum(e["amount"]       for e in expenses_docs), 2)
    total_salaries = round(sum(s.get("net_payable", 0) for s in salary_docs if s.get("paid_date")), 2)
    profit         = round(total_sales - total_spent - total_expenses - total_salaries, 2)

    today                 = datetime.now(IST).strftime("%Y-%m-%d")
    today_sales           = next((s for s in sales if s["date"] == today), None)
    today_sales_amount    = today_sales["total_amount"] if today_sales else 0.0
    today_purchases_amount = sum(p["total_cost"] for p in purchases if p["date"] == today)
    today_expenses_amount  = sum(e["amount"]     for e in expenses_docs if e["date"] == today)
    today_pnl             = round(today_sales_amount - today_purchases_amount - today_expenses_amount, 2)

    # Category-wise purchase spend
    cat_spend = {}
    for p in purchases:
        cat = items.get(p["item_id"], {}).get("category", "Other")
        cat_spend[cat] = cat_spend.get(cat, 0) + p["total_cost"]
    cat_spend_list = sorted(
        [{"category": k, "amount": round(v, 2)} for k, v in cat_spend.items()],
        key=lambda x: -x["amount"]
    )

    # Expense category breakdown
    exp_cat = {}
    for e in expenses_docs:
        exp_cat[e["category"]] = exp_cat.get(e["category"], 0) + e["amount"]
    exp_cat_list = sorted(
        [{"category": k, "amount": round(v, 2)} for k, v in exp_cat.items()],
        key=lambda x: -x["amount"]
    )

    # Daily sales trend (last 30 days)
    end_dt      = datetime.now(IST).date()
    start_dt    = end_dt - timedelta(days=29)
    sales_by_date = {s["date"]: s["total_amount"] for s in sales}
    trend = [
        {"date": (start_dt + timedelta(days=i)).isoformat(),
         "amount": float(sales_by_date.get((start_dt + timedelta(days=i)).isoformat(), 0))}
        for i in range(30)
    ]

    # Top 5 items by cost
    item_cost = {}
    for p in purchases:
        item_cost[p["item_id"]] = item_cost.get(p["item_id"], 0) + p["total_cost"]
    top_items_list = [
        {"name": items.get(iid, {}).get("name", "Unknown"), "amount": round(amt, 2)}
        for iid, amt in sorted(item_cost.items(), key=lambda x: -x[1])[:5]
    ]

    # Stock health
    stock  = await compute_stock()
    health = {"in": 0, "low": 0, "out": 0}
    for s in stock:
        if s["is_active"]:
            health[s["status"]] += 1
    alerts = [s for s in stock if s["status"] in ("low", "out") and s["is_active"]]

    return {
        "total_spent": total_spent, "total_sales": total_sales,
        "total_expenses": total_expenses, "total_salaries": total_salaries,
        "profit": profit,
        "today_sales": today_sales_amount,
        "today_purchases": round(today_purchases_amount, 2),
        "today_expenses": round(today_expenses_amount, 2),
        "today_pnl": today_pnl,
        "low_stock_count": health["low"], "out_of_stock_count": health["out"],
        "category_spend": cat_spend_list,
        "expense_category_spend": exp_cat_list,
        "sales_trend": trend,
        "top_items": top_items_list,
        "stock_health": health,
        "alerts_count": len(alerts),
    }
