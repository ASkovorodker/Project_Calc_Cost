from pathlib import Path
from typing import List, Dict

import pandas as pd


REQUIRED_COLUMNS = [
    "Участок линии",
    "Единица промышленного оборудования",
    "Количество единиц промышленного оборудования",
]


class InputReaderError(Exception):
    """Ошибка входного файла генератора."""
    pass


class InputReader:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)

    def read(self) -> List[Dict]:
        """
        Читает входной Excel файл и возвращает список словарей:
        [
            {
                "line_section": "...",
                "equipment": "...",
                "quantity": int
            }
        ]
        """

        self._validate_file_exists()

        df = pd.read_excel(self.file_path)

        self._validate_columns(df)

        df = self._normalize_dataframe(df)

        return df.to_dict(orient="records")

    # ----------------------------
    # Валидации
    # ----------------------------

    def _validate_file_exists(self):
        if not self.file_path.exists():
            raise InputReaderError(f"Файл не найден: {self.file_path}")

    def _validate_columns(self, df: pd.DataFrame):
        missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
        if missing:
            raise InputReaderError(
                f"Входной файл не содержит обязательные колонки: {missing}"
            )

    # ----------------------------
    # Нормализация
    # ----------------------------

    def _normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df[REQUIRED_COLUMNS].copy()

        df = df.rename(columns={
            "Участок линии": "line_section",
            "Единица промышленного оборудования": "equipment",
            "Количество единиц промышленного оборудования": "quantity",
        })

        df["line_section"] = df["line_section"].astype(str).str.strip()
        df["equipment"] = df["equipment"].astype(str).str.strip()

        try:
            df["quantity"] = df["quantity"].astype(int)
        except ValueError:
            raise InputReaderError(
                "Колонка 'Количество единиц промышленного оборудования' "
                "должна содержать целые числа."
            )

        if (df["quantity"] <= 0).any():
            raise InputReaderError("Количество единиц должно быть больше 0.")

        return df
