class Normalizer:
    """
    Приведение данных к каноническому виду.
    Никаких проверок — только нормализация.
    """

    UNIT_ALIASES = {
        "шт.": "шт",
        "штука": "шт",
        "штук": "шт",
        "м.": "м",
        "метр": "м",
        "метров": "м",
        "кг.": "кг",
    }

    TYPE_ALIASES = {
        "металлоконструкции": "м/к",
        "комп.": "комп",
        "смен.": "смен",
        "товар": "товар",
        "товары": "товар",
        "тов.": "товар",
    }

    @staticmethod
    def clean_string(value: str) -> str:
        return " ".join(value.strip().split())

    def normalize_unit(self, unit: str) -> str:
        unit = self.clean_string(unit.lower())
        return self.UNIT_ALIASES.get(unit, unit)

    def normalize_type(self, component_type: str) -> str:
        component_type = self.clean_string(component_type.lower())
        return self.TYPE_ALIASES.get(component_type, component_type)

    def normalize(self, row: dict) -> dict:
        return {
            "area": self.clean_string(row["area"]),
            "equipment_name": self.clean_string(row["equipment_name"]),
            "component_name": self.clean_string(row["component_name"]),
            "qty_per_equipment": float(row["qty_per_equipment"]),
            "unit": self.normalize_unit(row["unit"]),
            "component_type": self.normalize_type(row["component_type"]),
            "cost_with_vat": float(row["cost_with_vat"]),
        }
