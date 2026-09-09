"""
מיגרציה: מוסיפה טבלת shortages (חוסרים), מעדכנת CHECK על transactions כדי לתמוך ב-'missing',
מעדכנת מלאי תיק לאו ל-69, ויוצרת רשומות 'סמל' לכל מחלקה (לצורך החתמת ציוד פלוגתי).
בטוח להריץ כמה פעמים.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from db.operations import get_conn


def migrate():
    conn = get_conn()
    try:
        cur = conn.cursor()

        # 1. טבלת חוסרים
        cur.execute("""
            CREATE TABLE IF NOT EXISTS shortages (
                id                  SERIAL PRIMARY KEY,
                soldier_id          INTEGER NOT NULL REFERENCES soldiers(id),
                equipment_type_id   INTEGER NOT NULL REFERENCES equipment_types(id),
                quantity            INTEGER NOT NULL DEFAULT 1,
                reported_by_tg_id   TEXT,
                reported_by_name    TEXT,
                notes               TEXT,
                created_at          TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """)
        print("✅ טבלת shortages קיימת")

        # 2. עדכון CHECK על transactions כדי לתמוך גם ב-'missing'
        try:
            cur.execute("ALTER TABLE transactions DROP CONSTRAINT transactions_action_check")
        except Exception:
            conn.rollback()
        cur.execute("ALTER TABLE transactions ADD CONSTRAINT transactions_action_check "
                    "CHECK (action IN ('issue', 'return', 'missing'))")
        print("✅ transactions תומך גם ב-action='missing'")

        # 3. עדכון מלאי תיק לאו
        cur.execute("UPDATE equipment_types SET total_quantity = 69 WHERE name = 'תיק לאו'")
        print(f"✅ תיק לאו עודכן ל-69 (שורות שהושפעו: {cur.rowcount})")

        # 4. יצירת 'סמל' לכל מחלקה - מחזיקי ציוד פלוגתי
        cur.execute("SELECT id, name FROM platoons ORDER BY id")
        for p in cur.fetchall():
            holder_name = f"סמל {p['name']}"
            cur.execute(
                "SELECT id FROM holders WHERE name = %s AND platoon_id = %s",
                (holder_name, p["id"])
            )
            if cur.fetchone():
                continue
            cur.execute(
                "INSERT INTO holders (name, holder_type, platoon_id) VALUES (%s, 'platoon_sergeant', %s)",
                (holder_name, p["id"])
            )
            print(f"✅ נוצר מחזיק: {holder_name}")

        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
    print("\nהמיגרציה הושלמה.")
