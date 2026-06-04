import asyncio
from datetime import datetime, timedelta
from core.db import db
from core.config import IST


async def compute_stock() -> list:
    """Compute current stock = purchases - usage, per item."""
    items = await db.items.find({}, {"_id": 0}).to_list(2000)
    if not items:
        return []

    # Aggregation: sum purchases per item (excluding voided)
    purchase_agg = db.purchases.aggregate([
        {"$match": {"is_void": {"$ne": True}}},
        {"$group": {"_id": "$item_id", "total": {"$sum": "$quantity"}}}
    ])
    usage_agg = db.daily_usage.aggregate([
        {"$match": {"is_void": {"$ne": True}}},
        {"$group": {"_id": "$item_id", "total": {"$sum": "$quantity_used"}}}
    ])

    purchased, used = {}, {}
    async for doc in purchase_agg:
        purchased[doc["_id"]] = doc["total"]
    async for doc in usage_agg:
        used[doc["_id"]] = doc["total"]

    stock = []
    for item in items:
        iid   = item["id"]
        qty_in  = purchased.get(iid, 0)
        qty_out = used.get(iid, 0)
        qty_left = round(qty_in - qty_out, 3)
        reorder  = item.get("reorder_level", 0)
        status   = "out" if qty_left <= 0 else ("low" if qty_left <= reorder else "in")
        stock.append({**item, "qty_purchased": qty_in, "qty_used": qty_out,
                      "qty_left": qty_left, "status": status})
    return stock


async def get_alerts() -> list:
    """Return items that are low or out of stock."""
    stock = await compute_stock()
    return [s for s in stock if s["is_active"] and s["status"] in ("low", "out")]


async def aggregate_dashboard_data() -> dict:
    """
    Dashboard aggregations using MongoDB pipelines.
    Scalable to any data size — DB does the math, not Python.
    """
    today = datetime.now(IST).strftime("%Y-%m-%d")
    thirty_days_ago = (datetime.now(IST).date() - timedelta(days=29)).isoformat()

    # Run all aggregations in PARALLEL
    (
        purchase_totals,
        sales_totals,
        expense_totals,
        salary_totals,
        today_purchases_agg,
        today_expenses_agg,
        today_sales_doc,
        sales_trend_raw,
        cat_spend_raw,
        exp_cat_raw,
        top_items_raw,
        items_raw,
    ) = await asyncio.gather(
        # Total purchases (all time)
        db.purchases.aggregate([
            {"$match": {"is_void": {"$ne": True}}},
            {"$group": {"_id": None, "total": {"$sum": "$total_cost"}}}
        ]).to_list(1),

        # Total sales (all time)
        db.sales.aggregate([
            {"$group": {"_id": None, "total": {"$sum": "$total_amount"}}}
        ]).to_list(1),

        # Total expenses (all time)
        db.expenses.aggregate([
            {"$match": {"is_void": {"$ne": True}}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]).to_list(1),

        # Total paid salaries (all time)
        db.salaries.aggregate([
            {"$match": {"paid_date": {"$exists": True, "$ne": None}}},
            {"$group": {"_id": None, "total": {"$sum": "$net_payable"}}}
        ]).to_list(1),

        # Today's purchases
        db.purchases.aggregate([
            {"$match": {"is_void": {"$ne": True}, "date": today}},
            {"$group": {"_id": None, "total": {"$sum": "$total_cost"}}}
        ]).to_list(1),

        # Today's expenses
        db.expenses.aggregate([
            {"$match": {"is_void": {"$ne": True}, "date": today}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]).to_list(1),

        # Today's sales
        db.sales.find_one({"date": today}, {"_id": 0}),

        # Sales trend last 30 days
        db.sales.aggregate([
            {"$match": {"date": {"$gte": thirty_days_ago}}},
            {"$group": {"_id": "$date", "amount": {"$sum": "$total_amount"}}},
            {"$sort": {"_id": 1}}
        ]).to_list(30),

        # Category spend
        db.purchases.aggregate([
            {"$match": {"is_void": {"$ne": True}}},
            {"$lookup": {"from": "items", "localField": "item_id",
                         "foreignField": "id", "as": "item"}},
            {"$unwind": {"path": "$item", "preserveNullAndEmptyArrays": True}},
            {"$group": {"_id": {"$ifNull": ["$item.category", "Other"]},
                        "amount": {"$sum": "$total_cost"}}},
            {"$sort": {"amount": -1}},
            {"$limit": 10}
        ]).to_list(10),

        # Expense category breakdown
        db.expenses.aggregate([
            {"$match": {"is_void": {"$ne": True}}},
            {"$group": {"_id": "$category", "amount": {"$sum": "$amount"}}},
            {"$sort": {"amount": -1}},
            {"$limit": 10}
        ]).to_list(10),

        # Top 5 items by purchase cost
        db.purchases.aggregate([
            {"$match": {"is_void": {"$ne": True}}},
            {"$group": {"_id": "$item_id", "amount": {"$sum": "$total_cost"}}},
            {"$sort": {"amount": -1}},
            {"$limit": 5}
        ]).to_list(5),

        # Items lookup (for top items names)
        db.items.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(2000),
    )

    # Extract scalar values
    total_spent    = round(purchase_totals[0]["total"] if purchase_totals else 0, 2)
    total_sales    = round(sales_totals[0]["total"]    if sales_totals    else 0, 2)
    total_expenses = round(expense_totals[0]["total"]  if expense_totals  else 0, 2)
    total_salaries = round(salary_totals[0]["total"]   if salary_totals   else 0, 2)
    profit         = round(total_sales - total_spent - total_expenses - total_salaries, 2)

    today_sales_amount    = today_sales_doc["total_amount"]  if today_sales_doc else 0.0
    today_purchases_amount = round(today_purchases_agg[0]["total"] if today_purchases_agg else 0, 2)
    today_expenses_amount  = round(today_expenses_agg[0]["total"]  if today_expenses_agg  else 0, 2)
    today_pnl             = round(today_sales_amount - today_purchases_amount - today_expenses_amount, 2)

    # Build sales trend for last 30 days (fill missing days with 0)
    sales_by_date = {doc["_id"]: doc["amount"] for doc in sales_trend_raw}
    end_dt   = datetime.now(IST).date()
    start_dt = end_dt - timedelta(days=29)
    trend = [
        {"date": (start_dt + timedelta(days=i)).isoformat(),
         "amount": float(sales_by_date.get((start_dt + timedelta(days=i)).isoformat(), 0))}
        for i in range(30)
    ]

    # Category spend list
    cat_spend_list = [{"category": d["_id"], "amount": round(d["amount"], 2)}
                      for d in cat_spend_raw]

    # Expense category list
    exp_cat_list = [{"category": d["_id"], "amount": round(d["amount"], 2)}
                    for d in exp_cat_raw]

    # Top items with names
    items_map = {i["id"]: i["name"] for i in items_raw}
    top_items_list = [{"name": items_map.get(d["_id"], "Unknown"),
                       "amount": round(d["amount"], 2)} for d in top_items_raw]

    # Stock health (still needs compute_stock — but it's also optimized)
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
        "today_purchases": today_purchases_amount,
        "today_expenses": today_expenses_amount,
        "today_pnl": today_pnl,
        "low_stock_count": health["low"], "out_of_stock_count": health["out"],
        "in_stock_count": health["in"],
        "category_spend": cat_spend_list,
        "expense_categories": exp_cat_list,
        "sales_trend": trend,
        "top_items": top_items_list,
        "recent_alerts": alerts[:5],
        "stock_health": health,
    }
