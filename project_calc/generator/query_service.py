"""
Запросы к SQLite-БД для генератора.

Подключение в режиме read_only=True — генератор только читает БД.
"""
from project_calc.common.db.connection import get_connection


class QueryService:

    def __init__(self):
        self.conn = get_connection(read_only=True)
        self.cursor = self.conn.cursor()

    # ---------------------------------------
    # Поиск по area + equipment_name
    # ---------------------------------------
    def get_components_for_equipment(
        self,
        line_section: str,
        equipment: str,
        equipment_quantity: int,
    ):
        query = """
            SELECT
                e.area,
                e.equipment_name,
                ? as equipment_quantity,
                c.component_name,
                c.qty_per_equipment * ? as component_quantity,
                c.unit,
                cost.cost_with_vat,
                c.component_type
            FROM equipment e
            JOIN components c ON c.equipment_id = e.id
            LEFT JOIN costs cost ON cost.component_name = c.component_name
                                AND cost.unit = c.unit
            WHERE e.area = ?
              AND e.equipment_name = ?
        """

        self.cursor.execute(
            query,
            (
                equipment_quantity,
                equipment_quantity,
                line_section,
                equipment,
            ),
        )

        rows = self.cursor.fetchall()

        if not rows:
            return []

        return self._format(rows)

    # ---------------------------------------
    # Поиск по equipment_id (для Retrieval)
    # ---------------------------------------
    def get_components_by_id(
        self,
        equipment_id: int,
        equipment_quantity: int,
    ):
        query = """
            SELECT
                e.area,
                e.equipment_name,
                ? as equipment_quantity,
                c.component_name,
                c.qty_per_equipment * ? as component_quantity,
                c.unit,
                cost.cost_with_vat,
                c.component_type
            FROM equipment e
            JOIN components c ON c.equipment_id = e.id
            LEFT JOIN costs cost ON cost.component_name = c.component_name
                                AND cost.unit = c.unit
            WHERE e.id = ?
        """

        self.cursor.execute(
            query,
            (
                equipment_quantity,
                equipment_quantity,
                equipment_id,
            ),
        )

        rows = self.cursor.fetchall()

        return self._format(rows)

    # ---------------------------------------
    # Форматирование результата
    # ---------------------------------------
    def _format(self, rows):
        result = []
        for row in rows:
            result.append({
                "line_section":       row[0],
                "equipment":          row[1],
                "equipment_quantity": row[2],
                "component_name":     row[3],
                "component_quantity": row[4],
                "unit":               row[5],
                "cost_with_vat":      row[6],
                "type":               row[7],
            })
        return result

    def close(self):
        self.cursor.close()
        self.conn.close()
