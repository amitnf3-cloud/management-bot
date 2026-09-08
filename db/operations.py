"""
שכבת גישה למסד הנתונים - גרסת PostgreSQL (RDS)
זהה בממשק ל-SQLite המקורי, כדי שהבוט (bot/main.py, bot/access.py) לא יצטרך להשתנות בכלל
"""
import os
import psycopg2
import psycopg2.extras


def get_conn():
    # קוראים את משתני הסביבה כאן (לא בזמן ייבוא המודול) - כדי שזה יעבוד
    # גם אם load_dotenv() נקרא אחרי ש-db.operations כבר יובא
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
    """החתמה - נותן ציוד לחייל"""
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
    """זיכוי - מחזיר ציוד מחייל"""
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


def get_soldier_status(soldier_id):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT et.name, ch.quantity
               FROM current_holdings ch
               JOIN equipment_types et ON et.id = ch.equipment_type_id
               WHERE ch.soldier_id = %s
               ORDER BY et.name""",
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
            """SELECT et.id, et.name, ch.quantity
               FROM current_holdings ch
               JOIN equipment_types et ON et.id = ch.equipment_type_id
               WHERE ch.soldier_id = %s
               ORDER BY et.name""",
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
        cur.execute(
            "SELECT id FROM equipment_types WHERE name = %s AND is_active = 1", (name,)
        )
        row = cur.fetchone()
        return row["id"] if row else None
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
            """SELECT et.name, et.total_quantity, COALESCE(SUM(ch.quantity), 0) AS issued
               FROM equipment_types et
               LEFT JOIN current_holdings ch ON ch.equipment_type_id = et.id
               WHERE et.layer = %s AND et.is_active = 1
               GROUP BY et.id
               ORDER BY et.name""",
            (layer,)
        )
        result = []
        for r in cur.fetchall():
            total, issued = r["total_quantity"], r["issued"]
            result.append({"name": r["name"], "total": total, "issued": issued, "available": total - issued})
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
    """שם החייל לפי ID - משמש למסך אישור לפני הסרה"""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT full_name FROM soldiers WHERE id = %s", (soldier_id,))
        row = cur.fetchone()
        return row["full_name"] if row else None
    finally:
        conn.close()


def deactivate_soldier(soldier_id):
    """הסרת חייל - 'מכבה' אותו (is_active=0) בלי למחוק בפועל, כדי לשמר היסטוריה"""
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE soldiers SET is_active = 0 WHERE id = %s", (soldier_id,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()
