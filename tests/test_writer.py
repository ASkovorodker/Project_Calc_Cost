import psycopg2
from writer import DBWriter


def main():
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        dbname="p_calc",
        user="postgres",
        password=" "
    )

    writer = DBWriter(conn)

    test_rows = [
        {
            "area": "Линия 1",
            "equipment_name": "Пресс гидравлический",
            "component_name": "Насос",
            "qty_per_equipment": 2,
            "unit": "шт",
            "component_type": "товар",
            "cost_with_vat": 12000
        },
        # Та же строка, но БОЛЬШАЯ цена → цена обновится
        {
            "area": "Линия 1",
            "equipment_name": "Пресс гидравлический",
            "component_name": "Насос",
            "qty_per_equipment": 2,
            "unit": "шт",
            "component_type": "товар",
            "cost_with_vat": 15000
        },
        # Та же строка, но БОЛЬШЕ количество → qty обновится
        {
            "area": "Линия 1",
            "equipment_name": "Пресс гидравлический",
            "component_name": "Насос",
            "qty_per_equipment": 3,
            "unit": "шт",
            "component_type": "товар",
            "cost_with_vat": 14000  # меньше → цена НЕ обновится
        },
        # Новый компонент
        {
            "area": "Линия 1",
            "equipment_name": "Пресс гидравлический",
            "component_name": "Шланг РВД",
            "qty_per_equipment": 4,
            "unit": "м",
            "component_type": "комп",
            "cost_with_vat": 800
        }
    ]

    for row in test_rows:
        print(f"WRITE → {row}")
        writer.write_row(row)

    conn.close()


if __name__ == "__main__":
    main()
