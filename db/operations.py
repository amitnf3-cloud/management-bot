"""
שכבת גישה למסד הנתונים - פעולות ליבה
זיכוי / החתמה / דוחות
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "equipment.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def issue_equipment(soldier_id: int, equipment_type_id: int, quantity: int,
                     performed_by_tg_id: str = None, performed_by_name: str = None,
                     notes: str = None):
    """החתמה - נותן ציוד לחייל"""
    conn = get_conn()
    try:
        # עדכון / יצירת שורה בטבלת המצב הנוכחי
        existing = conn.execute(
            "SELECT id, quantity FROM current_holdings WHERE soldier_id=? AND equipment_type_id=?",
            (soldier_id, equipment_type_id)
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE current_holdings SET quantity = quantity + ?, updated_at = datetime('now') WHERE id=?",
                (quantity, existing["id"])
            )
        else:
            conn.execute(
                "INSERT INTO current_holdings (soldier_id, equipment_type_id, quantity) VALUES (?, ?, ?)",
                (soldier_id, equipment_type_id, quantity)
            )

        # רישום בלוג ההיסטוריה
        conn.execute(
            """INSERT INTO transactions
               (action, soldier_id, equipment_type_id, quantity, performed_by_tg_id, performed_by_name, notes)
               VALUES ('issue', ?, ?, ?, ?, ?, ?)""",
            (soldier_id, equipment_type_id, quantity, performed_by_tg_id, performed_by_name, notes)
        )
        conn.commit()
        return True
    finally:
        conn.close()


def return_equipment(soldier_id: int, equipment_type_id: int, quantity: int,
                      performed_by_tg_id: str = None, performed_by_name: str = None,
                      notes: str = None):
    """זיכוי - מחזיר ציוד מחייל"""
    conn = get_conn()
    try:
        existing = conn.execute(
            "SELECT id, quantity FROM current_holdings WHERE soldier_id=? AND equipment_type_id=?",
            (soldier_id, equipment_type_id)
        ).fetchone()

        if not existing or existing["quantity"] < quantity:
            raise ValueError("לא ניתן לזכות יותר ממה שהחייל מחזיק בפועל")

        new_qty = existing["quantity"] - quantity
        if new_qty == 0:
            conn.execute("DELETE FROM current_holdings WHERE id=?", (existing["id"],))
        else:
            conn.execute(
                "UPDATE current_holdings SET quantity = ?, updated_at = datetime('now') WHERE id=?",
                (new_qty, existing["id"])
            )

        conn.execute(
            """INSERT INTO transactions
               (action, soldier_id, equipment_type_id, quantity, performed_by_tg_id, performed_by_name, notes)
               VALUES ('return', ?, ?, ?, ?, ?, ?)""",
            (soldier_id, equipment_type_id, quantity, performed_by_tg_id, performed_by_name, notes)
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_soldier_holdings_with_ids(soldier_id: int):
    """מה חייל מחזיק כרגע, כולל ID הפריט - משמש לתפריט הזיכוי (מציג רק מה שיש לו)"""
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT et.id, et.name, ch.quantity
               FROM current_holdings ch
               JOIN equipment_types et ON et.id = ch.equipment_type_id
               WHERE ch.soldier_id = ?
               ORDER BY et.name""",
            (soldier_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_soldier_status(soldier_id: int):
    """מה חייל ספציפי מחזיק כרגע"""
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT et.name, ch.quantity
               FROM current_holdings ch
               JOIN equipment_types et ON et.id = ch.equipment_type_id
               WHERE ch.soldier_id = ?
               ORDER BY et.name""",
            (soldier_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_platoon_report(platoon_id: int):
    """דוח מלא למחלקה - מי מחזיק מה"""
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT s.full_name, et.name AS item, ch.quantity
               FROM soldiers s
               JOIN current_holdings ch ON ch.soldier_id = s.id
               JOIN equipment_types et ON et.id = ch.equipment_type_id
               WHERE s.platoon_id = ? AND s.is_active = 1
               ORDER BY s.full_name, et.name""",
            (platoon_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_soldiers_with_nothing(platoon_id: int = None):
    """דוח חוסרים - חיילים שעדיין לא חתמו על כלום (או במחלקה ספציפית)"""
    conn = get_conn()
    try:
        query = """SELECT s.id, s.full_name, p.name AS platoon
                   FROM soldiers s
                   JOIN platoons p ON p.id = s.platoon_id
                   WHERE s.is_active = 1
                   AND s.id NOT IN (SELECT DISTINCT soldier_id FROM current_holdings WHERE soldier_id IS NOT NULL)"""
        params = ()
        if platoon_id:
            query += " AND s.platoon_id = ?"
            params = (platoon_id,)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_equipment_type_id_by_name(name: str):
    """מחזיר את ה-ID של סוג ציוד לפי שם מדויק - משמש להרכבת ערכות (קיטים)"""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id FROM equipment_types WHERE name = ? AND is_active = 1", (name,)
        ).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


def get_warehouse_status(layer: str = "personal"):
    """מצב מחסן - לכל סוג ציוד: סה'כ במלאי, כמה מוחתם, כמה נשאר במחסן.
    'נשאר במחסן' מחושב אוטומטית (total_quantity פחות כל מה שרשום כמוחתם כרגע ב-current_holdings) -
    כל החתמה/זיכוי כבר מעדכן את current_holdings, כך שהמספר תמיד עדכני בלי צורך בעדכון נפרד."""
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT et.name, et.total_quantity, COALESCE(SUM(ch.quantity), 0) AS issued
               FROM equipment_types et
               LEFT JOIN current_holdings ch ON ch.equipment_type_id = et.id
               WHERE et.layer = ? AND et.is_active = 1
               GROUP BY et.id
               ORDER BY et.name""",
            (layer,)
        ).fetchall()
        result = []
        for r in rows:
            total, issued = r["total_quantity"], r["issued"]
            result.append({"name": r["name"], "total": total, "issued": issued, "available": total - issued})
        return result
    finally:
        conn.close()


def get_full_report_matrix(layer: str = "personal"):
    """נתונים לדוח אקסל - לכל מחלקה: רשימת חיילים X סוגי ציוד, עם הכמות שכל אחד מחזיק"""
    item_names = [i["name"] for i in get_equipment_types(layer)]
    platoons_data = []
    for platoon in get_platoons():
        soldiers = get_soldiers_by_platoon(platoon["id"])
        rows = get_platoon_report(platoon["id"])
        by_name = {}
        for r in rows:
            by_name.setdefault(r["full_name"], {})[r["item"]] = r["quantity"]
        platoons_data.append({
            "platoon_name": platoon["name"],
            "soldiers": [
                {"full_name": s["full_name"], "items": by_name.get(s["full_name"], {})}
                for s in soldiers
            ],
        })
    return item_names, platoons_data


def get_platoons():
    """רשימת כל המחלקות"""
    conn = get_conn()
    try:
        rows = conn.execute("SELECT id, name FROM platoons ORDER BY id").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_soldiers_by_platoon(platoon_id: int):
    """רשימת חיילים פעילים במחלקה מסוימת"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, full_name FROM soldiers WHERE platoon_id = ? AND is_active = 1 ORDER BY full_name",
            (platoon_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_equipment_types(layer: str = "personal"):
    """רשימת סוגי ציוד לפי שכבה (personal/company/battalion)"""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT id, name, unit FROM equipment_types WHERE layer = ? AND is_active = 1 ORDER BY name",
            (layer,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def add_soldier(full_name: str, platoon_id: int, personal_number: str = None):
    """הוספה מהירה של חייל חדש"""
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO soldiers (full_name, platoon_id, personal_number) VALUES (?, ?, ?)",
            (full_name, platoon_id, personal_number)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()
