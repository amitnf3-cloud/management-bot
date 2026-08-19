"""
בוט טלגרם לניהול חתימות ציוד - צנחנים
תפריט מונחה: החתמה / זיכוי / דוח מחלקה
"""
import os
import sys
import logging
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, MessageHandler, filters
)

from db import operations as ops
from db.excel_export import build_full_report
from bot import access

# טוען את הטוקן מקובץ .env (לא מקודד בתוך הקוד עצמו)
load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------------------------------------
# מצבי השיחה (Conversation States)
# ------------------------------------------------
CHOOSE_ACTION, CHOOSE_PLATOON, CHOOSE_SOLDIER, CHOOSE_ITEM, CHOOSE_QTY, ADD_SOLDIER_NAME, ADD_SOLDIER_PLATOON = range(7)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN לא נמצא - ודא שקובץ .env קיים ומכיל BOT_TOKEN=...")


MAIN_MENU_BUTTON = [InlineKeyboardButton("🔄 פעולה נוספת / תפריט ראשי", callback_data="menu")]

# ------------------------------------------------
# ערכות (קיטים) - החתמה מהירה של כמה פריטים בבת אחת
# ------------------------------------------------
KITS = {
    "kit_rifle": {
        "label": "🎖️ ציוד רובאי מלא",
        "items": [
            ("וסט לוחם", 1), ("מחסניות", 6), ("שלוקר", 1),
            ("משקפי מגן", 1), ("ח\"ע", 1), ("תא - ציוד רפואי אישי", 1),
            ("קסדה", 1), ("בירכיות", 2), ("פאוץ גב", 1),
        ],
    },
    "kit_negev_mag": {
        "label": "🔫 ציוד לחימה מלא - נגב/מאג",
        "items": [
            ("וסט מאג/נגב", 1), ("תוף", 4), ("שלוקר", 1),
            ("משקפי מגן", 1), ("ח\"ע", 1), ("תא - ציוד רפואי אישי", 1),
            ("קסדה", 1), ("בירכיות", 2),
        ],
    },
}


async def send_private_report(context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str, kind: str):
    """שולח דוח בהודעה פרטית, ומוחק את הדוח הקודם מאותו סוג (אם קיים) - כדי שהצ'אט יישאר נקי ומהיר"""
    prev_id = context.user_data.get(f"last_msg_{kind}")
    if prev_id:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=prev_id)
        except Exception:
            pass  # ההודעה כבר נמחקה/ישנה מדי - לא קריטי
    msg = await context.bot.send_message(chat_id=user_id, text=text)
    context.user_data[f"last_msg_{kind}"] = msg.message_id


async def send_private_document(context: ContextTypes.DEFAULT_TYPE, user_id: int, file_path: str,
                                 filename: str, caption: str, kind: str):
    """שולח קובץ בהודעה פרטית, ומוחק את הקובץ הקודם מאותו סוג - אותו עיקרון כמו send_private_report"""
    prev_id = context.user_data.get(f"last_msg_{kind}")
    if prev_id:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=prev_id)
        except Exception:
            pass
    with open(file_path, "rb") as f:
        msg = await context.bot.send_document(chat_id=user_id, document=f, filename=filename, caption=caption)
    context.user_data[f"last_msg_{kind}"] = msg.message_id


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, via_message=False):
    """מציג את התפריט הראשי - גם בפעם הראשונה וגם בחזרה מכפתור"""
    user = update.effective_user
    tg_id = str(user.id)
    level = access.get_access_level(tg_id)

    if level is None:
        text = "לא זוהית כמשתמש מורשה במערכת. פנה לרספ כדי להוסיף אותך."
        if via_message:
            await update.message.reply_text(text)
        else:
            await update.callback_query.edit_message_text(text)
        return ConversationHandler.END

    buttons = [[InlineKeyboardButton("📊 דוח מחלקה", callback_data="report")]]
    if access.can_edit(tg_id):
        buttons.insert(0, [
            InlineKeyboardButton("📤 החתמה", callback_data="issue"),
            InlineKeyboardButton("📥 זיכוי", callback_data="return"),
        ])
        buttons.append([
            InlineKeyboardButton("⚠️ דוח חוסרים", callback_data="missing"),
            InlineKeyboardButton("➕ הוסף חייל", callback_data="add_soldier"),
        ])
        buttons.append([
            InlineKeyboardButton("📦 מצב מחסן", callback_data="warehouse"),
            InlineKeyboardButton("📥 ייצוא לאקסל", callback_data="export_excel"),
        ])

    if via_message:
        await update.message.reply_text("מה תרצה לעשות?", reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.callback_query.edit_message_text("מה תרצה לעשות?", reply_markup=InlineKeyboardMarkup(buttons))
    return CHOOSE_ACTION


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await show_main_menu(update, context, via_message=True)


async def back_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return await show_main_menu(update, context, via_message=False)


async def choose_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data
    context.user_data["action"] = action
    tg_id = str(update.effective_user.id)

    if action == "report":
        buttons = [[InlineKeyboardButton(p["name"], callback_data=f"rp_{p['id']}")]
                   for p in ops.get_platoons()]
        buttons.append(MAIN_MENU_BUTTON)
        await query.edit_message_text("בחר מחלקה לדוח:", reply_markup=InlineKeyboardMarkup(buttons))
        return CHOOSE_PLATOON

    if action == "missing":
        if not access.can_edit(tg_id):
            await query.edit_message_text("אין לך הרשאה לפעולה הזו.",
                                           reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
            return ConversationHandler.END
        buttons = [[InlineKeyboardButton("כל הפלוגה", callback_data="ms_all")]]
        buttons += [[InlineKeyboardButton(p["name"], callback_data=f"ms_{p['id']}")]
                    for p in ops.get_platoons()]
        buttons.append(MAIN_MENU_BUTTON)
        await query.edit_message_text("דוח חוסרים - בחר מחלקה:", reply_markup=InlineKeyboardMarkup(buttons))
        return CHOOSE_PLATOON

    if action == "add_soldier":
        if not access.can_edit(tg_id):
            await query.edit_message_text("אין לך הרשאה לפעולה הזו.",
                                           reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
            return ConversationHandler.END
        await query.edit_message_text("כתוב את שם החייל המלא:",
                                       reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
        return ADD_SOLDIER_NAME

    if action == "warehouse":
        if not access.can_edit(tg_id):
            await query.edit_message_text("אין לך הרשאה לפעולה הזו.",
                                           reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
            return ConversationHandler.END
        status = ops.get_warehouse_status("personal")
        lines = [f"{s['name']}: {s['available']} במחסן (מתוך {s['total']}, מוחתם {s['issued']})"
                 for s in status]
        text = "📦 מצב מחסן (ציוד אישי):\n\n" + "\n".join(lines)
        await send_private_report(context, update.effective_user.id, text, kind="warehouse")
        await query.edit_message_text("✅ מצב המחסן נשלח אליך בהודעה פרטית.",
                                       reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
        return ConversationHandler.END

    if action == "export_excel":
        if not access.can_edit(tg_id):
            await query.edit_message_text("אין לך הרשאה לפעולה הזו.",
                                           reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
            return ConversationHandler.END
        await query.edit_message_text("⏳ מכין את קובץ האקסל...")
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = os.path.join(tmp_dir, "דוח_ציוד_מלא.xlsx")
            build_full_report(file_path)
            await send_private_document(
                context, update.effective_user.id, file_path,
                filename="דוח_ציוד_מלא.xlsx",
                caption="📥 דוח ציוד מלא - גיליון לכל מחלקה",
                kind="export_excel"
            )
        await query.edit_message_text("✅ קובץ האקסל נשלח אליך בהודעה פרטית.",
                                       reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
        return ConversationHandler.END

    # issue / return - צריך לבחור חייל קודם
    if not access.can_edit(tg_id):
        await query.edit_message_text("אין לך הרשאה לפעולה הזו.",
                                       reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
        return ConversationHandler.END

    buttons = [[InlineKeyboardButton(p["name"], callback_data=f"pl_{p['id']}")]
               for p in ops.get_platoons()]
    buttons.append(MAIN_MENU_BUTTON)
    label = "החתמה" if action == "issue" else "זיכוי"
    await query.edit_message_text(f"{label} - בחר מחלקה:", reply_markup=InlineKeyboardMarkup(buttons))
    return CHOOSE_PLATOON


async def choose_platoon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    tg_id = update.effective_user.id

    if data.startswith("rp_"):
        # דוח מחלקה מלא - מכיל שמות ופרטי ציוד, נשלח בפרטי בלבד
        platoon_id = int(data.split("_")[1])
        rows = ops.get_platoon_report(platoon_id)
        if not rows:
            text = "אין נתונים למחלקה זו עדיין."
        else:
            # קיבוץ לפי חייל - שורה אחת לכל אחד, פריטים מופרדים בפסיקים
            grouped = {}
            for r in rows:
                grouped.setdefault(r["full_name"], []).append(f"{r['item']} x{r['quantity']}")
            lines = [f"{name}: {', '.join(items)}" for name, items in grouped.items()]
            text = "📊 דוח מחלקה:\n\n" + "\n".join(lines)
        await send_private_report(context, tg_id, text, kind="platoon_report")
        await query.edit_message_text("✅ הדוח נשלח אליך בהודעה פרטית.",
                                       reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
        return ConversationHandler.END

    if data.startswith("ms_"):
        # דוח חוסרים - גם הוא מכיל שמות, נשלח בפרטי
        target = data.split("_", 1)[1]
        platoon_id = None if target == "all" else int(target)
        rows = ops.get_soldiers_with_nothing(platoon_id)
        if not rows:
            text = "אין חוסרים - כולם חתומים על משהו."
        else:
            lines = [f"{r['full_name']} ({r['platoon']})" for r in rows]
            text = "⚠️ טרם חתמו על כלום:\n\n" + "\n".join(lines)
        await send_private_report(context, tg_id, text, kind="missing_report")
        await query.edit_message_text("✅ דוח החוסרים נשלח אליך בהודעה פרטית.",
                                       reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
        return ConversationHandler.END

    platoon_id = int(data.split("_")[1])
    context.user_data["platoon_id"] = platoon_id
    soldiers = ops.get_soldiers_by_platoon(platoon_id)
    if not soldiers:
        await query.edit_message_text("אין חיילים רשומים במחלקה זו עדיין.",
                                       reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
        return ConversationHandler.END

    buttons = [[InlineKeyboardButton(s["full_name"], callback_data=f"sd_{s['id']}")]
               for s in soldiers]
    buttons.append(MAIN_MENU_BUTTON)
    await query.edit_message_text("בחר חייל:", reply_markup=InlineKeyboardMarkup(buttons))
    return CHOOSE_SOLDIER


async def add_soldier_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_soldier_name"] = update.message.text.strip()
    buttons = [[InlineKeyboardButton(p["name"], callback_data=f"asp_{p['id']}")]
               for p in ops.get_platoons()]
    buttons.append(MAIN_MENU_BUTTON)
    await update.message.reply_text("לאיזו מחלקה?", reply_markup=InlineKeyboardMarkup(buttons))
    return ADD_SOLDIER_PLATOON


async def add_soldier_platoon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    platoon_id = int(query.data.split("_")[1])
    name = context.user_data["new_soldier_name"]
    ops.add_soldier(name, platoon_id)
    await query.edit_message_text(f"✅ החייל {name} נוסף בהצלחה, חתום על 0 פריטים.",
                                   reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
    return ConversationHandler.END


async def choose_soldier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    soldier_id = int(query.data.split("_")[1])
    context.user_data["soldier_id"] = soldier_id
    action = context.user_data["action"]

    if action == "return":
        # בזיכוי מציגים רק פריטים שהחייל בפועל מחזיק - מונע טעויות וטרחה מיותרת
        holdings = ops.get_soldier_holdings_with_ids(soldier_id)
        if not holdings:
            await query.edit_message_text(
                "החייל הזה לא מחזיק כרגע שום ציוד, אין מה לזכות.",
                reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON])
            )
            return ConversationHandler.END
        buttons = [[InlineKeyboardButton(f"{h['name']} (יש: {h['quantity']})", callback_data=f"it_{h['id']}")]
                   for h in holdings]
    else:
        # בהחתמה מציגים קודם את הערכות המהירות (קיטים), ואז את כל סוגי הציוד הבודדים
        kit_buttons = [[InlineKeyboardButton(kit["label"], callback_data=kit_id)]
                       for kit_id, kit in KITS.items()]
        items = ops.get_equipment_types(layer="personal")
        item_buttons = [[InlineKeyboardButton(i["name"], callback_data=f"it_{i['id']}")]
                        for i in items]
        buttons = kit_buttons + item_buttons

    buttons.append(MAIN_MENU_BUTTON)
    await query.edit_message_text("בחר פריט ציוד:", reply_markup=InlineKeyboardMarkup(buttons))
    return CHOOSE_ITEM


async def choose_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data in KITS:
        # ערכה מהירה - מחתימים את כל הפריטים בבת אחת בכמויות שנקבעו מראש
        soldier_id = context.user_data["soldier_id"]
        tg_id = str(update.effective_user.id)
        performer_name = update.effective_user.full_name
        kit = KITS[data]

        lines = []
        missing = []
        for item_name, qty in kit["items"]:
            item_id = ops.get_equipment_type_id_by_name(item_name)
            if item_id is None:
                missing.append(item_name)
                continue
            ops.issue_equipment(soldier_id, item_id, qty, tg_id, performer_name)
            lines.append(f"{item_name} x{qty}")

        text = f"✅ הוחתם {kit['label']}:\n\n" + "\n".join(lines)
        if missing:
            text += "\n\n⚠️ לא נמצאו במערכת (דולגו): " + ", ".join(missing)
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
        return ConversationHandler.END

    item_id = int(data.split("_")[1])
    context.user_data["item_id"] = item_id

    buttons = [
        [InlineKeyboardButton(str(n), callback_data=f"qty_{n}") for n in range(1, 6)],
        [InlineKeyboardButton(str(n), callback_data=f"qty_{n}") for n in range(6, 11)],
    ]
    buttons.append(MAIN_MENU_BUTTON)
    await query.edit_message_text("כמה יחידות?", reply_markup=InlineKeyboardMarkup(buttons))
    return CHOOSE_QTY


async def choose_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[1])

    action = context.user_data["action"]
    soldier_id = context.user_data["soldier_id"]
    item_id = context.user_data["item_id"]
    tg_id = str(update.effective_user.id)
    performer_name = update.effective_user.full_name

    try:
        if action == "issue":
            ops.issue_equipment(soldier_id, item_id, qty, tg_id, performer_name)
            await query.edit_message_text(f"✅ הוחתם בהצלחה ({qty} יח')",
                                           reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
        else:
            ops.return_equipment(soldier_id, item_id, qty, tg_id, performer_name)
            await query.edit_message_text(f"✅ זוכה בהצלחה ({qty} יח')",
                                           reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
    except ValueError as e:
        await query.edit_message_text(f"❌ שגיאה: {e}",
                                       reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("בוטל.")
    return ConversationHandler.END


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(back_to_menu, pattern="^menu$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, start),
        ],
        states={
            CHOOSE_ACTION: [CallbackQueryHandler(choose_action)],
            CHOOSE_PLATOON: [
                CallbackQueryHandler(back_to_menu, pattern="^menu$"),
                CallbackQueryHandler(choose_platoon),
            ],
            CHOOSE_SOLDIER: [
                CallbackQueryHandler(back_to_menu, pattern="^menu$"),
                CallbackQueryHandler(choose_soldier),
            ],
            CHOOSE_ITEM: [
                CallbackQueryHandler(back_to_menu, pattern="^menu$"),
                CallbackQueryHandler(choose_item),
            ],
            CHOOSE_QTY: [
                CallbackQueryHandler(back_to_menu, pattern="^menu$"),
                CallbackQueryHandler(choose_qty),
            ],
            ADD_SOLDIER_NAME: [
                CallbackQueryHandler(back_to_menu, pattern="^menu$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_soldier_name),
            ],
            ADD_SOLDIER_PLATOON: [
                CallbackQueryHandler(back_to_menu, pattern="^menu$"),
                CallbackQueryHandler(add_soldier_platoon),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(back_to_menu, pattern="^menu$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, start),
        ],
    )
    app.add_handler(conv)

    logger.info("הבוט עולה...")
    app.run_polling()


if __name__ == "__main__":
    main()
