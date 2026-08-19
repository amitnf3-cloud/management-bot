"""
מיגרציה חד-פעמית: מריצים אחרי עדכון הסכימה, בלי למחוק מידע קיים.
- משנה שם 'חעת - ציוד רפואי אישי' ל-'ח"ע'
- מוסיף פריטים חדשים: תוף מאג, תוף נגב, וסט מאג (אם עוד לא קיימים)
בטוח להריץ כמה פעמים - לא יוצר כפילויות.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db.operations import get_conn

NEW_ITEMS = ["תוף מאג", "תוף נגב", "וסט מאג"]


def migrate():
    conn = get_conn()
    try:
        # שינוי שם חעת -> ח"ע (רק אם עדיין לא בוצע)
        old = conn.execute(
            "SELECT id FROM equipment_types WHERE name LIKE 'חעת%'"
        ).fetchone()
        if old:
            conn.execute("UPDATE equipment_types SET name = 'ח\"ע' WHERE id = ?", (old["id"],))
            print("✅ שונה שם: חעת -> ח\"ע")
        else:
            print("⏭️  שם 'חעת' לא נמצא (כנראה כבר עודכן קודם)")

        # הוספת פריטים חדשים - רק אם לא קיימים כבר
        for name in NEW_ITEMS:
            exists = conn.execute(
                "SELECT id FROM equipment_types WHERE name = ?", (name,)
            ).fetchone()
            if exists:
                print(f"⏭️  '{name}' כבר קיים - דולג")
                continue
            conn.execute(
                "INSERT INTO equipment_types (name, layer) VALUES (?, 'personal')", (name,)
            )
            print(f"✅ נוסף: {name}")

        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
    print("\nהמיגרציה הושלמה.")
