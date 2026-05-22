"""
Построение FAISS-индекса оборудования из SQLite-БД.

Артефакты:
  * equipment.index — FAISS-индекс (path из config.INDEX_PATH);
  * equipment_meta.json — метаданные в JSON, тот же формат, что ждёт
    SearchService (path из config.INDEX_META_PATH).

Подключение к БД — read_only=True. Параметры build(index_path, meta_path)
опциональны (по умолчанию из config) — удобно для тестов.

Запуск напрямую:
    python -m project_calc.parser.index_builder
"""
from __future__ import annotations

import os

# Offline-режим — должно стоять ДО первого импорта sentence_transformers
# (он подтянется через Embedder ниже). setdefault, чтобы разработчик мог
# принудительно включить онлайн через env при загрузке/обновлении модели.
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

import json
from pathlib import Path
from typing import Optional

import faiss
import numpy as np

from project_calc.common.retrieval.embedder import Embedder
from project_calc.common.db.connection import get_connection
from project_calc.common.config import INDEX_PATH, INDEX_META_PATH


class IndexBuilder:

    def __init__(self, embedder: Optional[Embedder] = None):
        # embedder опционален — удобно подменять в тестах
        self.embedder = embedder if embedder is not None else Embedder()

    def build(
        self,
        index_path: Optional[Path] = None,
        meta_path: Optional[Path] = None,
    ) -> int:
        """
        Прочитать всё оборудование из БД, посчитать эмбеддинги,
        собрать FAISS-индекс и записать на диск.

        :param index_path: путь к .index файлу. None → берётся из config.
        :param meta_path:  путь к .json файлу с метой. None → из config.
        :return: количество объектов в индексе.
        """
        idx_path  = Path(index_path) if index_path else INDEX_PATH
        meta_path = Path(meta_path)  if meta_path  else INDEX_META_PATH

        conn = get_connection(read_only=True)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, area, equipment_name FROM equipment")
            rows = cursor.fetchall()
            cursor.close()
        finally:
            conn.close()

        if not rows:
            raise RuntimeError(
                "В таблице equipment нет ни одной записи — "
                "нечего индексировать. Сначала запустите парсер."
            )

        vectors: list[np.ndarray] = []
        metadata: list[dict] = []

        for row in rows:
            equipment_id   = row[0]
            area           = row[1]
            equipment_name = row[2]

            text = f"{area} {equipment_name}"
            embedding = self.embedder.embed_passage(text)

            vectors.append(embedding)
            metadata.append({
                "equipment_id":   equipment_id,
                "area":           area,
                "equipment_name": equipment_name,
            })

        vectors_arr = np.array(vectors).astype("float32")
        dimension = vectors_arr.shape[1]

        # IndexFlatIP — inner product, на нормализованных векторах эквивалентно
        # cosine similarity (Embedder делает normalize_embeddings=True).
        index = faiss.IndexFlatIP(dimension)
        index.add(vectors_arr)

        idx_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(idx_path))

        meta_path.parent.mkdir(parents=True, exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        print(f"Индекс построен: {len(metadata)} объектов")
        print(f"  index: {idx_path}")
        print(f"  meta:  {meta_path}")

        return len(metadata)


if __name__ == "__main__":
    IndexBuilder().build()
