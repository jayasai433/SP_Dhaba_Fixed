"""
SP Dhaba Telegram Bot for Lokesh
Commands: /start /help /stock /purchase /sales /expense /status /cancel
"""

import os
import time
import logging
import httpx
from datetime import datetime, timezone, timedelta
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters,
)

BOT_TOKEN       = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED_CHAT_ID = int(os.environ["ALLOWED_CHAT_ID"])
BACKEND_URL     = os.environ["BACKEND_URL"].rstrip("/")
STAFF_EMAIL     = os.environ["STAFF_EMAIL"]
STAFF_PASSWORD  = os.environ["STAFF_PASSWORD"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Auth — class-based so caching works reliably ──────────────────────────────
class Auth:
    def __init__(self):
        self.token = ""
        self.expiry = 0.0

_auth = Auth()

async def get_token() -> str:
    if _auth.token and time.time() < _auth.expiry:
        return _auth.token
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            f"{BACKEND_URL}/api/auth/login",
            json={"email": STAFF_EMAIL, "password": STAFF_PASSWORD}
        )
        r.raise_for_status()
        _auth.token = r.json()["token"]
        _auth.expiry = time.time() + 6 * 3600
        logger.info("JWT refreshed")
        return _auth.token

async def api(method: str, path: str, **kwargs):
    token = await get_token()
    headers = {"Authorization": "Bearer " + token}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await getattr(client, method)(
            BACKEND_URL + "/api" + path,
            headers=headers,
            **kwargs
        )
        if not r.is_success:
            try:
                detail = r.json().get("detail", "Error " + str(r.status_code))
            except Exception:
                detail = "Error " + str(r.status_code)
            raise ValueError(detail)
        return r.json()

# ── Helpers ───────────────────────────────────────────────────────────────────
def ist_today() -> str:
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist).strftime("%Y-%m-%d")

def ist_yesterday() -> str:
    ist = timezone(timedelta(hours=5, minutes=30))
    return (datetime.now(ist) - timedelta(days=1)).strftime("%Y-%m-%d")

def authorized(update: Update) -> bool:
    return update.effective_chat.id == ALLOWED_CHAT_ID

async def deny(update: Update):
    await update.message.reply_text("Unauthorized.")

def make_keyboard(options: list, cols: int = 2) -> ReplyKeyboardMarkup:
    rows = [options[i:i+cols] for i in range(0, len(options), cols)]
    return ReplyKeyboardMarkup(rows, one_time_keyboard=True, resize_keyboard=True)

def fmt(amount: float) -> str:
    return "Rs " + "{:,.0f}".format(amount)

# ── Conversation states (unique integers) ─────────────────────────────────────
S_ITEM, S_QTY, S_NOTES          = 1, 2, 3
P_ITEM, P_QTY, P_PRICE, P_DATE  = 11, 12, 13, 14
SL_LUNCH, SL_DINNER, SL_OTHER   = 21, 22, 23
E_CAT, E_DESC, E_AMT             = 31, 32, 33

HELP = (
    "SP Dhaba Bot\n\n"
    "Commands:\n"
    "/stock    Record closing stock count\n"
    "/purchase Record a purchase\n"
    "/sales    Record today sales\n"
    "/expense  Record an expense\n"
    "/status   Today summary\n"
    "/cancel   Cancel current action\n\n"
    "I will ask you one question at a time.\n"
    "Buttons will appear where possible.\n"
    "Type /cancel anytime to stop."
)

# ── /start /help ──────────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return await deny(update)
    await update.message.reply_text(HELP)

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return await deny(update)
    await update.message.reply_text(HELP)

# ── /status ───────────────────────────────────────────────────────────────────
async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return await deny(update)
    await update.message.reply_text("Fetching today summary...")
    try:
        d = await api("get", "/dashboard")
        sales = d.get("today_sales", 0)
        exp   = d.get("today_expenses", 0)
        pnl   = d.get("today_pnl", 0)
        low   = d.get("low_stock_count", 0)
        out   = d.get("out_of_stock_count", 0)
        sign  = "PROFIT" if pnl >= 0 else "LOSS"
        lines = [
            "Today - " + ist_today(),
            "",
            "Sales:    " + fmt(sales),
            "Expenses: " + fmt(exp),
            sign + ":    " + fmt(abs(pnl)),
            "",
            "Low stock:    " + str(low) + " items",
            "Out of stock: " + str(out) + " items",
        ]
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text("Failed: " + str(e)[:100])

# ── /cancel ───────────────────────────────────────────────────────────────────
async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return await deny(update)
    ctx.user_data.clear()
    await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def cmd_unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return await deny(update)
    await update.message.reply_text("Unknown command. Type /help")

# ══════════════════════════════════════════════════════════════════════════════
# CLOSING STOCK
# ══════════════════════════════════════════════════════════════════════════════

async def stock_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return await deny(update)
    try:
        items = await api("get", "/items")
        active = [i for i in items if i.get("is_active", True)]
        ctx.user_data["item_map"] = {i["name"]: i for i in active}
        names = [i["name"] for i in active]
        await update.message.reply_text(
            "Which item did you count?",
            reply_markup=make_keyboard(names)
        )
        return S_ITEM
    except Exception as e:
        await update.message.reply_text("Error: " + str(e)[:100])
        return ConversationHandler.END

async def stock_item(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    item_map = ctx.user_data.get("item_map", {})
    # Exact match first, then partial
    item = item_map.get(name)
    if not item:
        item = next((v for k, v in item_map.items() if name.lower() in k.lower()), None)
    if not item:
        await update.message.reply_text("Not found. Please pick from the list.")
        return S_ITEM
    ctx.user_data["item"] = item
    await update.message.reply_text(
        "How many " + item["unit"] + " of " + item["name"] + " are left on shelf?\n"
        "Example: 7",
        reply_markup=ReplyKeyboardRemove()
    )
    return S_QTY

async def stock_qty(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        qty = float(update.message.text.strip())
        if qty < 0:
            await update.message.reply_text("Cannot be negative. Enter shelf count:")
            return S_QTY
        ctx.user_data["qty"] = qty
        await update.message.reply_text(
            "Any notes? (e.g. spillage, moved to fridge)\n"
            "Or type: skip"
        )
        return S_NOTES
    except ValueError:
        await update.message.reply_text("Please enter a number. Example: 7")
        return S_QTY

async def stock_notes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    notes = "" if update.message.text.strip().lower() == "skip" else update.message.text.strip()
    item = ctx.user_data["item"]
    qty  = ctx.user_data["qty"]
    try:
        result = await api("post", "/closing-stock", json={
            "date": ist_today(),
            "item_id": item["id"],
            "closing_qty": qty,
            "notes": notes
        })
        consumed = result.get("consumed", "?")
        lines = [
            "Closing Stock Saved",
            "",
            "Item: " + item["name"],
            "Closing: " + str(qty) + " " + item["unit"],
            "Consumed today: " + str(consumed) + " " + item["unit"],
        ]
        if notes:
            lines.append("Notes: " + notes)
        await update.message.reply_text("\n".join(lines))
    except Exception as e:
        await update.message.reply_text("Error: " + str(e)[:100])
    return ConversationHandler.END

# ══════════════════════════════════════════════════════════════════════════════
# PURCHASE
# ══════════════════════════════════════════════════════════════════════════════

async def purchase_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return await deny(update)
    try:
        items = await api("get", "/items")
        active = [i for i in items if i.get("is_active", True)]
        ctx.user_data["item_map"] = {i["name"]: i for i in active}
        names = [i["name"] for i in active]
        await update.message.reply_text(
            "Which item did you buy?",
            reply_markup=make_keyboard(names)
        )
        return P_ITEM
    except Exception as e:
        await update.message.reply_text("Error: " + str(e)[:100])
        return ConversationHandler.END

async def purchase_item(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    item_map = ctx.user_data.get("item_map", {})
    item = item_map.get(name)
    if not item:
        item = next((v for k, v in item_map.items() if name.lower() in k.lower()), None)
    if not item:
        await update.message.reply_text("Not found. Please pick from the list.")
        return P_ITEM
    ctx.user_data["item"] = item
    await update.message.reply_text(
        "How many " + item["unit"] + " of " + item["name"] + " did you buy?\n"
        "Example: 10",
        reply_markup=ReplyKeyboardRemove()
    )
    return P_QTY

async def purchase_qty(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        qty = float(update.message.text.strip())
        if qty <= 0:
            await update.message.reply_text("Must be more than 0. Enter quantity:")
            return P_QTY
        ctx.user_data["qty"] = qty
        item = ctx.user_data["item"]
        await update.message.reply_text(
            "Price per " + item["unit"] + " in rupees?\n"
            "Example: 200"
        )
        return P_PRICE
    except ValueError:
        await update.message.reply_text("Please enter a number. Example: 10")
        return P_QTY

async def purchase_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.strip())
        if price <= 0:
            await update.message.reply_text("Must be more than 0. Enter price:")
            return P_PRICE
        ctx.user_data["price"] = price
        item  = ctx.user_data["item"]
        qty   = ctx.user_data["qty"]
        total = qty * price
        await update.message.reply_text(
            "Summary:\n"
            "Item: " + item["name"] + "\n"
            "Qty: " + str(qty) + " " + item["unit"] + " x Rs " + str(int(price)) + "\n"
            "Total: " + fmt(total) + "\n\n"
            "When did you buy this?",
            reply_markup=make_keyboard(["Today", "Yesterday"])
        )
        return P_DATE
    except ValueError:
        await update.message.reply_text("Please enter a number. Example: 200")
        return P_PRICE

async def purchase_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    if text == "today":
        date = ist_today()
    elif text == "yesterday":
        date = ist_yesterday()
    else:
        try:
            datetime.strptime(text, "%Y-%m-%d")
            date = text
        except ValueError:
            await update.message.reply_text(
                "Please say Today or Yesterday.",
                reply_markup=make_keyboard(["Today", "Yesterday"])
            )
            return P_DATE
    item  = ctx.user_data["item"]
    qty   = ctx.user_data["qty"]
    price = ctx.user_data["price"]
    try:
        await api("post", "/purchases", json={
            "item_id": item["id"],
            "quantity": qty,
            "price_per_unit": price,
            "date": date,
            "notes": "Via Telegram"
        })
        lines = [
            "Purchase Saved",
            "",
            "Item: " + item["name"],
            "Qty: " + str(qty) + " " + item["unit"] + " x Rs " + str(int(price)),
            "Total: " + fmt(qty * price),
            "Date: " + date,
        ]
        await update.message.reply_text(
            "\n".join(lines),
            reply_markup=ReplyKeyboardRemove()
        )
    except Exception as e:
        await update.message.reply_text(
            "Error: " + str(e)[:100],
            reply_markup=ReplyKeyboardRemove()
        )
    return ConversationHandler.END

# ══════════════════════════════════════════════════════════════════════════════
# SALES
# ══════════════════════════════════════════════════════════════════════════════

async def sales_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return await deny(update)
    await update.message.reply_text(
        "Sales for " + ist_today() + "\n\n"
        "Lunch sales in Rs? (enter 0 if none)\n"
        "Example: 5000",
        reply_markup=ReplyKeyboardRemove()
    )
    return SL_LUNCH

async def sales_lunch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        ctx.user_data["lunch"] = float(update.message.text.strip())
        await update.message.reply_text(
            "Dinner sales in Rs? (enter 0 if none)\n"
            "Example: 4000"
        )
        return SL_DINNER
    except ValueError:
        await update.message.reply_text("Please enter a number. Example: 5000")
        return SL_LUNCH

async def sales_dinner(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        ctx.user_data["dinner"] = float(update.message.text.strip())
        await update.message.reply_text(
            "Other sales in Rs? (snacks, takeaway, etc. Enter 0 if none)\n"
            "Example: 500"
        )
        return SL_OTHER
    except ValueError:
        await update.message.reply_text("Please enter a number. Example: 4000")
        return SL_DINNER

async def sales_other(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        other  = float(update.message.text.strip())
        lunch  = ctx.user_data["lunch"]
        dinner = ctx.user_data["dinner"]
        total  = lunch + dinner + other
        try:
            await api("post", "/sales", json={
                "date": ist_today(),
                "lunch_amount":  lunch,
                "dinner_amount": dinner,
                "other_amount":  other,
                "notes": ""
            })
            lines = [
                "Sales Saved",
                "",
                "Lunch:  " + fmt(lunch),
                "Dinner: " + fmt(dinner),
                "Other:  " + fmt(other),
                "Total:  " + fmt(total),
            ]
            await update.message.reply_text("\n".join(lines))
        except Exception as e:
            await update.message.reply_text("Error: " + str(e)[:100])
    except ValueError:
        await update.message.reply_text("Please enter a number. Example: 500")
        return SL_OTHER
    return ConversationHandler.END

# ══════════════════════════════════════════════════════════════════════════════
# EXPENSE
# ══════════════════════════════════════════════════════════════════════════════

async def expense_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return await deny(update)
    try:
        cats = await api("get", "/expense-categories")
        names = [c["name"] for c in cats if c.get("is_active", True)]
        markup = make_keyboard(names) if names else ReplyKeyboardRemove()
        await update.message.reply_text("Expense category?", reply_markup=markup)
    except Exception:
        await update.message.reply_text(
            "Expense category?\nExample: Gas, Electricity, Transport",
            reply_markup=ReplyKeyboardRemove()
        )
    return E_CAT

async def expense_cat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["cat"] = update.message.text.strip()
    await update.message.reply_text(
        "Description?\nExample: Gas cylinder refill",
        reply_markup=ReplyKeyboardRemove()
    )
    return E_DESC

async def expense_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["desc"] = update.message.text.strip()
    await update.message.reply_text("Amount in Rs?\nExample: 1200")
    return E_AMT

async def expense_amt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            await update.message.reply_text("Must be more than 0. Enter amount:")
            return E_AMT
        cat  = ctx.user_data["cat"]
        desc = ctx.user_data["desc"]
        await api("post", "/expenses", json={
            "date": ist_today(),
            "category": cat,
            "description": desc,
            "amount": amount
        })
        lines = [
            "Expense Saved",
            "",
            "Category: " + cat,
            "Description: " + desc,
            "Amount: " + fmt(amount),
        ]
        await update.message.reply_text("\n".join(lines))
    except ValueError:
        await update.message.reply_text("Please enter a number. Example: 1200")
        return E_AMT
    except Exception as e:
        await update.message.reply_text("Error: " + str(e)[:100])
    return ConversationHandler.END

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    stock_conv = ConversationHandler(
        entry_points=[CommandHandler("stock", stock_start)],
        states={
            S_ITEM:  [MessageHandler(filters.TEXT & ~filters.COMMAND, stock_item)],
            S_QTY:   [MessageHandler(filters.TEXT & ~filters.COMMAND, stock_qty)],
            S_NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, stock_notes)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        allow_reentry=True,
    )

    purchase_conv = ConversationHandler(
        entry_points=[CommandHandler("purchase", purchase_start)],
        states={
            P_ITEM:  [MessageHandler(filters.TEXT & ~filters.COMMAND, purchase_item)],
            P_QTY:   [MessageHandler(filters.TEXT & ~filters.COMMAND, purchase_qty)],
            P_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, purchase_price)],
            P_DATE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, purchase_date)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        allow_reentry=True,
    )

    sales_conv = ConversationHandler(
        entry_points=[CommandHandler("sales", sales_start)],
        states={
            SL_LUNCH:  [MessageHandler(filters.TEXT & ~filters.COMMAND, sales_lunch)],
            SL_DINNER: [MessageHandler(filters.TEXT & ~filters.COMMAND, sales_dinner)],
            SL_OTHER:  [MessageHandler(filters.TEXT & ~filters.COMMAND, sales_other)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        allow_reentry=True,
    )

    expense_conv = ConversationHandler(
        entry_points=[CommandHandler("expense", expense_start)],
        states={
            E_CAT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_cat)],
            E_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_desc)],
            E_AMT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_amt)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("help",     cmd_help))
    app.add_handler(CommandHandler("status",   cmd_status))
    app.add_handler(stock_conv)
    app.add_handler(purchase_conv)
    app.add_handler(sales_conv)
    app.add_handler(expense_conv)
    app.add_handler(MessageHandler(filters.COMMAND, cmd_unknown))

    logger.info("SP Dhaba Bot started")
    # drop_pending_updates=True prevents old messages replaying on restart
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
