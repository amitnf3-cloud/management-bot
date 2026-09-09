import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))
from db.operations import get_conn

ACCESS_LEVELS = ("full", "mefaleg", "view_only")


def get_access_level(telegram_id: str) -> Optional[str]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT access_level FROM bot_users WHERE telegram_id = %s", (str(telegram_id),))
        row = cur.fetchone()
        return row["access_level"] if row else None
    finally:
        conn.close()


def can_edit(telegram_id: str) -> bool:
    return get_access_level(telegram_id) in ("full", "mefaleg")


def can_edit_battalion(telegram_id: str) -> bool:
    return get_access_level(telegram_id) == "mefaleg"


def register_user(telegram_id: str, display_name: str, access_level: str):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO bot_users (telegram_id, display_name, access_level) VALUES (%s, %s, %s)
               ON CONFLICT(telegram_id) DO UPDATE SET display_name = excluded.display_name,
               access_level = excluded.access_level""",
            (str(telegram_id), display_name, access_level)
        )
        conn.commit()
    finally:
        conn.close()
