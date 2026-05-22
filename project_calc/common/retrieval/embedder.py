"""
Обёртка над SentenceTransformer.

По умолчанию модель грузится из локальной папки MODEL_PATH (config.py) —
это нужно для offline-режима в release-сборке: пользователь без интернета
получает работающий генератор. Модель пакуется в release-bundle на dev-машине
скриптом scripts/download_model.py.

Опционально в конструктор можно передать другой путь или HuggingFace-ID
(в dev-сценариях). Если передан путь и его нет — кидаем RuntimeError
с подсказкой про download_model.py, иначе SentenceTransformer пойдёт в сеть
и в offline-окружении упадёт с менее понятным сообщением.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import numpy as np
from sentence_transformers import SentenceTransformer

from project_calc.common.config import MODEL_PATH

PathOrId = Union[str, Path]


class Embedder:
    def __init__(self, model: Optional[PathOrId] = None):
        if model is None:
            model = MODEL_PATH

        # Если это локальный путь и его нет — внятная ошибка.
        if isinstance(model, Path) and not model.exists():
            raise RuntimeError(
                f"Папка с моделью не найдена: {model}\n"
                f"Запустите: python scripts/download_model.py"
            )

        self.model = SentenceTransformer(str(model))

    # ---------------------------------
    # Эмбеддинг запроса (query)
    # ---------------------------------
    def embed_query(self, text: str) -> np.ndarray:
        return self.model.encode(
            "query: " + text.strip(),
            normalize_embeddings=True,
        )

    # ---------------------------------
    # Эмбеддинг документа (passage)
    # ---------------------------------
    def embed_passage(self, text: str) -> np.ndarray:
        return self.model.encode(
            "passage: " + text.strip(),
            normalize_embeddings=True,
        )
