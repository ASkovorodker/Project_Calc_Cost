"""
Поиск по FAISS-индексу оборудования.

Жёсткие пути к индексу заменены на импорт из project_calc.common.config.
Это значит:
  * В dev — индекс читается из data/index/ (или из env INDEX_PATH).
  * В release — из той же папки рядом с calculator.exe.
  * Для тестов можно подменить INDEX_PATH/INDEX_META_PATH через env.

Формат метаданных — JSON (см. equipment_meta.json в data/index/).
Старый pickle-формат от index_builder.py больше не поддерживается —
index_builder будет приведён к JSON на Шаге 9.
"""
import json

import faiss
import numpy as np

from project_calc.common.retrieval.embedder import Embedder
from project_calc.common.retrieval.confidence import ConfidenceEvaluator
from project_calc.common.config import INDEX_PATH, INDEX_META_PATH


class SearchService:

    def __init__(
        self,
        top_k: int = 5,
        threshold: float = 0.87,
        margin: float = 0.03,
    ):
        self.top_k = top_k

        self.embedder = Embedder()
        self.confidence_evaluator = ConfidenceEvaluator(
            threshold=threshold,
            margin=margin,
        )

        self.index = None
        self.metadata = None

        self._load_index()

    # ------------------------------
    # Загрузка индекса
    # ------------------------------
    def _load_index(self):
        if not INDEX_PATH.exists():
            raise FileNotFoundError(
                f"FAISS индекс не найден: {INDEX_PATH}. "
                f"Запустите index_builder."
            )

        if not INDEX_META_PATH.exists():
            raise FileNotFoundError(
                f"Файл метаданных не найден: {INDEX_META_PATH}."
            )

        # faiss.read_index ожидает str
        self.index = faiss.read_index(str(INDEX_PATH))

        with open(INDEX_META_PATH, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

    # ------------------------------
    # Основной поиск
    # ------------------------------
    def search(self, query: str, expected_area: str = None) -> dict:

        if not query or not query.strip():
            return {
                "query": query,
                "confidence": 0.0,
                "decision": "REJECT",
                "gap": 0.0,
                "results": [],
            }

        # 1. embedding query
        query_vector = self.embedder.embed_query(query)
        query_vector = np.array([query_vector]).astype(np.float32)

        # 2. поиск
        similarities, indices = self.index.search(
            query_vector,
            self.top_k,
        )

        similarities = similarities[0]
        indices = indices[0]

        results = []

        for score, idx in zip(similarities, indices):

            if idx == -1:
                continue

            meta = self.metadata[idx]

            results.append({
                "equipment_id": meta["equipment_id"],
                "equipment_name": meta["equipment_name"],
                "area": meta["area"],
                "similarity": float(score),
            })

        # ------------------------------
        # 3. penalty за area
        # ------------------------------
        if expected_area:
            for r in results:
                if r["area"] != expected_area:
                    r["similarity"] *= 0.92

        # ------------------------------
        # 4. пересортировка
        # ------------------------------
        results = sorted(
            results,
            key=lambda x: x["similarity"],
            reverse=True,
        )

        similarities = [r["similarity"] for r in results]

        # ------------------------------
        # 5. gap
        # ------------------------------
        gap = 0.0
        if len(similarities) > 1:
            gap = similarities[0] - similarities[1]

        # ------------------------------
        # 6. decision
        # ------------------------------
        decision = self.confidence_evaluator.evaluate(similarities)

        return {
            "query": query,
            "confidence": similarities[0] if similarities else 0.0,
            "decision": decision,
            "gap": gap,
            "results": results,
        }
