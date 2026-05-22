"""
Отчёт по содержимому SQLite-БД project_calc.

Запуск:
    python scripts/check_db.py
    python scripts/check_db.py --db /path/to/database.db
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Добавляем корень репо в sys.path, чтобы можно было запускать из любой папки
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from project_calc.common.config import DB_PATH
from project_calc.common.db.connection import get_connection


def parse_args():
    p = argparse.ArgumentParser(description="Отчёт по project_calc БД")
    p.add_argument("--db", default=None, help=f"Путь к .db (по умолчанию: {DB_PATH})")
    return p.parse_args()


def line(c="-", n=60):
    print(c * n)


def main():
    args = parse_args()
    db_path = Path(args.db) if args.db else DB_PATH

    if not db_path.exists():
        print(f"БД не найдена: {db_path}")
        return 1

    conn = get_connection(db_path=db_path, read_only=True)

    print(f"БД: {db_path}")
    print(f"Размер файла: {db_path.stat().st_size / 1024:.1f} KB")

    # ===== Сводка =====
    line("=")
    print("СВОДКА")
    line("=")
    eq    = conn.execute("SELECT COUNT(*) FROM equipment").fetchone()[0]
    comp  = conn.execute("SELECT COUNT(*) FROM components").fetchone()[0]
    cost  = conn.execute("SELECT COUNT(*) FROM costs").fetchone()[0]
    areas = conn.execute("SELECT COUNT(DISTINCT area) FROM equipment").fetchone()[0]
    print(f"  Участков (area):         {areas}")
    print(f"  Единиц оборудования:     {eq}")
    print(f"  Записей состава:         {comp}")
    print(f"  Позиций в costs:         {cost}")

    if eq == 0:
        print("\n[БД пуста — запустите парсер]")
        conn.close()
        return 0

    # ===== Участки =====
    line()
    print("УЧАСТКИ ЛИНИИ")
    line()
    for row in conn.execute("""
        SELECT e.area, COUNT(DISTINCT e.id) AS eq_cnt, COUNT(c.id) AS comp_cnt
        FROM equipment e
        LEFT JOIN components c ON c.equipment_id = e.id
        GROUP BY e.area
        ORDER BY e.area
    """):
        print(f"  {row['area']:50s}  eq={row['eq_cnt']:3d}  comp={row['comp_cnt']:4d}")

    # ===== Оборудование =====
    line()
    print("ОБОРУДОВАНИЕ")
    line()
    for row in conn.execute("""
        SELECT e.area, e.equipment_name, COUNT(c.id) AS comp_cnt
        FROM equipment e
        LEFT JOIN components c ON c.equipment_id = e.id
        GROUP BY e.id
        ORDER BY e.area, e.equipment_name
    """):
        print(f"  {row['area']:30s} | {row['equipment_name']:30s}  ({row['comp_cnt']} компонентов)")

    # ===== Распределение по типам =====
    line()
    print("РАСПРЕДЕЛЕНИЕ ПО ТИПАМ КОМПОНЕНТОВ")
    line()
    for row in conn.execute("""
        SELECT component_type, COUNT(*) AS n
        FROM components
        GROUP BY component_type
        ORDER BY n DESC
    """):
        print(f"  {row['component_type']:15s}  {row['n']:5d}")

    # ===== Распределение по единицам =====
    line()
    print("РАСПРЕДЕЛЕНИЕ ПО ЕДИНИЦАМ ИЗМЕРЕНИЯ")
    line()
    for row in conn.execute("""
        SELECT unit, COUNT(*) AS n
        FROM components
        GROUP BY unit
        ORDER BY n DESC
    """):
        print(f"  {row['unit']:15s}  {row['n']:5d}")

    # ===== Топ-10 самых дорогих позиций =====
    line()
    print("ТОП-10 САМЫХ ДОРОГИХ ПОЗИЦИЙ В costs")
    line()
    for row in conn.execute("""
        SELECT component_name, unit, cost_with_vat
        FROM costs
        ORDER BY cost_with_vat DESC
        LIMIT 10
    """):
        print(f"  {row['cost_with_vat']:12.2f}  {row['component_name']} ({row['unit']})")

    # ===== Позиции состава без цены =====
    line()
    print("КОМПОНЕНТЫ БЕЗ ЦЕНЫ В costs")
    line()
    missing = list(conn.execute("""
        SELECT DISTINCT c.component_name, c.unit
        FROM components c
        LEFT JOIN costs cost ON cost.component_name = c.component_name
                            AND cost.unit          = c.unit
        WHERE cost.cost_with_vat IS NULL
        ORDER BY c.component_name
    """))
    if not missing:
        print("  (нет — все компоненты имеют цены)")
    else:
        print(f"  Всего: {len(missing)}")
        for row in missing[:20]:
            print(f"    {row['component_name']} ({row['unit']})")
        if len(missing) > 20:
            print(f"    ... и ещё {len(missing) - 20}")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
