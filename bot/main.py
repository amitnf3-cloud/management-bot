"""
בוט טלגרם לניהול חתימות ציוד - צנחנים
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
from db.excel_export import build_full_report, build_shortage_report, build_battalion_inventory_report
from bot import access

load_dotenv(Path(__file__).parent.parent / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

(CHOOSE_ACTION, CHOOSE_PLATOON, CHOOSE_SOLDIER, CHOOSE_ITEM, CHOOSE_QTY,
 ADD_SOLDIER_NAME, ADD_SOLDIER_PLATOON, REMOVE_SOLDIER_CONFIRM,
 BATTALION_ITEM_NAME, BATTALION_ITEM_QTY, BATTALION_ITEM_HOLDER, BATTALION_NEW_HOLDER_NAME,
 BATTALION_RETURN_HOLDER, BATTALION_RETURN_ITEM, BATTALION_RETURN_QTY) = range(15)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN לא נמצא - ודא שקובץ .env קיים ומכיל BOT_TOKEN=...")

MAIN_MENU_BUTTON = [InlineKeyboardButton("🔄 פעולה נוספת / תפריט ראשי", callback_data="menu")]

ACTION_LABELS = {"issue": "החתמה", "return": "זיכוי", "shortage": "דיווח חוסר"}

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
    prev_id = context.user_data.get(f"last_msg_{kind}")
    if prev_id:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=prev_id)
        except Exception:
            pass
    msg = await context.bot.send_message(chat_id=user_id, text=text)
    context.user_data[f"last_msg_{kind}"] = msg.message_id


async def send_private_document(context: ContextTypes.DEFAULT_TYPE, user_id: int, file_path: str,
                                 filename: str, caption: str, kind: str):
    prev_id = context.user_data.get(f"last_msg_{kind}")
    if prev_id:
        try:
            await context.bot.delete_message(chat_id=user_id, message_id=prev_id)
        except Exception:
            pass
    with open(file_path, "rb") as f:
        msg = await context.bot.send_document(chat_id=user_id, document=f, filename=filename, caption=caption)
    context.user_data[f"last_msg_{kind}"] = msg.message_id


def _do_battalion_issue(context: ContextTypes.DEFAULT_TYPE, holder_id: int, tg_id: str, performer_name: str) -> str:
    name = context.user_data["battalion_item_name"]
    qty = context.user_data["battalion_item_qty"]
    item_id, created = ops.get_or_create_battalion_equipment(name)
    ops.increase_total_quantity(item_id, qty)
    ops.issue_to_holder(holder_id, item_id, qty, tg_id, performer_name)
    note = " (פריט חדש נוצר במערכת)" if created else ""
    return f"✅ נקלט מול הגדוד: {name} x{qty}{note}"


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, via_message=False):
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
            InlineKeyboardButton("🆘 דיווח חוסר", callback_data="shortage"),
        ])
        buttons.append([
            InlineKeyboardButton("➕ הוסף חייל", callback_data="add_soldier"),
            InlineKeyboardButton("🗑️ הסר חייל", callback_data="remove_soldier"),
        ])
        buttons.append([
            InlineKeyboardButton("📦 מצב מחסן", callback_data="warehouse"),
            InlineKeyboardButton("📥 יצוא אקסל - מחלקות", callback_data="export_excel"),
        ])
        buttons.append([
            InlineKeyboardButton("🎖️ חתמנו מול הגדוד", callback_data="battalion_add"),
            InlineKeyboardButton("📤 זיכוי מול הגדוד", callback_data="battalion_return"),
        ])
        buttons.append([
            InlineKeyboardButton("📋 מלאי מול הגדוד", callback_data="battalion_inventory"),
            InlineKeyboardButton("📥 יצוא מול הגדוד", callback_data="export_battalion"),
        ])
        buttons.append([
            InlineKeyboardButton("📥 יצוא חוסרים", callback_data="export_shortage"),
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

    if action == "remove_soldier":
        if not access.can_edit(tg_id):
            await query.edit_message_text("אין לך הרשאה לפעולה הזו.",
                                           reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
            return ConversationHandler.END
        buttons = [[InlineKeyboardButton(p["name"], callback_data=f"pl_{p['id']}")]
                   for p in ops.get_platoons()]
        buttons.append(MAIN_MENU_BUTTON)
        await query.edit_message_text("הסרת חייל - בחר מחלקה:", reply_markup=InlineKeyboardMarkup(buttons))
        return CHOOSE_PLATOON

    if action == "warehouse":
        if not access.can_edit(tg_id):
            await query.edit_message_text("אין לך הרשאה לפעולה הזו.",
                                           reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
            return ConversationHandler.END
        status = ops.get_warehouse_status("personal")
        lines = [f"{s['name']}: {s['available']} במחסן (מתוך {s['total']}, מוחתם {s['issued']}, אבד {s['missing']})"
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
                filename="דוח_ציוד_מלא.xlsx", caption="📥 דוח ציוד מלא - גיליון לכל מחלקה",
                kind="export_excel"
            )
        await query.edit_message_text("✅ קובץ האקסל נשלח אליך בהודעה פרטית.",
                                       reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
        return ConversationHandler.END

    if action == "export_shortage":
        if not access.can_edit(tg_id):
            await query.edit_message_text("אין לך הרשאה לפעולה הזו.",
                                           reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
            return ConversationHandler.END
        await query.edit_message_text("⏳ מכין את קובץ האקסל...")
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = os.path.join(tmp_dir, "דוח_חוסרים.xlsx")
            build_shortage_report(file_path)
            await send_private_document(
                context, update.effective_user.id, file_path,
                filename="דוח_חוסרים.xlsx", caption="📥 דוח חוסרים", kind="export_shortage"
            )
        await query.edit_message_text("✅ קובץ החוסרים נשלח אליך בהודעה פרטית.",
                                       reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
        return ConversationHandler.END

    if action == "export_battalion":
        if not access.can_edit(tg_id):
            await query.edit_message_text("אין לך הרשאה לפעולה הזו.",
                                           reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
            return ConversationHandler.END
        await query.edit_message_text("⏳ מכין את קובץ האקסל...")
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = os.path.join(tmp_dir, "ציוד_מול_הגדוד.xlsx")
            build_battalion_inventory_report(file_path)
            await send_private_document(
                context, update.effective_user.id, file_path,
                filename="ציוד_מול_הגדוד.xlsx", caption="📥 ציוד מול הגדוד", kind="export_battalion"
            )
        await query.edit_message_text("✅ הקובץ נשלח אליך בהודעה פרטית.",
                                       reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
        return ConversationHandler.END

    if action == "battalion_inventory":
        if not access.can_edit(tg_id):
            await query.edit_message_text("אין לך הרשאה לפעולה הזו.",
                                           reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
            return ConversationHandler.END
        inventory = ops.get_battalion_inventory()
        if not inventory:
            text = "אין עדיין ציוד רשום מול הגדוד."
        else:
            lines = []
            for item in inventory:
                holders_text = ", ".join(f"{h['name']}: {h['quantity']}" for h in item["held_by"]) or "אף אחד"
                lines.append(f"{item['name']}: סה\"כ {item['total']}, במחסן {item['available']} | אצל: {holders_text}")
            text = "📋 מלאי מול הגדוד:\n\n" + "\n".join(lines)
        await send_private_report(context, update.effective_user.id, text, kind="battalion_inventory")
        await query.edit_message_text("✅ נשלח אליך בהודעה פרטית.",
                                       reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
        return ConversationHandler.END

    if action == "battalion_add":
        if not access.can_edit(tg_id):
            await query.edit_message_text("אין לך הרשאה לפעולה הזו.",
                                           reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
            return ConversationHandler.END
        await query.edit_message_text("על מה חתמנו מול הגדוד? (כתוב את שם הציוד)",
                                       reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
        return BATTALION_ITEM_NAME

    if action == "battalion_return":
        if not access.can_edit(tg_id):
            await query.edit_message_text("אין לך הרשאה לפעולה הזו.",
                                           reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
            return ConversationHandler.END
        holders = ops.get_battalion_holders()
        if not holders:
            await query.edit_message_text("אין עדיין אף איש מפל\"ג רשום מול הגדוד.",
                                           reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
            return ConversationHandler.END
        buttons = [[InlineKeyboardButton(h["name"], callback_data=f"brh_{h['id']}")] for h in holders]
        buttons.append(MAIN_MENU_BUTTON)
        await query.edit_message_text("זיכוי מול הגדוד - מי מחזיר?", reply_markup=InlineKeyboardMarkup(buttons))
        return BATTALION_RETURN_HOLDER

    if action in ("issue", "return", "shortage"):
        if not access.can_edit(tg_id):
            await query.edit_message_text("אין לך הרשאה לפעולה הזו.",
                                           reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
            return ConversationHandler.END
        buttons = [[InlineKeyboardButton(p["name"], callback_data=f"pl_{p['id']}")]
                   for p in ops.get_platoons()]
        buttons.append(MAIN_MENU_BUTTON)
        label = ACTION_LABELS[action]
        await query.edit_message_text(f"{label} - בחר מחלקה:", reply_markup=InlineKeyboardMarkup(buttons))
        return CHOOSE_PLATOON

    return ConversationHandler.END


async def choose_platoon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    tg_id = update.effective_user.id

    if data.startswith("rp_"):
        platoon_id = int(data.split("_")[1])
        rows = ops.get_platoon_report(platoon_id)
        if not rows:
            text = "אין נתונים למחלקה זו עדיין."
        else:
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
        target = data.split("_", 1)[1]
        platoon_id = None if target == "all" else int(target)
        no_items_rows = ops.get_soldiers_with_nothing(platoon_id)
        shortage_rows = ops.get_shortage_report(platoon_id)
        lines = []
        if no_items_rows:
            lines.append("👤 טרם חתמו על כלום:")
            lines += [f"  {r['full_name']} ({r['platoon']})" for r in no_items_rows]
        if shortage_rows:
            if lines:
                lines.append("")
            lines.append("📉 פריטים שדווחו חסרים:")
            lines += [f"  {r['full_name']} ({r['platoon']}): {r['item']} x{r['quantity']}" for r in shortage_rows]
        text = "⚠️ דוח חוסרים:\n\n" + "\n".join(lines) if lines else "אין חוסרים כרגע - הכל תקין."
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


async def choose_soldier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    soldier_id = int(query.data.split("_")[1])
    context.user_data["soldier_id"] = soldier_id
    action = context.user_data["action"]

    if action == "remove_soldier":
        name = ops.get_soldier_name(soldier_id)
        buttons = [
            [InlineKeyboardButton("✅ כן, הסר", callback_data=f"confirm_remove_{soldier_id}")],
            [InlineKeyboardButton("❌ ביטול", callback_data="menu")],
        ]
        await query.edit_message_text(
            f"בטוח שאתה רוצה להסיר את {name}?\nזה לא מוחק היסטוריה, רק מסמן אותו כלא-פעיל.",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return REMOVE_SOLDIER_CONFIRM

    if action in ("return", "shortage"):
        holdings = ops.get_soldier_holdings_with_ids(soldier_id)
        if not holdings:
            await query.edit_message_text(
                "החייל הזה לא מחזיק כרגע שום ציוד.",
                reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON])
            )
            return ConversationHandler.END
        buttons = [[InlineKeyboardButton(f"{h['name']} (יש: {h['quantity']})", callback_data=f"it_{h['id']}")]
                   for h in holdings]
    else:
        kit_buttons = [[InlineKeyboardButton(kit["label"], callback_data=kit_id)]
                       for kit_id, kit in KITS.items()]
        items = ops.get_equipment_types(layer="personal")
        item_buttons = [[InlineKeyboardButton(i["name"], callback_data=f"it_{i['id']}")]
                        for i in items]
        buttons = kit_buttons + item_buttons

    buttons.append(MAIN_MENU_BUTTON)
    await query.edit_message_text("בחר פריט ציוד:", reply_markup=InlineKeyboardMarkup(buttons))
    return CHOOSE_ITEM


async def confirm_remove_soldier(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    soldier_id = int(query.data.split("_")[2])
    name = ops.get_soldier_name(soldier_id)
    ops.deactivate_soldier(soldier_id)
    await query.edit_message_text(f"✅ {name} הוסר בהצלחה.",
                                   reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
    return ConversationHandler.END


async def choose_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data in KITS:
        soldier_id = context.user_data["soldier_id"]
        tg_id = str(update.effective_user.id)
        performer_name = update.effective_user.full_name
        kit = KITS[data]
        lines, missing = [], []
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
        elif action == "return":
            ops.return_equipment(soldier_id, item_id, qty, tg_id, performer_name)
            await query.edit_message_text(f"✅ זוכה בהצלחה ({qty} יח')",
                                           reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
        elif action == "shortage":
            ops.report_shortage(soldier_id, item_id, qty, tg_id, performer_name)
            await query.edit_message_text(f"✅ דווח חוסר ({qty} יח') - יופיע בדוח החוסרים",
                                           reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
    except ValueError as e:
        await query.edit_message_text(f"❌ שגיאה: {e}",
                                       reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))

    return ConversationHandler.END


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


async def battalion_item_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["battalion_item_name"] = update.message.text.strip()
    await update.message.reply_text(
        "כמה יחידות? (כתוב מספר)", reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON])
    )
    return BATTALION_ITEM_QTY


async def battalion_item_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text(
            "צריך מספר חיובי. כמה יחידות?", reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON])
        )
        return BATTALION_ITEM_QTY

    context.user_data["battalion_item_qty"] = int(text)
    holders = ops.get_battalion_holders()
    buttons = [[InlineKeyboardButton(h["name"], callback_data=f"hold_{h['id']}")] for h in holders]
    buttons.append([InlineKeyboardButton("➕ הוסף שם חדש", callback_data="new_holder")])
    buttons.append(MAIN_MENU_BUTTON)
    await update.message.reply_text("מי חתם על זה? (איש מפל\"ג)", reply_markup=InlineKeyboardMarkup(buttons))
    return BATTALION_ITEM_HOLDER


async def battalion_choose_holder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "new_holder":
        await query.edit_message_text("מה השם המלא שלו?")
        return BATTALION_NEW_HOLDER_NAME

    holder_id = int(query.data.split("_")[1])
    tg_id = str(update.effective_user.id)
    performer_name = update.effective_user.full_name
    text = _do_battalion_issue(context, holder_id, tg_id, performer_name)
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
    return ConversationHandler.END


async def battalion_new_holder_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    holder_id = ops.create_battalion_holder(name)
    tg_id = str(update.effective_user.id)
    performer_name = update.effective_user.full_name
    text = _do_battalion_issue(context, holder_id, tg_id, performer_name)
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
    return ConversationHandler.END


async def battalion_return_choose_holder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    holder_id = int(query.data.split("_")[1])
    context.user_data["battalion_holder_id"] = holder_id
    holdings = ops.get_holder_holdings_with_ids(holder_id)
    if not holdings:
        await query.edit_message_text("האיש הזה לא מחזיק כרגע שום ציוד מול הגדוד.",
                                       reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
        return ConversationHandler.END
    buttons = [[InlineKeyboardButton(f"{h['name']} (יש: {h['quantity']})", callback_data=f"bri_{h['id']}")]
               for h in holdings]
    buttons.append(MAIN_MENU_BUTTON)
    await query.edit_message_text("על איזה פריט מזכים?", reply_markup=InlineKeyboardMarkup(buttons))
    return BATTALION_RETURN_ITEM


async def battalion_return_choose_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_id = int(query.data.split("_")[1])
    context.user_data["battalion_return_item_id"] = item_id
    buttons = [
        [InlineKeyboardButton(str(n), callback_data=f"brq_{n}") for n in range(1, 6)],
        [InlineKeyboardButton(str(n), callback_data=f"brq_{n}") for n in range(6, 11)],
    ]
    buttons.append(MAIN_MENU_BUTTON)
    await query.edit_message_text("כמה יחידות מזכים?", reply_markup=InlineKeyboardMarkup(buttons))
    return BATTALION_RETURN_QTY


async def battalion_return_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qty = int(query.data.split("_")[1])
    holder_id = context.user_data["battalion_holder_id"]
    item_id = context.user_data["battalion_return_item_id"]
    tg_id = str(update.effective_user.id)
    performer_name = update.effective_user.full_name

    try:
        ops.return_from_battalion(holder_id, item_id, qty, tg_id, performer_name)
        await query.edit_message_text(
            f"✅ זוכה בהצלחה מול הגדוד ({qty} יח') - ירד גם מהתכולה הכוללת שלנו",
            reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON])
        )
    except ValueError as e:
        await query.edit_message_text(f"❌ שגיאה: {e}", reply_markup=InlineKeyboardMarkup([MAIN_MENU_BUTTON]))
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
            REMOVE_SOLDIER_CONFIRM: [
                CallbackQueryHandler(back_to_menu, pattern="^menu$"),
                CallbackQueryHandler(confirm_remove_soldier, pattern="^confirm_remove_"),
            ],
            BATTALION_ITEM_NAME: [
                CallbackQueryHandler(back_to_menu, pattern="^menu$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, battalion_item_name),
            ],
            BATTALION_ITEM_QTY: [
                CallbackQueryHandler(back_to_menu, pattern="^menu$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, battalion_item_qty),
            ],
            BATTALION_ITEM_HOLDER: [
                CallbackQueryHandler(back_to_menu, pattern="^menu$"),
                CallbackQueryHandler(battalion_choose_holder),
            ],
            BATTALION_NEW_HOLDER_NAME: [
                CallbackQueryHandler(back_to_menu, pattern="^menu$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, battalion_new_holder_name),
            ],
            BATTALION_RETURN_HOLDER: [
                CallbackQueryHandler(back_to_menu, pattern="^menu$"),
                CallbackQueryHandler(battalion_return_choose_holder),
            ],
            BATTALION_RETURN_ITEM: [
                CallbackQueryHandler(back_to_menu, pattern="^menu$"),
                CallbackQueryHandler(battalion_return_choose_item),
            ],
            BATTALION_RETURN_QTY: [
                CallbackQueryHandler(back_to_menu, pattern="^menu$"),
                CallbackQueryHandler(battalion_return_qty),
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
