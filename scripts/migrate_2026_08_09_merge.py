"""
מיגרציה חד-פעמית #3: מאחדת וסט נגב + וסט מאג -> פריט אחד 'וסט נגב/מאג',
ותוף נגב + תוף מאג -> פריט אחד 'תוף נגב/מאג' (זה אותו ציוד בפועל, לא צריך הפרדה).

מה זה עושה בפועל, לכל זוג:
1. יוצר פריט חדש מאוחד עם המלאי הנכון (9 / 55)
2. אם יש חיילים שכבר חתומים על אחד הפריטים הישנים - מעביר את ההחתמה לפריט המאוחד (לא מאבד נתונים)
3. מעביר גם את ההיסטוריה (transactions) לפריט המאוחד
4. מכבה (is_active=0) את שני הפריטים הישנים - הם לא יופיעו יותר ברשימות, אבל נשארים בטבלה לצורך היסטוריה

בטוח להריץ כמה פעמים - אם המיזוג כבר בוצע, הסקריפט מזהה את זה ולא עושה כלום.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.operations import get_conn

MERGES = [
    {"new_name": "וסט מאג/נגב", "old_names": ["וסט נגב", "וסט מאג"], "total_quantity": 9},
    {"new_name": "תוף", "old_names": ["תוף נגב", "תוף מאג"], "total_quantity": 55},
]


def merge_pair(conn, new_name, old_names, total_quantity):
    # אם הפריט המאוחד כבר קיים - כנראה שהמיזוג הזה כבר בוצע
    existing_new = conn.execute(
        "SELECT id FROM equipment_types WHERE name = ?", (new_name,)
    ).fetchone()
    if existing_new:
        print(f"⏭️  '{new_name}' כבר קיים - המיזוג הזה כבר בוצע, דולג")
        return

    old_ids = []
    for old_name in old_names:
        row = conn.execute(
            "SELECT id FROM equipment_types WHERE name = ?", (old_name,)
        ).fetchone()
        if row:
            old_ids.append(row["id"])
        else:
            print(f"⚠️  '{old_name}' לא נמצא - ממשיך בלעדיו")

    if not old_ids:
        print(f"⚠️  אף אחד מ-{old_names} לא נמצא, יוצר את '{new_name}' ריק עם מלאי {total_quantity}")

    # יצירת הפריט המאוחד
    cur = conn.execute(
        "INSERT INTO equipment_types (name, layer, total_quantity) VALUES (?, 'personal', ?)",
        (new_name, total_quantity)
    )
    new_id = cur.lastrowid
    print(f"✅ נוצר פריט מאוחד: {new_name} (מלאי {total_quantity})")

    # העברת החתמות קיימות (current_holdings) מהפריטים הישנים לחדש
    for old_id in old_ids:
        holdings = conn.execute(
            "SELECT id, soldier_id, holder_id, quantity FROM current_holdings WHERE equipment_type_id = ?",
            (old_id,)
        ).fetchall()
        for h in holdings:
            # בודקים אם כבר יש רשומה לאותו חייל/מחזיק על הפריט החדש (למשל אם היה חתום על שניהם)
            key_col, key_val = ("soldier_id", h["soldier_id"]) if h["soldier_id"] else ("holder_id", h["holder_id"])
            existing = conn.execute(
                f"SELECT id, quantity FROM current_holdings WHERE {key_col} = ? AND equipment_type_id = ?",
                (key_val, new_id)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE current_holdings SET quantity = quantity + ? WHERE id = ?",
                    (h["quantity"], existing["id"])
                )
                conn.execute("DELETE FROM current_holdings WHERE id = ?", (h["id"],))
            else:
                conn.execute(
                    "UPDATE current_holdings SET equipment_type_id = ? WHERE id = ?",
                    (new_id, h["id"])
                )
            print(f"   ↳ הועברה החתמה קיימת ({key_col}={key_val}) לפריט המאוחד")

        # העברת היסטוריה
        conn.execute(
            "UPDATE transactions SET equipment_type_id = ? WHERE equipment_type_id = ?",
            (new_id, old_id)
        )

        # כיבוי הפריט הישן - נשאר בטבלה (להיסטוריה) אבל לא מופיע ברשימות
        conn.execute("UPDATE equipment_types SET is_active = 0 WHERE id = ?", (old_id,))
        print(f"   ↳ '{old_names}' כובה (is_active=0)")


def migrate():
    conn = get_conn()
    try:
        for merge in MERGES:
            merge_pair(conn, merge["new_name"], merge["old_names"], merge["total_quantity"])
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
    print("\nהמיזוג הושלם.")
