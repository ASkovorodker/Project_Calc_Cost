"""
Построить FAISS-индекс оборудования из текущей SQLite-БД.

Обёртка над project_calc.parser.index_builder.IndexBuilder.
Удобно, что все вспомогательные скрипты лежат в одной папке scripts/.

Запуск:
    python scripts/build_index.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from project_calc.parser.index_builder import IndexBuilder


def main() -> int:
    try:
        n = IndexBuilder().build()
    except RuntimeError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return 1
    print(f"OK: построено {n} объектов в индексе.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
