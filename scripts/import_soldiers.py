"""
ייבוא חיילים מקובץ אקסל לתוך המערכת
שימוש: python scripts/import_soldiers.py "נתיב לקובץ האקסל"

קורא מהגליון 'רשימת חיילים מלאה' (עמודות: מחלקה, שם פרטי, שם משפחה)
ומדלג אוטומטית על חייל שכבר קיים במחלקה שלו (מונע כפילויות אם מריצים פעמיים).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import openpyxl
from db.operations import get_conn, get_platoons

PLATOON_NAME_MAP = {
    "1": "מחלקה 1",
    "2": "מחלקה 2",
    "3": "מחלקה 3",
    "רתק": "רתק",
    "חפק": "חפק",
    "מפלג": "מפלג",
}


def import_from_excel(path: str, sheet_name: str = "רשימת חיילים מלאה"):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[sheet_name]

    # מיפוי שם מחלקה -> id
    platoons = {p["name"]: p["id"] for p in get_platoons()}

    conn = get_conn()
    added, skipped_duplicate, skipped_unknown_platoon, skipped_blank = 0, 0, 0, 0

    try:
        for row in ws.iter_rows(min_row=2, values_only=True):
            platoon_raw, first, last = row[0], row[1], row[2]

            if platoon_raw is None or first is None or last is None:
                skipped_blank += 1
                continue

            platoon_name = PLATOON_NAME_MAP.get(str(platoon_raw).strip())
            if platoon_name is None or platoon_name not in platoons:
                print(f"⚠️  מחלקה לא מזוהה: '{platoon_raw}' עבור {first} {last} - דולג")
                skipped_unknown_platoon += 1
                continue

            platoon_id = platoons[platoon_name]
            full_name = f"{str(first).strip()} {str(last).strip()}"

            # בדיקת כפילות - אותו שם מלא באותה מחלקה
            existing = conn.execute(
                "SELECT id FROM soldiers WHERE full_name = ? AND platoon_id = ? AND is_active = 1",
                (full_name, platoon_id)
            ).fetchone()
            if existing:
                skipped_duplicate += 1
                continue

            conn.execute(
                "INSERT INTO soldiers (full_name, platoon_id) VALUES (?, ?)",
                (full_name, platoon_id)
            )
            added += 1

        conn.commit()
    finally:
        conn.close()

    print()
    print(f"✅ נוספו: {added}")
    print(f"⏭️  דולגו (כפילות - כבר קיימים): {skipped_duplicate}")
    print(f"⚠️  דולגו (מחלקה לא מזוהה): {skipped_unknown_platoon}")
    print(f"⬜ דולגו (שורה ריקה): {skipped_blank}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("שימוש: python scripts/import_soldiers.py \"נתיב לקובץ האקסל\"")
        sys.exit(1)
    import_from_excel(sys.argv[1])
