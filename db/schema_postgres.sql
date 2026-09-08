-- ============================================
-- מערכת ניהול חתימות ציוד - צנחנים
-- Schema PostgreSQL (RDS) - מותאם מ-SQLite
-- ============================================

-- ------------------------------------------------
-- מחלקות
-- ------------------------------------------------
CREATE TABLE platoons (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE
);

INSERT INTO platoons (name) VALUES
    ('מחלקה 1'), ('מחלקה 2'), ('מחלקה 3'), ('רתק'), ('חפק'), ('מפלג');

-- ------------------------------------------------
-- חיילים
-- ------------------------------------------------
CREATE TABLE soldiers (
    id              SERIAL PRIMARY KEY,
    full_name       TEXT NOT NULL,
    personal_number TEXT UNIQUE,
    platoon_id      INTEGER NOT NULL REFERENCES platoons(id),
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------
-- סוגי ציוד
-- ------------------------------------------------
CREATE TABLE equipment_types (
    id              SERIAL PRIMARY KEY,
    name            TEXT NOT NULL,
    layer           TEXT NOT NULL CHECK (layer IN ('personal', 'company', 'battalion')),
    unit            TEXT NOT NULL DEFAULT 'יחידה',
    total_quantity  INTEGER NOT NULL DEFAULT 0,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

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

INSERT INTO equipment_types (name, layer) VALUES
    ('ערכת פריצה', 'company'), ('מזמרה', 'company'), ('הילטי', 'company');

INSERT INTO equipment_types (name, layer, total_quantity) VALUES
    ('גריקן מים', 'battalion', 1),
    ('גריקן סולר', 'battalion', 1),
    ('אלונקות', 'battalion', 8),
    ('ערכת פריצה קרה', 'battalion', 3),
    ('ערכת פריצה הידרו', 'battalion', 1),
    ('ערכת ניצן', 'battalion', 1);

-- ------------------------------------------------
-- מחזיקים (לשכבה הפלוגתית/גדודית)
-- ------------------------------------------------
CREATE TABLE holders (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    holder_type TEXT NOT NULL CHECK (holder_type IN ('soldier', 'platoon_sergeant', 'battalion')),
    platoon_id  INTEGER REFERENCES platoons(id)
);

-- ------------------------------------------------
-- מצב נוכחי - מי מחזיק מה
-- ------------------------------------------------
CREATE TABLE current_holdings (
    id                  SERIAL PRIMARY KEY,
    soldier_id          INTEGER REFERENCES soldiers(id),
    holder_id           INTEGER REFERENCES holders(id),
    equipment_type_id   INTEGER NOT NULL REFERENCES equipment_types(id),
    quantity            INTEGER NOT NULL DEFAULT 1,
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW(),
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
-- היסטוריה
-- ------------------------------------------------
CREATE TABLE transactions (
    id                  SERIAL PRIMARY KEY,
    action              TEXT NOT NULL CHECK (action IN ('issue', 'return')),
    soldier_id          INTEGER REFERENCES soldiers(id),
    holder_id           INTEGER REFERENCES holders(id),
    equipment_type_id   INTEGER NOT NULL REFERENCES equipment_types(id),
    quantity            INTEGER NOT NULL DEFAULT 1,
    performed_by_tg_id  TEXT,
    performed_by_name   TEXT,
    notes               TEXT,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------
-- הרשאות טלגרם
-- ------------------------------------------------
CREATE TABLE bot_users (
    id              SERIAL PRIMARY KEY,
    telegram_id     TEXT NOT NULL UNIQUE,
    display_name    TEXT,
    access_level    TEXT NOT NULL CHECK (access_level IN ('full', 'mefaleg', 'view_only')),
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
