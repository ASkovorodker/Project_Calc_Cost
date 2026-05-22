"""
Скачать sentence-transformers модель и сохранить локально.

Запускается один раз на dev-машине при наличии интернета — после этого
модель лежит в models/ и используется генератором/index_builder в offline-режиме.

Запуск:
    python scripts/download_model.py

После выполнения папка models/multilingual-e5-base/ должна весить ~1.1 GB.
В git её НЕ коммитим (см. .gitignore: models/).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Чтобы можно было запускать из любой папки
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sentence_transformers import SentenceTransformer

from project_calc.common.config import MODEL_PATH

# Идентификатор модели на HuggingFace. Менять только синхронно
# с реальной заменой ML-модели.
MODEL_HF_ID = "intfloat/multilingual-e5-base"


def folder_size_mb(path: Path) -> float:
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            total += f.stat().st_size
    return total / (1024 * 1024)


def main() -> int:
    print(f"Скачивание модели: {MODEL_HF_ID}")
    print(f"Целевая папка:     {MODEL_PATH}")
    print()
    print("Это может занять несколько минут (около 1.1 GB).")
    print()

    if MODEL_PATH.exists() and any(MODEL_PATH.iterdir()):
        print(f"WARNING: папка {MODEL_PATH} уже существует и не пуста.")
        print("Если хотите перекачать — удалите её и запустите снова.")
        return 1

    # SentenceTransformer сам скачает модель и закеширует.
    model = SentenceTransformer(MODEL_HF_ID)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(MODEL_PATH))

    size_mb = folder_size_mb(MODEL_PATH)
    print()
    print(f"Готово.")
    print(f"  путь:   {MODEL_PATH}")
    print(f"  размер: {size_mb:.1f} MB")
    print()
    print("Теперь genrator/index_builder будут использовать локальную модель,")
    print("интернет на машине пользователя не нужен.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
