"""
מנקה כל מה שיצרת בבדיקות - מוחק פריטי ציוד ואנשי-מפל'ג שהשם שלהם מתחיל ב'בדיקה'.
תריץ ידנית אחרי שבדקת את הבוט, לפני שממשיכים לשימוש אמיתי.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from db.operations import get_conn

conn = get_conn()
try:
    cur = conn.cursor()

    # מוצאים אילו equipment_types וholders נוצרו בבדיקה
    cur.execute("SELECT id, name FROM equipment_types WHERE name LIKE 'בדיקה%'")
    test_items = cur.fetchall()
    cur.execute("SELECT id, name FROM holders WHERE name LIKE 'בדיקה%'")
    test_holders = cur.fetchall()

    print("פריטי ציוד שיימחקו:", [i["name"] for i in test_items])
    print("אנשים שיימחקו:", [h["name"] for h in test_holders])

    for item in test_items:
        cur.execute("DELETE FROM transactions WHERE equipment_type_id = %s", (item["id"],))
        cur.execute("DELETE FROM current_holdings WHERE equipment_type_id = %s", (item["id"],))
        cur.execute("DELETE FROM shortages WHERE equipment_type_id = %s", (item["id"],))
        cur.execute("DELETE FROM equipment_types WHERE id = %s", (item["id"],))

    for h in test_holders:
        cur.execute("DELETE FROM current_holdings WHERE holder_id = %s", (h["id"],))
        cur.execute("DELETE FROM transactions WHERE holder_id = %s", (h["id"],))
        cur.execute("DELETE FROM holders WHERE id = %s", (h["id"],))

    conn.commit()
    print("נוקה בהצלחה.")
finally:
    conn.close()
