class ValidationError(Exception):
    pass


class Validator:

    @staticmethod
    def normalize_str(value, field):
        if value is None:
            raise ValidationError(f"{field} = NULL")

        value = str(value).strip()
        if not value:
            raise ValidationError(f"{field} пустой")

        return value

    @staticmethod
    def normalize_float(value, field):
        if value is None:
            raise ValidationError(f"{field} = NULL")

        try:
            value = float(value)
        except Exception:
            raise ValidationError(f"{field} не число: {value}")

        if value <= 0:
            raise ValidationError(f"{field} <= 0")

        return value

    def validate(self, raw_row: dict) -> dict:
        return {
            "area": self.normalize_str(raw_row["area"], "area"),
            "equipment_name": self.normalize_str(
                raw_row["equipment_name"], "equipment_name"
            ),
            "component_name": self.normalize_str(
                raw_row["component_name"], "component_name"
            ),
            "qty_per_equipment": self.normalize_float(
                raw_row["qty_per_equipment"], "qty_per_equipment"
            ),
            "unit": self.normalize_str(raw_row["unit"], "unit"),
            "component_type": self.normalize_str(
                raw_row["component_type"], "component_type"
            ),
            "cost_with_vat": self.normalize_float(
                raw_row["cost_with_vat"], "cost_with_vat"
            ),
        }
