-- ============================================================
-- SQLite schema for project_calc
-- Источник: BD Scripts/Create_structure_DB.sql (PostgreSQL)
--
-- Адаптации под SQLite:
--   * SERIAL PRIMARY KEY        → INTEGER PRIMARY KEY AUTOINCREMENT
--   * DATE DEFAULT CURRENT_DATE → TEXT DEFAULT CURRENT_DATE
--   * CREATE TABLE IF NOT EXISTS / INSERT OR IGNORE — идемпотентность
--   * Явный индекс на components(equipment_id) — FK index не создаётся
--     автоматически
--
-- ВАЖНО: PRAGMA foreign_keys = ON выставляется на каждом подключении
-- (см. project_calc/common/db/connection.py). PRAGMA в этом файле
-- задана для случая ручного применения схемы через sqlite3 CLI.
-- ============================================================

PRAGMA foreign_keys = ON;

-- ============================================================
-- 1. Справочник типов комплектующих
-- ============================================================
CREATE TABLE IF NOT EXISTS component_types (
    type_code   TEXT PRIMARY KEY,
    description TEXT
);

INSERT OR IGNORE INTO component_types (type_code, description) VALUES
    ('комп',   'Комплектующее изделие'),
    ('м/к',    'Металлоконструкция'),
    ('услуга', 'Инженерные услуги'),
    ('товар',  'Дорогое оборудование');

-- ============================================================
-- 2. Справочник единиц измерения
-- ============================================================
CREATE TABLE IF NOT EXISTS units (
    unit_code   TEXT PRIMARY KEY,
    description TEXT
);

INSERT OR IGNORE INTO units (unit_code, description) VALUES
    ('шт',   'Штука'),
    ('кг',   'Килограмм'),
    ('м',    'Метр'),
    ('смен', 'Смена');

-- ============================================================
-- 3. Единицы оборудования
-- ============================================================
CREATE TABLE IF NOT EXISTS equipment (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    area            TEXT NOT NULL,
    equipment_name  TEXT NOT NULL,
    UNIQUE (area, equipment_name)
);

-- ============================================================
-- 4. Состав оборудования
-- ============================================================
CREATE TABLE IF NOT EXISTS components (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment_id       INTEGER NOT NULL
        REFERENCES equipment(id)
        ON DELETE CASCADE,
    component_name     TEXT NOT NULL,
    unit               TEXT NOT NULL
        REFERENCES units(unit_code),
    qty_per_equipment  NUMERIC NOT NULL CHECK (qty_per_equipment > 0),
    component_type     TEXT NOT NULL
        REFERENCES component_types(type_code)
);

-- Индекс для быстрого получения состава оборудования по equipment_id
CREATE INDEX IF NOT EXISTS idx_components_equipment_id
    ON components(equipment_id);

-- ============================================================
-- 5. Себестоимость
-- ============================================================
CREATE TABLE IF NOT EXISTS costs (
    component_name  TEXT NOT NULL,
    unit            TEXT NOT NULL
        REFERENCES units(unit_code),
    cost_with_vat   NUMERIC NOT NULL CHECK (cost_with_vat >= 0),
    valid_from      TEXT DEFAULT CURRENT_DATE,
    PRIMARY KEY (component_name, unit)
);
