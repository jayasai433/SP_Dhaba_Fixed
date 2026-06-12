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

# ── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN       = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED_CHAT_ID = int(os.environ["ALLOWED_CHAT_ID"])
BACKEND_URL     = os.environ["BACKEND_URL"].rstrip("/")
STAFF_EMAIL     = os.environ["STAFF_EMAIL"]
STAFF_PASSWORD  = os.environ["STAFF_PASSWORD"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Auth ──────────────────────────────────────────────────────────────────────
_token = ""
_token_expiry = 0.0

async def get_token() -> str:
    global _token, _token_expiry
    if _token and time.time() < _token_expiry:
        return _token
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(
            f"{BACKEND_URL}/api/auth/login",
            json={"email": STAFF_EMAIL, "password": STAFF_PASSWORD}
        )
        r.raise_for_status()
        _token = r.json()["token"]
        _token_expiry = time.time() + 6 * 3600
        logger.info("JWT refreshed")
        return _token

async def call(method: str, path: str, **kwargs) -> dict:
    token = await get_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=15) as c:
        r = await getattr(c, method)(
            f"{BACKEND_URL}/api{path}", headers=headers, **kwargs
        )
        if not r.is_success:
            try:
                detail = r.json().get("detail", str(r.status_code))
            except Exception:
                detail = f"HTTP {r.status_code}"
            raise httpx.HTTPStatusError(str(detail), request=r.request, response=r)
        return r.json()

# ── Helpers ───────────────────────────────────────────────────────────────────
def today() -> str:
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist).strftime("%Y-%m-%d")

def yesterday() -> str:
    ist = timezone(timedelta(hours=5, minutes=30))
    return (datetime.now(ist) - timedelta(days=1)).strftime("%Y-%m-%d")

def auth(update: Update) -> bool:
    return update.effective_chat.id == ALLOWED_CHAT_ID

async def deny(update: Update):
    await update.message.reply_text("Unauthorized.")
    logger.warning("Unauthorized: %s", update.effective_chat.id)

def kb(options: list, cols: int = 2) -> ReplyKeyboardMarkup:
    rows = [options[i:i+cols] for i in range(0, len(options), cols)]
    return ReplyKeyboardMarkup(rows, one_time_keyboard=True, resize_keyboard=True)

# ── States ────────────────────────────────────────────────────────────────────
S_ITEM, S_QTY, S_NOTES = 1, 2, 3
P_ITEM, P_QTY, P_PRICE, P_DATE = 10, 11, 12, 13
SL_LUNCH, SL_DINNER, SL_OTHER, SL_NOTES = 20, 21, 22, 23
E_CAT, E_DESC, E_AMT = 30, 31, 32

# ── /start /help ──────────────────────────────────────────────────────────────
HELP_TEXT = (
    "SP Dhaba Bot\n\n"
    "I will guide you step by step. Just tap a command:\n\n"
    "/stock    Count shelf items (closing stock)\n"
    "/purchase Record what you bought today\n"
    "/sales    Record today sales\n"
    "/expense  Record an expense\n"
    "/status   Today summary\n"
    "/cancel   Cancel current action\n\n"
    "For purchase I will ask:\n"
    "  1. Which item?\n"
    "  2. How many kg/litre/pcs?\n"
    "  3. Price per unit in rupees?\n"
    "  4. Today or Yesterday?\n\n"
    "No need to remember any format."
)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not auth(update): return await deny(update)
    await update.message.reply_text(HELP_TEXT)

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not auth(update): return await deny(update)
    await update.message.reply_text(HELP_TEXT)

# ── /status ───────────────────────────────────────────────────────────────────
async def status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not auth(update): return await deny(update)
    await update.message.reply_text("Fetching summary...")
    try:
        d = await call("get", "/dashboard")
        sales = d.get("today_sales", 0)
        exp   = d.get("today_expenses", 0)
        pnl   = d.get("today_pnl", 0)
        low   = d.get("low_stock_count", 0)
        out   = d.get("out_of_stock_count", 0)
        icon  = "UP" if pnl >= 0 else "DOWN"
        label = "Profit" if pnl >= 0 else "Loss"
        nl = "\n"
        msg = nl.join([
            "Today Summary - " + today(),
            "",
            "Sales:    Rs " + f"{sales:,.0f}",
            "Expenses: Rs " + f"{exp:,.0f}",
            icon + " " + label + ": Rs " + f"{abs(pnl):,.0f}",
            "",
            "Low stock:    " + str(low) + " items",
            "Out of stock: " + str(out) + " items",
        ])
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text("Could not fetch status: " + str(e)[:80])

# ── /cancel ───────────────────────────────────────────────────────────────────
async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not auth(update): return await deny(update)
    ctx.user_data.clear()
    await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not auth(update): return await deny(update)
    await update.message.reply_text("Unknown command. Type /help")

# ══════════════════════════════════════════════════════════════════════════════
# CLOSING STOCK
# ══════════════════════════════════════════════════════════════════════════════

async def stock_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not auth(update): return await deny(update)
    args = ctx.args
    if args and len(args) >= 2:
        return await stock_quick(update, ctx, " ".join(args[:-1]), args[-1])
    try:
        items = await call("get", "/items")
        active = [i for i in items if i.get("is_active", True)]
        ctx.user_data["items"] = {i["name"].lower(): i for i in active}
        names = [i["name"] for i in active]
        await update.message.reply_text(
            "Which item did you count on the shelf?",
            reply_markup=kb(names)
        )
        return S_ITEM
    except Exception as e:
        await update.message.reply_text("Error loading items: " + str(e)[:80])
        return ConversationHandler.END

async def stock_quick(update, ctx, item_name, qty_str):
    try:
        qty = float(qty_str)
        if qty < 0:
            await update.message.reply_text("Quantity cannot be negative.")
            return ConversationHandler.END
        items = await call("get", "/items")
        item = next((i for i in items if item_name.lower() in i["name"].lower()), None)
        if not item:
            await update.message.reply_text("Item not found: " + item_name)
            return ConversationHandler.END
        result = await call("post", "/closing-stock", json={
            "date": today(), "item_id": item["id"],
            "closing_qty": qty, "notes": "Via Telegram"
        })
        consumed = result.get("consumed", "?")
        await update.message.reply_text(
            "Closing Stock Saved\n\n"
            "Item: " + item["name"] + "\n"
            "Closing: " + str(qty) + " " + item["unit"] + "\n"
            "Consumed today: " + str(consumed) + " " + item["unit"]
        )
    except httpx.HTTPStatusError as e:
        await update.message.reply_text("Error: " + str(e)[:100])
    except Exception as e:
        await update.message.reply_text("Failed: " + str(e)[:100])
    return ConversationHandler.END

async def s_item(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    items = ctx.user_data.get("items", {})
    item = items.get(name.lower()) or next(
        (v for k, v in items.items() if name.lower() in k), None
    )
    if not item:
        await update.message.reply_text("Item not found. Pick from the list.")
        return S_ITEM
    ctx.user_data["s_item"] = item
    await update.message.reply_text(
        "How many " + item["unit"] + " of " + item["name"] + " are left on shelf?\n"
        "(Enter a number, for example: 7)",
        reply_markup=ReplyKeyboardRemove()
    )
    return S_QTY

async def s_qty(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        qty = float(update.message.text.strip())
        if qty < 0:
            await update.message.reply_text("Cannot be negative. Enter shelf count:")
            return S_QTY
        ctx.user_data["s_qty"] = qty
        await update.message.reply_text(
            "Any notes? (spillage, moved to fridge, etc.)\n"
            "Or type skip to save now."
        )
        return S_NOTES
    except ValueError:
        await update.message.reply_text("Enter a number (e.g. 7 or 2.5):")
        return S_QTY

async def s_notes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    notes = update.message.text.strip()
    if notes.lower() == "skip":
        notes = ""
    item = ctx.user_data["s_item"]
    qty  = ctx.user_data["s_qty"]
    try:
        result = await call("post", "/closing-stock", json={
            "date": today(), "item_id": item["id"],
            "closing_qty": qty, "notes": notes
        })
        consumed = result.get("consumed", "?")
        msg = (
            "Closing Stock Saved\n\n"
            "Item: " + item["name"] + "\n"
            "Closing qty: " + str(qty) + " " + item["unit"] + "\n"
            "Consumed today: " + str(consumed) + " " + item["unit"]
        )
        if notes:
            msg += "\nNotes: " + notes
        await update.message.reply_text(msg)
    except httpx.HTTPStatusError as e:
        await update.message.reply_text("Error: " + str(e)[:100])
    except Exception as e:
        await update.message.reply_text("Failed: " + str(e)[:100])
    return ConversationHandler.END

# ══════════════════════════════════════════════════════════════════════════════
# PURCHASE
# ══════════════════════════════════════════════════════════════════════════════

async def purchase_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not auth(update): return await deny(update)
    args = ctx.args
    if args and len(args) >= 3:
        return await purchase_quick(update, ctx, args[0], args[1], args[2])
    try:
        items = await call("get", "/items")
        active = [i for i in items if i.get("is_active", True)]
        ctx.user_data["items"] = {i["name"].lower(): i for i in active}
        names = [i["name"] for i in active]
        await update.message.reply_text(
            "Which item did you buy?",
            reply_markup=kb(names)
        )
        return P_ITEM
    except Exception as e:
        await update.message.reply_text("Error loading items: " + str(e)[:80])
        return ConversationHandler.END

async def purchase_quick(update, ctx, item_name, qty_str, price_str):
    try:
        qty   = float(qty_str)
        price = float(price_str)
        if qty <= 0 or price <= 0:
            await update.message.reply_text("Quantity and price must be greater than 0.")
            return ConversationHandler.END
        items = await call("get", "/items")
        item = next((i for i in items if item_name.lower() in i["name"].lower()), None)
        if not item:
            await update.message.reply_text("Item not found: " + item_name)
            return ConversationHandler.END
        await call("post", "/purchases", json={
            "item_id": item["id"], "quantity": qty,
            "price_per_unit": price, "date": today(), "notes": "Via Telegram"
        })
        await update.message.reply_text(
            "Purchase Saved\n\n"
            "Item: " + item["name"] + "\n"
            "Qty: " + str(qty) + " " + item["unit"] + " x Rs " + str(price) + "\n"
            "Total: Rs " + f"{qty*price:,.0f}"
        )
    except httpx.HTTPStatusError as e:
        await update.message.reply_text("Error: " + str(e)[:100])
    except Exception as e:
        await update.message.reply_text("Failed: " + str(e)[:100])
    return ConversationHandler.END

async def p_item(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    items = ctx.user_data.get("items", {})
    item = items.get(name.lower()) or next(
        (v for k, v in items.items() if name.lower() in k), None
    )
    if not item:
        await update.message.reply_text("Item not found. Pick from the list.")
        return P_ITEM
    ctx.user_data["p_item"] = item
    await update.message.reply_text(
        "How many " + item["unit"] + " of " + item["name"] + " did you buy?\n"
        "(Enter a number, for example: 10)",
        reply_markup=ReplyKeyboardRemove()
    )
    return P_QTY

async def p_qty(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        qty = float(update.message.text.strip())
        if qty <= 0:
            await update.message.reply_text("Must be greater than 0. Enter quantity:")
            return P_QTY
        ctx.user_data["p_qty"] = qty
        item = ctx.user_data["p_item"]
        await update.message.reply_text(
            "What is the price per " + item["unit"] + " in rupees?\n"
            "(For example: 200 means Rs 200 per " + item["unit"] + ")"
        )
        return P_PRICE
    except ValueError:
        await update.message.reply_text("Enter a number:")
        return P_QTY

async def p_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.strip())
        if price <= 0:
            await update.message.reply_text("Price must be greater than 0:")
            return P_PRICE
        ctx.user_data["p_price"] = price
        item  = ctx.user_data["p_item"]
        qty   = ctx.user_data["p_qty"]
        total = qty * price
        await update.message.reply_text(
            "Confirm Purchase:\n"
            "Item: " + item["name"] + "\n"
            "Qty: " + str(qty) + " " + item["unit"] + " x Rs " + str(price) + "\n"
            "Total: Rs " + f"{total:,.0f}" + "\n\n"
            "When did you buy this?",
            reply_markup=kb(["Today", "Yesterday"])
        )
        return P_DATE
    except ValueError:
        await update.message.reply_text("Enter a number:")
        return P_PRICE

async def p_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    if text == "today":
        purchase_date = today()
    elif text == "yesterday":
        purchase_date = yesterday()
    else:
        try:
            datetime.strptime(text, "%Y-%m-%d")
            purchase_date = text
        except ValueError:
            await update.message.reply_text("Say Today, Yesterday, or YYYY-MM-DD:")
            return P_DATE
    item  = ctx.user_data["p_item"]
    qty   = ctx.user_data["p_qty"]
    price = ctx.user_data["p_price"]
    try:
        await call("post", "/purchases", json={
            "item_id": item["id"], "quantity": qty,
            "price_per_unit": price, "date": purchase_date,
            "notes": "Via Telegram"
        })
        await update.message.reply_text(
            "Purchase Saved\n\n"
            "Item: " + item["name"] + "\n"
            "Qty: " + str(qty) + " " + item["unit"] + " x Rs " + str(price) + "\n"
            "Total: Rs " + f"{qty*price:,.0f}" + "\n"
            "Date: " + purchase_date,
            reply_markup=ReplyKeyboardRemove()
        )
    except httpx.HTTPStatusError as e:
        await update.message.reply_text("Error: " + str(e)[:100], reply_markup=ReplyKeyboardRemove())
    except Exception as e:
        await update.message.reply_text("Failed: " + str(e)[:100], reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ══════════════════════════════════════════════════════════════════════════════
# SALES
# ══════════════════════════════════════════════════════════════════════════════

async def sales_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not auth(update): return await deny(update)
    await update.message.reply_text(
        "Sales for " + today() + "\n\n"
        "How much was Lunch sales in Rs?\n"
        "(Enter a number, for example: 5000)",
        reply_markup=ReplyKeyboardRemove()
    )
    return SL_LUNCH

async def sl_lunch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        ctx.user_data["lunch"] = float(update.message.text.strip())
        await update.message.reply_text("Dinner sales in Rs? (enter 0 if none)")
        return SL_DINNER
    except ValueError:
        await update.message.reply_text("Enter a number:")
        return SL_LUNCH

async def sl_dinner(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        ctx.user_data["dinner"] = float(update.message.text.strip())
        await update.message.reply_text("Other sales in Rs? (snacks, takeaway, etc. Enter 0 if none)")
        return SL_OTHER
    except ValueError:
        await update.message.reply_text("Enter a number:")
        return SL_DINNER

async def sl_other(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        ctx.user_data["other"] = float(update.message.text.strip())
        total = ctx.user_data["lunch"] + ctx.user_data["dinner"] + ctx.user_data["other"]
        await update.message.reply_text(
            "Total: Rs " + f"{total:,.0f}" + "\n\n"
            "Any notes? Or type skip to save now."
        )
        return SL_NOTES
    except ValueError:
        await update.message.reply_text("Enter a number:")
        return SL_OTHER

async def sl_notes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    notes = update.message.text.strip()
    if notes.lower() == "skip":
        notes = ""
    lunch  = ctx.user_data["lunch"]
    dinner = ctx.user_data["dinner"]
    other  = ctx.user_data["other"]
    total  = lunch + dinner + other
    try:
        await call("post", "/sales", json={
            "date": today(),
            "lunch_amount": lunch,
            "dinner_amount": dinner,
            "other_amount": other,
            "total_amount": total,
            "notes": notes
        })
        msg = (
            "Sales Saved\n\n"
            "Lunch:  Rs " + f"{lunch:,.0f}" + "\n"
            "Dinner: Rs " + f"{dinner:,.0f}" + "\n"
            "Other:  Rs " + f"{other:,.0f}" + "\n"
            "Total:  Rs " + f"{total:,.0f}"
        )
        if notes:
            msg += "\nNotes: " + notes
        await update.message.reply_text(msg)
    except httpx.HTTPStatusError as e:
        await update.message.reply_text("Error: " + str(e)[:100])
    except Exception as e:
        await update.message.reply_text("Failed: " + str(e)[:100])
    return ConversationHandler.END

# ══════════════════════════════════════════════════════════════════════════════
# EXPENSE
# ══════════════════════════════════════════════════════════════════════════════

async def expense_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not auth(update): return await deny(update)
    try:
        cats = await call("get", "/expense-categories")
        cat_names = [c["name"] for c in cats if c.get("is_active", True)]
        markup = kb(cat_names) if cat_names else ReplyKeyboardRemove()
        await update.message.reply_text("Expense category?", reply_markup=markup)
        return E_CAT
    except Exception:
        await update.message.reply_text(
            "Expense category?\n(e.g. Gas, Electricity, Transport)",
            reply_markup=ReplyKeyboardRemove()
        )
        return E_CAT

async def e_cat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["e_cat"] = update.message.text.strip()
    await update.message.reply_text(
        "Description?\n(e.g. Gas cylinder refill)",
        reply_markup=ReplyKeyboardRemove()
    )
    return E_DESC

async def e_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["e_desc"] = update.message.text.strip()
    await update.message.reply_text("Amount in Rs?")
    return E_AMT

async def e_amt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            await update.message.reply_text("Amount must be greater than 0:")
            return E_AMT
        cat  = ctx.user_data["e_cat"]
        desc = ctx.user_data["e_desc"]
        await call("post", "/expenses", json={
            "date": today(), "category": cat,
            "description": desc, "amount": amount
        })
        await update.message.reply_text(
            "Expense Saved\n\n"
            "Category: " + cat + "\n"
            "Description: " + desc + "\n"
            "Amount: Rs " + f"{amount:,.0f}"
        )
    except httpx.HTTPStatusError as e:
        await update.message.reply_text("Error: " + str(e)[:100])
    except ValueError:
        await update.message.reply_text("Enter a number:")
        return E_AMT
    except Exception as e:
        await update.message.reply_text("Failed: " + str(e)[:100])
    return ConversationHandler.END

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    stock_conv = ConversationHandler(
        entry_points=[CommandHandler("stock", stock_cmd)],
        states={
            S_ITEM:  [MessageHandler(filters.TEXT & ~filters.COMMAND, s_item)],
            S_QTY:   [MessageHandler(filters.TEXT & ~filters.COMMAND, s_qty)],
            S_NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, s_notes)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    purchase_conv = ConversationHandler(
        entry_points=[CommandHandler("purchase", purchase_cmd)],
        states={
            P_ITEM:  [MessageHandler(filters.TEXT & ~filters.COMMAND, p_item)],
            P_QTY:   [MessageHandler(filters.TEXT & ~filters.COMMAND, p_qty)],
            P_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, p_price)],
            P_DATE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, p_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    sales_conv = ConversationHandler(
        entry_points=[CommandHandler("sales", sales_cmd)],
        states={
            SL_LUNCH:  [MessageHandler(filters.TEXT & ~filters.COMMAND, sl_lunch)],
            SL_DINNER: [MessageHandler(filters.TEXT & ~filters.COMMAND, sl_dinner)],
            SL_OTHER:  [MessageHandler(filters.TEXT & ~filters.COMMAND, sl_other)],
            SL_NOTES:  [MessageHandler(filters.TEXT & ~filters.COMMAND, sl_notes)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    expense_conv = ConversationHandler(
        entry_points=[CommandHandler("expense", expense_cmd)],
        states={
            E_CAT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, e_cat)],
            E_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, e_desc)],
            E_AMT:  [MessageHandler(filters.TEXT & ~filters.COMMAND, e_amt)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start",    start))
    app.add_handler(CommandHandler("help",     help_cmd))
    app.add_handler(CommandHandler("status",   status))
    app.add_handler(stock_conv)
    app.add_handler(purchase_conv)
    app.add_handler(sales_conv)
    app.add_handler(expense_conv)
    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    logger.info("SP Dhaba Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
