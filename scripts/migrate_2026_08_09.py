"""
מיגרציה חד-פעמית #2: מריצים אחרי עדכון הסכימה, בלי למחוק מידע קיים (95 החיילים נשארים בדיוק כמו שהם).
- מוסיפה עמודת total_quantity (מלאי כולל) לטבלת equipment_types
- משנה שם 'פלייט/וסט בסיסי' -> 'וסט לוחם' (ההנחה: זה אותו פריט, שם עדכני יותר)
- מעדכנת כמויות מלאי לפריטים קיימים
- מוסיפה פריטי ציוד אישי חדשים (פאוץ גב, חלפ"ס, רשת הסוואה, מצנפת, את חפירה, רצועת נשק, רשת ענבר, דגל אדום)
- מוסיפה ציוד גדודי (גריקנים, אלונקות, ערכות פריצה, ערכת ניצן)
בטוח להריץ כמה פעמים - לא יוצר כפילויות ולא דורס נתונים קיימים.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.operations import get_conn

# עדכוני כמות לפריטים קיימים (name -> total_quantity)
QUANTITY_UPDATES = {
    "וסט לוחם": 71,
    "קסדה": 70,
    "מחסניות": 379,
    "בירכיות": 162,
    "שלוקר": 71,
    "משקפי מגן": 59,
    "ח\"ע": 51,
    "תא - ציוד רפואי אישי": 43,
    "מכנס": 50,
    "חולצה": 50,
}

# פריטים אישיים חדשים (name, total_quantity)
NEW_PERSONAL_ITEMS = [
    ("פאוץ גב", 67),
    ("חלפ\"ס", 0),  # כמות לא סופקה - עדכן ידנית כשתדע
    ("רשת הסוואה", 20),
    ("מצנפת", 23),
    ("את חפירה", 10),
    ("רצועת נשק", 44),
    ("רשת ענבר", 4),
    ("דגל אדום", 4),
]

# ציוד גדודי חדש - מה שהפלוגה חתומה עליו מול הגדוד (name, total_quantity)
NEW_BATTALION_ITEMS = [
    ("גריקן מים", 1),
    ("גריקן סולר", 1),
    ("אלונקות", 8),
    ("ערכת פריצה קרה", 3),
    ("ערכת פריצה הידרו", 1),
    ("ערכת ניצן", 1),
]


def column_exists(conn, table, column):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == column for r in rows)


def migrate():
    conn = get_conn()
    try:
        # 1. הוספת עמודת total_quantity אם עוד לא קיימת
        if not column_exists(conn, "equipment_types", "total_quantity"):
            conn.execute("ALTER TABLE equipment_types ADD COLUMN total_quantity INTEGER NOT NULL DEFAULT 0")
            print("✅ נוספה עמודת total_quantity")
        else:
            print("⏭️  עמודת total_quantity כבר קיימת")

        # 2. שינוי שם פלייט/וסט בסיסי -> וסט לוחם
        old_vest = conn.execute(
            "SELECT id FROM equipment_types WHERE name = 'פלייט/וסט בסיסי'"
        ).fetchone()
        if old_vest:
            conn.execute("UPDATE equipment_types SET name = 'וסט לוחם' WHERE id = ?", (old_vest["id"],))
            print("✅ שונה שם: פלייט/וסט בסיסי -> וסט לוחם")
        else:
            print("⏭️  'פלייט/וסט בסיסי' לא נמצא (כנראה כבר עודכן, או שם שונה)")

        # 3. עדכון כמויות מלאי לפריטים קיימים
        for name, qty in QUANTITY_UPDATES.items():
            row = conn.execute("SELECT id FROM equipment_types WHERE name = ?", (name,)).fetchone()
            if row:
                conn.execute("UPDATE equipment_types SET total_quantity = ? WHERE id = ?", (qty, row["id"]))
                print(f"✅ עודכן מלאי: {name} = {qty}")
            else:
                print(f"⚠️  '{name}' לא נמצא במערכת - לא עודכן (בדוק שם ידנית)")

        # 4. הוספת פריטים אישיים חדשים
        for name, qty in NEW_PERSONAL_ITEMS:
            exists = conn.execute("SELECT id FROM equipment_types WHERE name = ?", (name,)).fetchone()
            if exists:
                print(f"⏭️  '{name}' כבר קיים - דולג")
                continue
            conn.execute(
                "INSERT INTO equipment_types (name, layer, total_quantity) VALUES (?, 'personal', ?)",
                (name, qty)
            )
            print(f"✅ נוסף (אישי): {name} - מלאי {qty}")

        # 5. הוספת ציוד גדודי חדש
        for name, qty in NEW_BATTALION_ITEMS:
            exists = conn.execute("SELECT id FROM equipment_types WHERE name = ?", (name,)).fetchone()
            if exists:
                print(f"⏭️  '{name}' כבר קיים - דולג")
                continue
            conn.execute(
                "INSERT INTO equipment_types (name, layer, total_quantity) VALUES (?, 'battalion', ?)",
                (name, qty)
            )
            print(f"✅ נוסף (גדודי): {name} - מלאי {qty}")

        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
    print("\nהמיגרציה הושלמה. שים לב: כמות 'וסט נגב', 'וסט מאג', 'תוף נגב', 'תוף מאג' נשארה 0")
    print("(כי לא ידוע הפילוח המדויק ביניהם) - נעדכן כשתאשר את החלוקה.")
