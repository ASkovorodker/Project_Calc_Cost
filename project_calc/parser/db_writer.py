"""
Запись результата парсинга в SQLite-БД.

API блочный: write_equipment(area, equipment_name, items) — один вызов на
одно оборудование. Парсер группирует строки Excel по (area, equipment_name)
перед вызовом writer.

Поведение:
  * equipment — INSERT OR IGNORE по UNIQUE(area, equipment_name).
  * components — вставляются ТОЛЬКО если equipment был создан в этом вызове.
    Если оборудование уже было в БД, состав не трогаем (правило "snapshot
    первого встреченного состава"). Состав не задублируется при повторных
    прогонах парсера.
  * costs — условный UPSERT по PK (component_name, unit): новая цена выше —
    перезаписываем, иначе игнор (max-strategy).

Транзакция: write_equipment атомарна — commit на успехе, rollback на ошибке.
"""
from __future__ import annotations

import sqlite3
from typing import Sequence


# SQL-запросы вынесены в константы — удобно искать и править.

_INSERT_EQUIPMENT = """
INSERT OR IGNORE INTO equipment (area, equipment_name) VALUES (?, ?)
"""

_SELECT_EQUIPMENT_ID = """
SELECT id FROM equipment WHERE area = ? AND equipment_name = ?
"""

_INSERT_COMPONENT = """
INSERT INTO components
    (equipment_id, component_name, qty_per_equipment, unit, component_type)
VALUES (?, ?, ?, ?, ?)
"""

_UPSERT_COST = """
INSERT INTO costs (component_name, unit, cost_with_vat, valid_from)
VALUES (?, ?, ?, CURRENT_DATE)
ON CONFLICT(component_name, unit) DO UPDATE SET
    cost_with_vat = excluded.cost_with_vat,
    valid_from    = CURRENT_DATE
WHERE excluded.cost_with_vat > costs.cost_with_vat
"""


class DBWriter:
    """
    Принимает открытое sqlite3.Connection (проще тестировать и контролировать
    жизненный цикл со стороны вызывающего кода).
    """

    def __init__(self, connection: sqlite3.Connection):
        self.conn = connection

    # =========================================================
    # PUBLIC API
    # =========================================================
    def write_equipment(
        self,
        area: str,
        equipment_name: str,
        items: Sequence[dict],
    ) -> dict:
        """
        Записать оборудование с его составом и ценами.

        items: список словарей с ключами
            component_name, qty_per_equipment, unit, component_type, cost_with_vat.

        Поведение:
          * equipment вставляется через INSERT OR IGNORE; если уже было — id
            всё равно достаётся через SELECT, флаг equipment_new=False.
          * components: вставляются ТОЛЬКО если equipment_new=True.
            Иначе состав в БД остаётся прежним (см. plan 7.1).
          * costs: для каждого item — условный UPSERT (max-strategy).

        Возвращает dict со статистикой: equipment_new, components_added,
        costs_upserted (число строк, реально вставленных или обновлённых).

        Транзакция: атомарна. На любой ошибке rollback и проброс наверх.
        """
        cur = self.conn.cursor()
        try:
            equipment_id, is_new = self._get_or_create_equipment(
                cur, area, equipment_name
            )

            components_added = 0
            if is_new and items:
                cur.executemany(
                    _INSERT_COMPONENT,
                    [
                        (
                            equipment_id,
                            item["component_name"],
                            item["qty_per_equipment"],
                            item["unit"],
                            item["component_type"],
                        )
                        for item in items
                    ],
                )
                components_added = len(items)

            costs_upserted = 0
            for item in items:
                cur.execute(
                    _UPSERT_COST,
                    (
                        item["component_name"],
                        item["unit"],
                        item["cost_with_vat"],
                    ),
                )
                # rowcount: 1 — INSERT прошёл или WHERE-условие сработало;
                #          0 — WHERE отсёк (новая цена не выше).
                if cur.rowcount > 0:
                    costs_upserted += 1

            self.conn.commit()

            return {
                "equipment_new": is_new,
                "components_added": components_added,
                "costs_upserted": costs_upserted,
            }

        except Exception:
            self.conn.rollback()
            raise

        finally:
            cur.close()

    # =========================================================
    # INTERNALS
    # =========================================================
    def _get_or_create_equipment(
        self,
        cur: sqlite3.Cursor,
        area: str,
        equipment_name: str,
    ) -> tuple[int, bool]:
        """
        Получить equipment.id, при необходимости создать.

        Возвращает (id, is_new). is_new=True означает, что строка
        вставлена в этом вызове и состав ещё надо записать.
        """
        cur.execute(_INSERT_EQUIPMENT, (area, equipment_name))
        # rowcount=1 если строку вставили; 0 если IGNORE проглотил конфликт.
        is_new = cur.rowcount == 1

        cur.execute(_SELECT_EQUIPMENT_ID, (area, equipment_name))
        row = cur.fetchone()
        if row is None:
            # Не должно случиться, но защищаемся.
            raise RuntimeError(
                f"Не удалось получить id для equipment "
                f"({area!r}, {equipment_name!r})"
            )

        # row может быть либо tuple, либо sqlite3.Row — оба индексируются по 0.
        return row[0], is_new
