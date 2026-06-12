"""
SP Dhaba — Telegram Bot for Lokesh
====================================
Allows Lokesh to record daily operations via Telegram.

Commands:
  /start          — welcome + help
  /help           — list all commands
  /stock          — record closing stock (guided)
  /purchase       — record a purchase (guided)
  /sales          — record today's sales (guided)
  /expense        — record an expense (guided)
  /status         — view today's summary
  /stock <item> <qty>           — quick mode
  /purchase <item> <qty> <price> — quick mode

Security:
  - Only responds to ALLOWED_CHAT_ID (Lokesh's chat ID)
  - Uses staff JWT — no admin access
  - Token auto-refreshes every 6 hours
  - All writes go through existing backend validation
"""

import os
import re
import json
import asyncio
import logging
from datetime import datetime, date
import httpx
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, ContextTypes, filters,
)

# ── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN      = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED_CHAT_ID = int(os.environ["ALLOWED_CHAT_ID"])   # Lokesh's Telegram chat ID
BACKEND_URL    = os.environ["BACKEND_URL"].rstrip("/")  # https://spdhaba-production.up.railway.app
STAFF_EMAIL    = os.environ["STAFF_EMAIL"]
STAFF_PASSWORD = os.environ["STAFF_PASSWORD"]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Auth state ────────────────────────────────────────────────────────────────
_token: str = ""
_token_expiry: float = 0

async def get_token() -> str:
    """Get a valid staff JWT — auto-refreshes every 6 hours."""
    global _token, _token_expiry
    import time
    if _token and time.time() < _token_expiry:
        return _token
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(f"{BACKEND_URL}/api/auth/login", json={
            "email": STAFF_EMAIL, "password": STAFF_PASSWORD
        })
        resp.raise_for_status()
        data = resp.json()
        _token = data["token"]
        _token_expiry = time.time() + 6 * 3600
        logger.info("Bot: JWT refreshed")
        return _token

async def api(method: str, path: str, **kwargs) -> dict:
    """Make authenticated API call."""
    token = await get_token()
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await getattr(client, method)(
            f"{BACKEND_URL}/api{path}",
            headers=headers, **kwargs
        )
        resp.raise_for_status()
        return resp.json()

# ── Security guard ────────────────────────────────────────────────────────────
def authorized(update: Update) -> bool:
    """Only allow Lokesh's chat ID."""
    return update.effective_chat.id == ALLOWED_CHAT_ID

async def reject(update: Update):
    await update.message.reply_text("⛔ Unauthorized. This bot is private.")
    logger.warning(f"Unauthorized access attempt from chat_id={update.effective_chat.id}")

# ── IST date helper ───────────────────────────────────────────────────────────
def today_ist() -> str:
    from datetime import timezone, timedelta
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist).strftime("%Y-%m-%d")

# ── Conversation states ───────────────────────────────────────────────────────
# Stock recording
STOCK_ITEM, STOCK_QTY, STOCK_NOTES = range(3)
# Purchase recording
PUR_ITEM, PUR_QTY, PUR_PRICE, PUR_DATE = range(10, 14)
# Sales recording
SALES_LUNCH, SALES_DINNER, SALES_OTHER, SALES_NOTES = range(20, 24)
# Expense recording
EXP_CAT, EXP_DESC, EXP_AMOUNT = range(30, 33)

# ── /start and /help ──────────────────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return await reject(update)
    await update.message.reply_text(
        "🍛 *SP Dhaba Bot*\n\n"
        "Hello Lokesh! Here's what I can do:\n\n"
        "📦 /stock — Record closing stock count\n"
        "🛒 /purchase — Record a purchase\n"
        "💰 /sales — Record today's sales\n"
        "💸 /expense — Record an expense\n"
        "📊 /status — Today's summary\n"
        "❓ /help — Show this message\n\n"
        "_Quick mode examples:_\n"
        "`/stock Chicken 7`\n"
        "`/purchase Chicken 10 200`",
        parse_mode="Markdown"
    )

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return await reject(update)
    await start(update, ctx)

# ── /status — today's summary ─────────────────────────────────────────────────
async def status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return await reject(update)
    await update.message.reply_text("⏳ Fetching today's summary...")
    try:
        today = today_ist()
        dash  = await api("get", "/dashboard")

        sales    = dash.get("today_sales", 0)
        expenses = dash.get("today_expenses", 0)
        pnl      = dash.get("today_pnl", 0)
        low      = dash.get("low_stock_count", 0)
        out      = dash.get("out_of_stock_count", 0)

        pnl_icon = "📈" if pnl >= 0 else "📉"
        pnl_label = "Profit" if pnl >= 0 else "Loss"

        msg = (
            f"📊 *Today's Summary — {today}*\n\n"
            f"💰 Sales:    ₹{sales:,.0f}\n"
            f"💸 Expenses: ₹{expenses:,.0f}\n"
            f"{pnl_icon} {pnl_label}:  ₹{abs(pnl):,.0f}\n\n"
            f"⚠️ Low stock:    {low} items\n"
            f"🔴 Out of stock: {out} items\n\n"
        )

        if out > 0 or low > 0:
            alerts = await api("get", "/alerts")
            critical = [a for a in (alerts if isinstance(alerts, list) else [])
                       if a.get("severity") == "critical"][:5]
            if critical:
                msg += "*🚨 Critical Alerts:*\n"
                for a in critical:
                    msg += f"• {a['item_name']}: {a['title']}\n"

        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Status error: {e}")
        await update.message.reply_text("❌ Could not fetch status. Try again.")

# ══════════════════════════════════════════════════════════════════════════════
# CLOSING STOCK — conversation + quick mode
# ══════════════════════════════════════════════════════════════════════════════

async def stock_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return await reject(update)

    # Quick mode: /stock Chicken 7
    args = ctx.args
    if args and len(args) >= 2:
        return await _stock_quick(update, ctx, " ".join(args[:-1]), args[-1])

    # Guided mode — fetch items
    try:
        items = await api("get", "/items")
        active = [i for i in items if i.get("is_active", True)]
        ctx.user_data["items"] = {i["name"].lower(): i for i in active}
        names = [i["name"] for i in active]

        # Build keyboard in rows of 2
        keyboard = [names[i:i+2] for i in range(0, len(names), 2)]
        markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "📦 *Record Closing Stock*\n\nWhich item did you count?",
            reply_markup=markup, parse_mode="Markdown"
        )
        return STOCK_ITEM
    except Exception as e:
        logger.error(f"Stock start error: {e}")
        await update.message.reply_text("❌ Could not load items. Try again.")
        return ConversationHandler.END

async def _stock_quick(update, ctx, item_name, qty_str):
    """Quick mode handler for /stock <item> <qty>"""
    try:
        qty = float(qty_str)
        if qty < 0:
            await update.message.reply_text("❌ Quantity cannot be negative.")
            return ConversationHandler.END

        items = await api("get", "/items")
        item = next((i for i in items
                    if item_name.lower() in i["name"].lower()), None)
        if not item:
            await update.message.reply_text(f"❌ Item '{item_name}' not found. Use /stock to see all items.")
            return ConversationHandler.END

        result = await api("post", "/closing-stock", json={
            "date": today_ist(),
            "item_id": item["id"],
            "closing_qty": qty,
            "notes": "Via Telegram bot"
        })
        consumed = result.get("consumed", "?")
        await update.message.reply_text(
            f"✅ *Closing Stock Saved*\n\n"
            f"Item: {item['name']}\n"
            f"Closing qty: {qty} {item['unit']}\n"
            f"Consumed today: {consumed} {item['unit']}",
            parse_mode="Markdown"
        )
    except httpx.HTTPStatusError as e:
        err = e.response.json().get("detail", str(e))
        await update.message.reply_text(f"❌ Error: {err}")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {str(e)[:100]}")
    return ConversationHandler.END

async def stock_item(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    items = ctx.user_data.get("items", {})
    item = items.get(name.lower())
    if not item:
        # fuzzy match
        item = next((v for k, v in items.items() if name.lower() in k), None)
    if not item:
        await update.message.reply_text("❌ Item not found. Please pick from the keyboard.")
        return STOCK_ITEM
    ctx.user_data["stock_item"] = item
    await update.message.reply_text(
        f"How many *{item['name']}* ({item['unit']}) are left on the shelf?",
        reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown"
    )
    return STOCK_QTY

async def stock_qty(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        qty = float(update.message.text.strip())
        if qty < 0:
            await update.message.reply_text("❌ Cannot be negative. Enter shelf count:")
            return STOCK_QTY
        ctx.user_data["stock_qty"] = qty
        await update.message.reply_text(
            "Any notes? (spillage, moved to fridge, etc.)\nOr type *skip* to continue.",
            parse_mode="Markdown"
        )
        return STOCK_NOTES
    except ValueError:
        await update.message.reply_text("❌ Enter a number (e.g. 7 or 2.5):")
        return STOCK_QTY

async def stock_notes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    notes = update.message.text.strip()
    if notes.lower() == "skip":
        notes = ""
    item = ctx.user_data["stock_item"]
    qty  = ctx.user_data["stock_qty"]
    try:
        result = await api("post", "/closing-stock", json={
            "date": today_ist(),
            "item_id": item["id"],
            "closing_qty": qty,
            "notes": notes
        })
        consumed = result.get("consumed", "?")
        await update.message.reply_text(
            f"✅ *Closing Stock Saved*\n\n"
            f"Item: {item['name']}\n"
            f"Closing qty: {qty} {item['unit']}\n"
            f"Consumed today: {consumed} {item['unit']}"
            + (f"\nNotes: {notes}" if notes else ""),
            parse_mode="Markdown"
        )
    except httpx.HTTPStatusError as e:
        err = e.response.json().get("detail", str(e))
        await update.message.reply_text(f"❌ Error: {err}")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {str(e)[:100]}")
    return ConversationHandler.END

# ══════════════════════════════════════════════════════════════════════════════
# PURCHASE — conversation + quick mode
# ══════════════════════════════════════════════════════════════════════════════

async def purchase_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return await reject(update)

    # Quick mode: /purchase Chicken 10 200
    args = ctx.args
    if args and len(args) >= 3:
        return await _purchase_quick(update, ctx, args[0], args[1], args[2])

    try:
        items = await api("get", "/items")
        active = [i for i in items if i.get("is_active", True)]
        ctx.user_data["items"] = {i["name"].lower(): i for i in active}
        names = [i["name"] for i in active]
        keyboard = [names[i:i+2] for i in range(0, len(names), 2)]
        markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text(
            "🛒 *Record Purchase*\n\nWhich item did you buy?",
            reply_markup=markup, parse_mode="Markdown"
        )
        return PUR_ITEM
    except Exception as e:
        await update.message.reply_text("❌ Could not load items. Try again.")
        return ConversationHandler.END

async def _purchase_quick(update, ctx, item_name, qty_str, price_str):
    try:
        qty   = float(qty_str)
        price = float(price_str)
        if qty <= 0 or price <= 0:
            await update.message.reply_text("❌ Quantity and price must be greater than 0.")
            return ConversationHandler.END

        items = await api("get", "/items")
        item = next((i for i in items
                    if item_name.lower() in i["name"].lower()), None)
        if not item:
            await update.message.reply_text(f"❌ Item '{item_name}' not found.")
            return ConversationHandler.END

        total = qty * price
        result = await api("post", "/purchases", json={
            "item_id": item["id"],
            "quantity": qty,
            "price_per_unit": price,
            "date": today_ist(),
            "notes": "Via Telegram bot"
        })
        await update.message.reply_text(
            f"✅ *Purchase Saved*\n\n"
            f"Item: {item['name']}\n"
            f"Qty: {qty} {item['unit']} @ ₹{price}\n"
            f"Total: ₹{total:,.0f}",
            parse_mode="Markdown"
        )
    except httpx.HTTPStatusError as e:
        err = e.response.json().get("detail", str(e))
        await update.message.reply_text(f"❌ Error: {err}")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {str(e)[:100]}")
    return ConversationHandler.END

async def pur_item(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    items = ctx.user_data.get("items", {})
    item = items.get(name.lower()) or next(
        (v for k, v in items.items() if name.lower() in k), None)
    if not item:
        await update.message.reply_text("❌ Item not found. Pick from the keyboard.")
        return PUR_ITEM
    ctx.user_data["pur_item"] = item
    await update.message.reply_text(
        f"How many *{item['unit']}* of {item['name']} did you buy?",
        reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown"
    )
    return PUR_QTY

async def pur_qty(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        qty = float(update.message.text.strip())
        if qty <= 0:
            await update.message.reply_text("❌ Must be greater than 0:")
            return PUR_QTY
        ctx.user_data["pur_qty"] = qty
        await update.message.reply_text("Price per unit (₹)?")
        return PUR_PRICE
    except ValueError:
        await update.message.reply_text("❌ Enter a number:")
        return PUR_QTY

async def pur_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.strip())
        if price <= 0:
            await update.message.reply_text("❌ Price must be greater than 0:")
            return PUR_PRICE
        ctx.user_data["pur_price"] = price
        item  = ctx.user_data["pur_item"]
        qty   = ctx.user_data["pur_qty"]
        total = qty * price
        keyboard = ReplyKeyboardMarkup([["Today", "Yesterday"]], one_time_keyboard=True)
        await update.message.reply_text(
            f"Total: ₹{total:,.0f}\n\nDate of purchase?",
            reply_markup=keyboard
        )
        return PUR_DATE
    except ValueError:
        await update.message.reply_text("❌ Enter a number:")
        return PUR_PRICE

async def pur_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from datetime import timedelta, timezone, datetime as dt
    ist = timezone(timedelta(hours=5, minutes=30))
    text = update.message.text.strip().lower()
    if text == "today":
        purchase_date = dt.now(ist).strftime("%Y-%m-%d")
    elif text == "yesterday":
        purchase_date = (dt.now(ist) - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        # Try parse YYYY-MM-DD
        try:
            datetime.strptime(text, "%Y-%m-%d")
            purchase_date = text
        except ValueError:
            await update.message.reply_text("❌ Say 'Today', 'Yesterday', or YYYY-MM-DD:")
            return PUR_DATE

    item  = ctx.user_data["pur_item"]
    qty   = ctx.user_data["pur_qty"]
    price = ctx.user_data["pur_price"]
    try:
        await api("post", "/purchases", json={
            "item_id": item["id"],
            "quantity": qty,
            "price_per_unit": price,
            "date": purchase_date,
            "notes": "Via Telegram bot"
        })
        await update.message.reply_text(
            f"✅ *Purchase Saved*\n\n"
            f"Item: {item['name']}\n"
            f"Qty: {qty} {item['unit']} @ ₹{price}\n"
            f"Total: ₹{qty*price:,.0f}\n"
            f"Date: {purchase_date}",
            reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown"
        )
    except httpx.HTTPStatusError as e:
        err = e.response.json().get("detail", str(e))
        await update.message.reply_text(f"❌ Error: {err}", reply_markup=ReplyKeyboardRemove())
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {str(e)[:100]}", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

# ══════════════════════════════════════════════════════════════════════════════
# SALES
# ══════════════════════════════════════════════════════════════════════════════

async def sales_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return await reject(update)
    await update.message.reply_text(
        f"💰 *Record Sales — {today_ist()}*\n\nLunch sales (₹)?",
        reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown"
    )
    return SALES_LUNCH

async def sales_lunch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        ctx.user_data["lunch"] = float(update.message.text.strip())
        await update.message.reply_text("Dinner sales (₹)?")
        return SALES_DINNER
    except ValueError:
        await update.message.reply_text("❌ Enter a number:")
        return SALES_LUNCH

async def sales_dinner(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        ctx.user_data["dinner"] = float(update.message.text.strip())
        await update.message.reply_text("Other sales (₹)? (snacks, takeaway, etc.)\nType 0 if none.")
        return SALES_OTHER
    except ValueError:
        await update.message.reply_text("❌ Enter a number:")
        return SALES_DINNER

async def sales_other(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        ctx.user_data["other"] = float(update.message.text.strip())
        total = ctx.user_data["lunch"] + ctx.user_data["dinner"] + ctx.user_data["other"]
        await update.message.reply_text(
            f"Total: ₹{total:,.0f}\n\nAny notes? (type *skip* to save now)",
            parse_mode="Markdown"
        )
        return SALES_NOTES
    except ValueError:
        await update.message.reply_text("❌ Enter a number:")
        return SALES_OTHER

async def sales_notes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    notes = update.message.text.strip()
    if notes.lower() == "skip": notes = ""
    lunch  = ctx.user_data["lunch"]
    dinner = ctx.user_data["dinner"]
    other  = ctx.user_data["other"]
    total  = lunch + dinner + other
    try:
        await api("post", "/sales", json={
            "date": today_ist(),
            "lunch_amount": lunch,
            "dinner_amount": dinner,
            "other_amount": other,
            "total_amount": total,
            "notes": notes
        })
        await update.message.reply_text(
            f"✅ *Sales Saved*\n\n"
            f"Lunch:  ₹{lunch:,.0f}\n"
            f"Dinner: ₹{dinner:,.0f}\n"
            f"Other:  ₹{other:,.0f}\n"
            f"Total:  ₹{total:,.0f}"
            + (f"\nNotes: {notes}" if notes else ""),
            parse_mode="Markdown"
        )
    except httpx.HTTPStatusError as e:
        err = e.response.json().get("detail", str(e))
        await update.message.reply_text(f"❌ Error: {err}")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {str(e)[:100]}")
    return ConversationHandler.END

# ══════════════════════════════════════════════════════════════════════════════
# EXPENSE
# ══════════════════════════════════════════════════════════════════════════════

async def expense_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return await reject(update)
    try:
        settings = await api("get", "/settings/categories")
        cats = [c["name"] for c in settings] if isinstance(settings, list) else []
        if cats:
            keyboard = [cats[i:i+2] for i in range(0, len(cats), 2)]
            markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        else:
            markup = ReplyKeyboardRemove()
        await update.message.reply_text(
            "💸 *Record Expense*\n\nCategory?",
            reply_markup=markup, parse_mode="Markdown"
        )
        return EXP_CAT
    except Exception:
        await update.message.reply_text(
            "💸 *Record Expense*\n\nCategory? (e.g. Gas, Electricity, Transport)",
            reply_markup=ReplyKeyboardRemove(), parse_mode="Markdown"
        )
        return EXP_CAT

async def exp_cat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["exp_cat"] = update.message.text.strip()
    await update.message.reply_text(
        "Description? (e.g. Gas cylinder refill)",
        reply_markup=ReplyKeyboardRemove()
    )
    return EXP_DESC

async def exp_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["exp_desc"] = update.message.text.strip()
    await update.message.reply_text("Amount (₹)?")
    return EXP_AMOUNT

async def exp_amount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            await update.message.reply_text("❌ Amount must be greater than 0:")
            return EXP_AMOUNT
        cat  = ctx.user_data["exp_cat"]
        desc = ctx.user_data["exp_desc"]
        await api("post", "/expenses", json={
            "date": today_ist(),
            "category": cat,
            "description": desc,
            "amount": amount
        })
        await update.message.reply_text(
            f"✅ *Expense Saved*\n\n"
            f"Category: {cat}\n"
            f"Description: {desc}\n"
            f"Amount: ₹{amount:,.0f}",
            parse_mode="Markdown"
        )
    except httpx.HTTPStatusError as e:
        err = e.response.json().get("detail", str(e))
        await update.message.reply_text(f"❌ Error: {err}")
    except ValueError:
        await update.message.reply_text("❌ Enter a number:")
        return EXP_AMOUNT
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {str(e)[:100]}")
    return ConversationHandler.END

# ── Cancel any conversation ───────────────────────────────────────────────────
async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return await reject(update)
    ctx.user_data.clear()
    await update.message.reply_text(
        "❌ Cancelled.", reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# ── Unknown command ───────────────────────────────────────────────────────────
async def unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not authorized(update): return await reject(update)
    await update.message.reply_text(
        "❓ Unknown command. Type /help to see what I can do."
    )

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Stock conversation
    stock_conv = ConversationHandler(
        entry_points=[CommandHandler("stock", stock_cmd)],
        states={
            STOCK_ITEM:  [MessageHandler(filters.TEXT & ~filters.COMMAND, stock_item)],
            STOCK_QTY:   [MessageHandler(filters.TEXT & ~filters.COMMAND, stock_qty)],
            STOCK_NOTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, stock_notes)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Purchase conversation
    purchase_conv = ConversationHandler(
        entry_points=[CommandHandler("purchase", purchase_cmd)],
        states={
            PUR_ITEM:  [MessageHandler(filters.TEXT & ~filters.COMMAND, pur_item)],
            PUR_QTY:   [MessageHandler(filters.TEXT & ~filters.COMMAND, pur_qty)],
            PUR_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, pur_price)],
            PUR_DATE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, pur_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Sales conversation
    sales_conv = ConversationHandler(
        entry_points=[CommandHandler("sales", sales_cmd)],
        states={
            SALES_LUNCH:  [MessageHandler(filters.TEXT & ~filters.COMMAND, sales_lunch)],
            SALES_DINNER: [MessageHandler(filters.TEXT & ~filters.COMMAND, sales_dinner)],
            SALES_OTHER:  [MessageHandler(filters.TEXT & ~filters.COMMAND, sales_other)],
            SALES_NOTES:  [MessageHandler(filters.TEXT & ~filters.COMMAND, sales_notes)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    # Expense conversation
    expense_conv = ConversationHandler(
        entry_points=[CommandHandler("expense", expense_cmd)],
        states={
            EXP_CAT:    [MessageHandler(filters.TEXT & ~filters.COMMAND, exp_cat)],
            EXP_DESC:   [MessageHandler(filters.TEXT & ~filters.COMMAND, exp_desc)],
            EXP_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, exp_amount)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("help",    help_cmd))
    app.add_handler(CommandHandler("status",  status))
    app.add_handler(stock_conv)
    app.add_handler(purchase_conv)
    app.add_handler(sales_conv)
    app.add_handler(expense_conv)
    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    logger.info("SP Dhaba Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
