"""
שכבת גישה למסד הנתונים - PostgreSQL (RDS)
"""
import os
from pathlib import Path
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# טוענים את ה-.env כאן, ברמת המודול - כך שכל סקריפט שמייבא את הקובץ הזה
# (לא רק bot/main.py) יקבל אוטומטית את פרטי ההתחברות, בלי לזכור לקרוא load_dotenv() בעצמו
load_dotenv(Path(__file__).parent.parent / ".env")


def get_conn():
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "database-1.c7ggwak60lzg.eu-north-1.rds.amazonaws.com"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        cursor_factory=psycopg2.extras.RealDictCursor
    )
    return conn


def issue_equipment(soldier_id, equipment_type_id, quantity,
                     performed_by_tg_id=None, performed_by_name=None, notes=None):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, quantity FROM current_holdings WHERE soldier_id=%s AND equipment_type_id=%s",
            (soldier_id, equipment_type_id)
        )
        existing = cur.fetchone()
        if existing:
            cur.execute(
                "UPDATE current_holdings SET quantity = quantity + %s, updated_at = NOW() WHERE id=%s",
                (quantity, existing["id"])
            )
        else:
            cur.execute(
                "INSERT INTO current_holdings (soldier_id, equipment_type_id, quantity) VALUES (%s, %s, %s)",
                (soldier_id, equipment_type_id, quantity)
            )
        cur.execute(
            """INSERT INTO transactions
               (action, soldier_id, equipment_type_id, quantity, performed_by_tg_id, performed_by_name, notes)
               VALUES ('issue', %s, %s, %s, %s, %s, %s)""",
            (soldier_id, equipment_type_id, quantity, performed_by_tg_id, performed_by_name, notes)
        )
        conn.commit()
        return True
    finally:
        conn.close()


def return_equipment(soldier_id, equipment_type_id, quantity,
                      performed_by_tg_id=None, performed_by_name=None, notes=None):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, quantity FROM current_holdings WHERE soldier_id=%s AND equipment_type_id=%s",
            (soldier_id, equipment_type_id)
        )
        existing = cur.fetchone()
        if not existing or existing["quantity"] < quantity:
            raise ValueError("לא ניתן לזכות יותר ממה שהחייל מחזיק בפועל")
        new_qty = existing["quantity"] - quantity
        if new_qty == 0:
            cur.execute("DELETE FROM current_holdings WHERE id=%s", (existing["id"],))
        else:
            cur.execute(
                "UPDATE current_holdings SET quantity = %s, updated_at = NOW() WHERE id=%s",
                (new_qty, existing["id"])
            )
        cur.execute(
            """INSERT INTO transactions
               (action, soldier_id, equipment_type_id, quantity, performed_by_tg_id, performed_by_name, notes)
               VALUES ('return', %s, %s, %s, %s, %s, %s)""",
            (soldier_id, equipment_type_id, quantity, performed_by_tg_id, performed_by_name, notes)
        )
        conn.commit()
        return True
    finally:
        conn.close()


def report_shortage(soldier_id, equipment_type_id, quantity,
                     performed_by_tg_id=None, performed_by_name=None, notes=None):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, quantity FROM current_holdings WHERE soldier_id=%s AND equipment_type_id=%s",
            (soldier_id, equipment_type_id)
        )
        existing = cur.fetchone()
        if not existing or existing["quantity"] < quantity:
            raise ValueError("לא ניתן לדווח חוסר על יותר ממה שהחייל מחזיק בפועל")
        new_qty = existing["quantity"] - quantity
        if new_qty == 0:
            cur.execute("DELETE FROM current_holdings WHERE id=%s", (existing["id"],))
        else:
            cur.execute(
                "UPDATE current_holdings SET quantity = %s, updated_at = NOW() WHERE id=%s",
                (new_qty, existing["id"])
            )
        cur.execute(
            "INSERT INTO shortages (soldier_id, equipment_type_id, quantity, reported_by_tg_id, reported_by_name, notes) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (soldier_id, equipment_type_id, quantity, performed_by_tg_id, performed_by_name, notes)
        )
        cur.execute(
            """INSERT INTO transactions
               (action, soldier_id, equipment_type_id, quantity, performed_by_tg_id, performed_by_name, notes)
               VALUES ('missing', %s, %s, %s, %s, %s, %s)""",
            (soldier_id, equipment_type_id, quantity, performed_by_tg_id, performed_by_name, notes)
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_shortage_report(platoon_id=None):
    conn = get_conn()
    try:
        cur = conn.cursor()
        query = """SELECT s.full_name, p.name AS platoon, et.name AS item, sh.quantity
                   FROM shortages sh
                   JOIN soldiers s ON s.id = sh.soldier_id
                   JOIN platoons p ON p.id = s.platoon_id
                   JOIN equipment_types et ON et.id = sh.equipment_type_id"""
        params = ()
        if platoon_id:
            query += " WHERE s.platoon_id = %s"
            params = (platoon_id,)
        query += " ORDER BY s.full_name, et.name"
        cur.execute(query, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_soldier_status(soldier_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT et.name, ch.quantity FROM current_holdings ch
               JOIN equipment_types et ON et.id = ch.equipment_type_id
               WHERE ch.soldier_id = %s ORDER BY et.name""",
            (soldier_id,)
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_soldier_holdings_with_ids(soldier_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT et.id, et.name, ch.quantity FROM current_holdings ch
               JOIN equipment_types et ON et.id = ch.equipment_type_id
               WHERE ch.soldier_id = %s ORDER BY et.name""",
            (soldier_id,)
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_platoon_report(platoon_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT s.full_name, et.name AS item, ch.quantity
               FROM soldiers s
               JOIN current_holdings ch ON ch.soldier_id = s.id
               JOIN equipment_types et ON et.id = ch.equipment_type_id
               WHERE s.platoon_id = %s AND s.is_active = 1
               ORDER BY s.full_name, et.name""",
            (platoon_id,)
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_soldiers_with_nothing(platoon_id=None):
    conn = get_conn()
    try:
        cur = conn.cursor()
        query = """SELECT s.id, s.full_name, p.name AS platoon
                   FROM soldiers s
                   JOIN platoons p ON p.id = s.platoon_id
                   WHERE s.is_active = 1
                   AND s.id NOT IN (SELECT DISTINCT soldier_id FROM current_holdings WHERE soldier_id IS NOT NULL)"""
        params = ()
        if platoon_id:
            query += " AND s.platoon_id = %s"
            params = (platoon_id,)
        cur.execute(query, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_equipment_type_id_by_name(name):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM equipment_types WHERE name = %s AND is_active = 1", (name,))
        row = cur.fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


def get_or_create_battalion_equipment(name):
    """מחפש פריט ציוד 'מול הגדוד' לפי שם, ואם לא קיים - יוצר אותו (טקסט חופשי)"""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM equipment_types WHERE name = %s AND layer = 'battalion'", (name,))
        row = cur.fetchone()
        if row:
            return row["id"], False
        cur.execute(
            "INSERT INTO equipment_types (name, layer, total_quantity) VALUES (%s, 'battalion', 0) RETURNING id",
            (name,)
        )
        new_id = cur.fetchone()["id"]
        conn.commit()
        return new_id, True
    finally:
        conn.close()


def increase_total_quantity(equipment_type_id, delta):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE equipment_types SET total_quantity = total_quantity + %s WHERE id = %s",
            (delta, equipment_type_id)
        )
        conn.commit()
    finally:
        conn.close()


def get_battalion_holders():
    """רשימת אנשי מפל\"ג שכבר חתמו על משהו מול הגדוד בעבר (לבחירה מרשימה, נמנע מכפילויות)"""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM holders WHERE holder_type = 'battalion' ORDER BY name")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def create_battalion_holder(name):
    """יוצר איש מפל\"ג חדש ברשימה (כשמישהו מקליד שם שלא היה קודם)"""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO holders (name, holder_type, platoon_id) VALUES (%s, 'battalion', NULL) RETURNING id",
            (name,)
        )
        new_id = cur.fetchone()["id"]
        conn.commit()
        return new_id
    finally:
        conn.close()


def issue_to_holder(holder_id, equipment_type_id, quantity,
                     performed_by_tg_id=None, performed_by_name=None, notes=None):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, quantity FROM current_holdings WHERE holder_id=%s AND equipment_type_id=%s",
            (holder_id, equipment_type_id)
        )
        existing = cur.fetchone()
        if existing:
            cur.execute(
                "UPDATE current_holdings SET quantity = quantity + %s, updated_at = NOW() WHERE id=%s",
                (quantity, existing["id"])
            )
        else:
            cur.execute(
                "INSERT INTO current_holdings (holder_id, equipment_type_id, quantity) VALUES (%s, %s, %s)",
                (holder_id, equipment_type_id, quantity)
            )
        cur.execute(
            """INSERT INTO transactions
               (action, holder_id, equipment_type_id, quantity, performed_by_tg_id, performed_by_name, notes)
               VALUES ('issue', %s, %s, %s, %s, %s, %s)""",
            (holder_id, equipment_type_id, quantity, performed_by_tg_id, performed_by_name, notes)
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_holder_holdings_with_ids(holder_id):
    """מה מחזיק (איש מפל'ג) מחזיק כרגע - לצורך תפריט הזיכוי מול הגדוד"""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT et.id, et.name, ch.quantity FROM current_holdings ch
               JOIN equipment_types et ON et.id = ch.equipment_type_id
               WHERE ch.holder_id = %s ORDER BY et.name""",
            (holder_id,)
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def return_from_battalion(holder_id, equipment_type_id, quantity,
                           performed_by_tg_id=None, performed_by_name=None, notes=None):
    """זיכוי ציוד בחזרה לגדוד - בניגוד לזיכוי רגיל, זה גם מוריד מהתכולה הכוללת שלנו
    (כי הציוד עוזב את הפלוגה לגמרי, לא חוזר ל'זמין במחסן שלנו')"""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, quantity FROM current_holdings WHERE holder_id=%s AND equipment_type_id=%s",
            (holder_id, equipment_type_id)
        )
        existing = cur.fetchone()
        if not existing or existing["quantity"] < quantity:
            raise ValueError("לא ניתן לזכות יותר ממה שרשום כמוחתם")
        new_qty = existing["quantity"] - quantity
        if new_qty == 0:
            cur.execute("DELETE FROM current_holdings WHERE id=%s", (existing["id"],))
        else:
            cur.execute(
                "UPDATE current_holdings SET quantity = %s, updated_at = NOW() WHERE id=%s",
                (new_qty, existing["id"])
            )
        cur.execute(
            "UPDATE equipment_types SET total_quantity = total_quantity - %s WHERE id = %s",
            (quantity, equipment_type_id)
        )
        cur.execute(
            """INSERT INTO transactions
               (action, holder_id, equipment_type_id, quantity, performed_by_tg_id, performed_by_name, notes)
               VALUES ('return', %s, %s, %s, %s, %s, %s)""",
            (holder_id, equipment_type_id, quantity, performed_by_tg_id, performed_by_name, notes)
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_battalion_inventory():
    """מלאי הציוד מול הגדוד - לכל פריט: סה'כ, אצל איזה איש מפל'ג, וכמה נשאר במחסן"""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, total_quantity FROM equipment_types "
            "WHERE layer = 'battalion' AND is_active = 1 ORDER BY name"
        )
        items = [dict(r) for r in cur.fetchall()]
        result = []
        for item in items:
            cur.execute(
                """SELECT h.name, ch.quantity FROM current_holdings ch
                   JOIN holders h ON h.id = ch.holder_id
                   WHERE ch.equipment_type_id = %s""",
                (item["id"],)
            )
            holdings = [dict(r) for r in cur.fetchall()]
            issued = sum(h["quantity"] for h in holdings)
            result.append({
                "name": item["name"], "total": item["total_quantity"],
                "held_by": holdings, "issued": issued,
                "available": item["total_quantity"] - issued,
            })
        return result
    finally:
        conn.close()


def get_platoons():
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM platoons ORDER BY id")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_soldiers_by_platoon(platoon_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, full_name FROM soldiers WHERE platoon_id = %s AND is_active = 1 ORDER BY full_name",
            (platoon_id,)
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_equipment_types(layer="personal"):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, unit FROM equipment_types WHERE layer = %s AND is_active = 1 ORDER BY name",
            (layer,)
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_warehouse_status(layer="personal"):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT et.id, et.name, et.total_quantity, COALESCE(SUM(ch.quantity), 0) AS issued
               FROM equipment_types et
               LEFT JOIN current_holdings ch ON ch.equipment_type_id = et.id
               WHERE et.layer = %s AND et.is_active = 1
               GROUP BY et.id ORDER BY et.name""",
            (layer,)
        )
        rows = [dict(r) for r in cur.fetchall()]
        result = []
        for r in rows:
            cur.execute(
                "SELECT COALESCE(SUM(quantity), 0) AS missing FROM shortages WHERE equipment_type_id = %s",
                (r["id"],)
            )
            missing = cur.fetchone()["missing"]
            total, issued = r["total_quantity"], r["issued"]
            result.append({
                "name": r["name"], "total": total, "issued": issued,
                "missing": missing, "available": total - issued - missing
            })
        return result
    finally:
        conn.close()


def get_full_report_matrix(layer="personal"):
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


def add_soldier(full_name, platoon_id, personal_number=None):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO soldiers (full_name, platoon_id, personal_number) VALUES (%s, %s, %s) RETURNING id",
            (full_name, platoon_id, personal_number)
        )
        new_id = cur.fetchone()["id"]
        conn.commit()
        return new_id
    finally:
        conn.close()


def get_soldier_name(soldier_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT full_name FROM soldiers WHERE id = %s", (soldier_id,))
        row = cur.fetchone()
        return row["full_name"] if row else None
    finally:
        conn.close()


def deactivate_soldier(soldier_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE soldiers SET is_active = 0 WHERE id = %s", (soldier_id,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()
