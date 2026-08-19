-- ============================================
-- מערכת ניהול חתימות ציוד - צנחנים
-- Schema v0.1
-- ============================================

PRAGMA foreign_keys = ON;

-- ------------------------------------------------
-- מחלקות (הפלוגה מחולקת ל-6 מחלקות/גופים)
-- ------------------------------------------------
CREATE TABLE platoons (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE     -- מחלקה 1 / מחלקה 2 / מחלקה 3 / רת"ק / חפ"ק / מפל"ג
);

INSERT INTO platoons (name) VALUES
    ('מחלקה 1'),
    ('מחלקה 2'),
    ('מחלקה 3'),
    ('רתק'),
    ('חפק'),
    ('מפלג');

-- ------------------------------------------------
-- חיילים
-- ------------------------------------------------
CREATE TABLE soldiers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name       TEXT NOT NULL,
    personal_number TEXT UNIQUE,             -- מספר אישי, לא חובה למלא בהתחלה
    platoon_id      INTEGER NOT NULL REFERENCES platoons(id),
    is_active       INTEGER NOT NULL DEFAULT 1,  -- 0 = השתחרר/עבר הצידה, לא נמחק כדי לשמור היסטוריה
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ------------------------------------------------
-- סוגי ציוד - גנרי לכל 3 השכבות (אישי / פלוגתי / גדודי)
-- כך שהוספת פריט חדש = שורה חדשה, לא שינוי קוד
-- ------------------------------------------------
CREATE TABLE equipment_types (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    layer           TEXT NOT NULL CHECK (layer IN ('personal', 'company', 'battalion')),
    unit            TEXT NOT NULL DEFAULT 'יחידה',  -- למשל 'מחסנית', 'יחידה' וכו
    total_quantity  INTEGER NOT NULL DEFAULT 0,  -- כמה יש בסך הכל (מחסן + מוחתם) - לחישוב 'כמה נשאר במחסן'
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ציוד אישי - עם מלאי כולל (מחסן), נכון לתאריך הספירה האחרונה
-- 0 = טרם נספר/עודכן, אפשר לעדכן בהמשך
INSERT INTO equipment_types (name, layer, total_quantity) VALUES
    ('תיק לאו', 'personal', 0),
    ('וסט לוחם', 'personal', 71),
    ('קסדה', 'personal', 70),
    ('מחסניות', 'personal', 379),
    ('בירכיות', 'personal', 162),
    ('שקש', 'personal', 0),
    ('חולצה', 'personal', 50),
    ('מכנס', 'personal', 50),
    ('משקפי מגן', 'personal', 59),
    ('וסט מאג/נגב', 'personal', 9),
    ('ח"ע', 'personal', 51),
    ('תא - ציוד רפואי אישי', 'personal', 43),
    ('שלוקר', 'personal', 71),
    ('חרמונית', 'personal', 0),
    ('תוף', 'personal', 55),
    ('פאוץ גב', 'personal', 67),
    ('חלפ"ס', 'personal', 0),
    ('רשת הסוואה', 'personal', 20),
    ('מצנפת', 'personal', 23),
    ('את חפירה', 'personal', 10),
    ('רצועת נשק', 'personal', 44),
    ('רשת ענבר', 'personal', 4),
    ('דגל אדום', 'personal', 4);

-- ציוד גדודי - מה שהפלוגה חתומה עליו מול הגדוד
INSERT INTO equipment_types (name, layer, total_quantity) VALUES
    ('גריקן מים', 'battalion', 1),
    ('גריקן סולר', 'battalion', 1),
    ('אלונקות', 'battalion', 8),
    ('ערכת פריצה קרה', 'battalion', 3),
    ('ערכת פריצה הידרו', 'battalion', 1),
    ('ערכת ניצן', 'battalion', 1);

-- ציוד פלוגתי - גרסה ראשונית (רשימה חלקית, נמשיך להוסיף)
INSERT INTO equipment_types (name, layer) VALUES
    ('ערכת פריצה', 'company'),
    ('מזמרה', 'company'),
    ('הילטי', 'company');

-- ------------------------------------------------
-- "מחזיקים אפשריים" בשכבה הפלוגתית/גדודית
-- ציוד פלוגתי מוחתם לרוב על סמל/מחלקה, לא על חייל בודד
-- ולכן אנחנו צריכים ישות "מחזיק" גנרית
-- ------------------------------------------------
CREATE TABLE holders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,             -- שם חופשי: "סמל מחלקה 2", "מפלג", "גדוד 202" וכו
    holder_type TEXT NOT NULL CHECK (holder_type IN ('soldier', 'platoon_sergeant', 'battalion')),
    platoon_id  INTEGER REFERENCES platoons(id)  -- רלוונטי אם זה סמל מחלקה
);

-- ------------------------------------------------
-- טבלת המצב הנוכחי - "מי מחזיק מה עכשיו"
-- זו הטבלה שרוב השאילתות (דוח חוסרים, מצב מחלקה) ירוצו עליה
-- מהירה כי היא קטנה - שורה אחת לכל צירוף (מחזיק, סוג ציוד)
-- ------------------------------------------------
CREATE TABLE current_holdings (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    soldier_id          INTEGER REFERENCES soldiers(id),      -- לשכבה האישית
    holder_id           INTEGER REFERENCES holders(id),        -- לשכבה הפלוגתית/גדודית
    equipment_type_id    INTEGER NOT NULL REFERENCES equipment_types(id),
    quantity            INTEGER NOT NULL DEFAULT 1,
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (
        (soldier_id IS NOT NULL AND holder_id IS NULL) OR
        (soldier_id IS NULL AND holder_id IS NOT NULL)
    )
);

CREATE UNIQUE INDEX idx_holding_soldier ON current_holdings(soldier_id, equipment_type_id)
    WHERE soldier_id IS NOT NULL;
CREATE UNIQUE INDEX idx_holding_holder ON current_holdings(holder_id, equipment_type_id)
    WHERE holder_id IS NOT NULL;

-- ------------------------------------------------
-- לוג היסטורי - כל פעולה (החתמה/זיכוי) נשמרת כאן לצמיתות
-- לא משפיע על מהירות השאילתות היומיומיות כי אלה רצות על current_holdings
-- ------------------------------------------------
CREATE TABLE transactions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    action              TEXT NOT NULL CHECK (action IN ('issue', 'return')),  -- issue=החתמה, return=זיכוי
    soldier_id          INTEGER REFERENCES soldiers(id),
    holder_id           INTEGER REFERENCES holders(id),
    equipment_type_id    INTEGER NOT NULL REFERENCES equipment_types(id),
    quantity            INTEGER NOT NULL DEFAULT 1,
    performed_by_tg_id  TEXT,             -- Telegram user id של מי שביצע
    performed_by_name   TEXT,
    notes               TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ------------------------------------------------
-- הרשאות טלגרם
-- full_access = אתה + 2 אנשים -> יכולים לזכות/להחתים בכל השכבות
-- mefaleg_access = אנשי מפל"ג -> גם שכבת הגדוד
-- view_only = כולם (כולל 6 הסמלים) -> צפייה בלבד, לא מוגבל למחלקה שלהם
-- ------------------------------------------------
CREATE TABLE bot_users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id     TEXT NOT NULL UNIQUE,
    display_name    TEXT,
    access_level    TEXT NOT NULL CHECK (access_level IN ('full', 'mefaleg', 'view_only')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
