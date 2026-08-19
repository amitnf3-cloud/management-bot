"""
בדיקת הרשאות משתמשים בבוט
full      - אתה + 2 אנשים -> יכולים לזכות/להחתים בכל השכבות (אישי + פלוגתי)
mefaleg   - אנשי מפל"ג -> גם שכבת הגדוד
view_only - כולם (כולל 6 הסמלים) -> צפייה בלבד
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from db.operations import get_conn

ACCESS_LEVELS = ("full", "mefaleg", "view_only")


def get_access_level(telegram_id: str) -> str | None:
    """מחזיר את רמת ההרשאה של המשתמש, או None אם הוא לא רשום בכלל"""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT access_level FROM bot_users WHERE telegram_id = ?", (str(telegram_id),)
        ).fetchone()
        return row["access_level"] if row else None
    finally:
        conn.close()


def can_edit(telegram_id: str) -> bool:
    """האם המשתמש יכול לבצע החתמה/זיכוי (אישי + פלוגתי)"""
    level = get_access_level(telegram_id)
    return level in ("full", "mefaleg")


def can_edit_battalion(telegram_id: str) -> bool:
    """האם המשתמש יכול לערוך את שכבת הגדוד (רק מפל"ג)"""
    return get_access_level(telegram_id) == "mefaleg"


def register_user(telegram_id: str, display_name: str, access_level: str):
    """רישום משתמש חדש להרשאות (אתה תריץ את זה ידנית עבור כל אחד מהמורשים)"""
    if access_level not in ACCESS_LEVELS:
        raise ValueError(f"access_level must be one of {ACCESS_LEVELS}")
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO bot_users (telegram_id, display_name, access_level)
               VALUES (?, ?, ?)
               ON CONFLICT(telegram_id) DO UPDATE SET
                   display_name = excluded.display_name,
                   access_level = excluded.access_level""",
            (str(telegram_id), display_name, access_level)
        )
        conn.commit()
    finally:
        conn.close()
