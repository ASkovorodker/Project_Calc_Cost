"""
Создать пустую SQLite-БД по схеме project_calc/common/db/schema/init_sqlite.sql.

Запуск:
    python scripts/init_db.py

Если БД уже существует — печатает предупреждение и завершается с rc=1,
не перезаписывая (чтобы случайно не потерять данные). Чтобы пересоздать —
удалите файл и запустите снова.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from project_calc.common.config import DB_PATH
from project_calc.common.db.connection import get_connection

SCHEMA_PATH = (
    ROOT / "project_calc" / "common" / "db" / "schema" / "init_sqlite.sql"
)


def main() -> int:
    if DB_PATH.exists():
        print(f"WARNING: БД уже существует: {DB_PATH}")
        print("Чтобы пересоздать — удалите файл и запустите снова.")
        return 1

    if not SCHEMA_PATH.exists():
        print(f"FAIL: не найдена схема: {SCHEMA_PATH}", file=sys.stderr)
        return 1

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = get_connection()
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()

    print(f"OK: БД создана: {DB_PATH}")
    print(f"Размер: {DB_PATH.stat().st_size} байт")
    return 0


if __name__ == "__main__":
    sys.exit(main())
