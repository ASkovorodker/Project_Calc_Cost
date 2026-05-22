"""
Entry-point генератора расчёта.

Запуск:
    python -m project_calc.generator
    python -m project_calc.generator --input ... --template ... --output ...

В release-режиме (PyInstaller) запускается без аргументов — пути
берутся из config (input.xlsx и result.xlsx в data/, template.xlsx
в template/). Для отладки можно перекрыть любым из CLI-аргументов
или env-переменными INPUT_PATH/OUTPUT_PATH/TEMPLATE_PATH.

Pipeline:
    InputReader → для каждой строки:
        1) QueryService.get_components_for_equipment — прямой поиск в БД
        2) если нет — SearchService.search → лучший match → get_components_by_id
        3) если ничего не подошло — строка с пометкой "НЕ НАЙДЕНО В БД"
    → ExcelGenerator.generate → result.xlsx

SearchService инициализируется ЛЕНИВО: модель и FAISS-индекс грузятся
только когда прямой поиск не нашёл ответа в БД. Это экономит 3-5 секунд
старта в типичном случае, когда БД покрывает все запросы.
"""
from __future__ import annotations

import os

# Offline-режим для HuggingFace / sentence_transformers.
# Должно стоять ДО первого импорта sentence_transformers (даже косвенного через
# SearchService → Embedder). setdefault — чтобы разработчик мог принудительно
# включить онлайн через env, не правя код.
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

from project_calc.common.config import (
    INPUT_PATH, OUTPUT_PATH, TEMPLATE_PATH, ensure_dirs,
)
from project_calc.common.logging_.logger import get_logger
from project_calc.generator.input_reader import InputReader, InputReaderError
from project_calc.generator.query_service import QueryService
from project_calc.generator.excel_generator import ExcelGenerator, ExcelGeneratorError


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m project_calc.generator",
        description="Генератор расчёта на основе input.xlsx",
    )
    p.add_argument("--input",    default=str(INPUT_PATH),
                   help=f"Входной .xlsx (по умолчанию: {INPUT_PATH})")
    p.add_argument("--template", default=str(TEMPLATE_PATH),
                   help=f"Шаблон расчёта (по умолчанию: {TEMPLATE_PATH})")
    p.add_argument("--output",   default=str(OUTPUT_PATH),
                   help=f"Выходной .xlsx (по умолчанию: {OUTPUT_PATH})")
    p.add_argument("--top-k", type=int, default=5,
                   help="Сколько кандидатов брать из retrieval (по умолчанию 5)")
    return p.parse_args(argv)


class _LazySearch:
    """Обёртка с ленивой инициализацией SearchService.

    Реальный сервис создаётся при первом вызове .search() — модель и индекс
    грузятся только если прямой поиск в БД не нашёл ответа. В типичном
    случае (БД покрывает все запросы) ML-стек не трогается совсем.
    """

    def __init__(self, top_k: int):
        self.top_k = top_k
        self._service = None

    def search(self, query: str, expected_area: str | None = None) -> dict:
        if self._service is None:
            # Импорт здесь, чтобы не тянуть sentence_transformers
            # при холодном старте генератора.
            from project_calc.common.retrieval.search_service import SearchService
            self._service = SearchService(top_k=self.top_k)
        return self._service.search(query=query, expected_area=expected_area)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    ensure_dirs()
    logger = get_logger()

    input_path    = Path(args.input)
    template_path = Path(args.template)
    output_path   = Path(args.output)

    stats: Counter = Counter()
    missing_blocks: list[tuple[str, str]] = []

    query_service: QueryService | None = None
    try:
        # 1. Прочитать input
        reader = InputReader(str(input_path))
        input_data = reader.read()
        print(f"Прочитано строк из input: {len(input_data)}")

        # 2. Открыть БД. SearchService создаётся лениво.
        query_service = QueryService()
        search        = _LazySearch(top_k=args.top_k)

        full_data: list[dict] = []

        # 3. Обработка строк
        for row in input_data:
            line_section = row["line_section"]
            equipment    = row["equipment"]
            quantity     = row["quantity"]

            print(f"\nОбработка: {line_section} | {equipment}")

            # 3.1 Прямой поиск
            components = query_service.get_components_for_equipment(
                line_section=line_section,
                equipment=equipment,
                equipment_quantity=quantity,
            )

            # Е.1.2: status="DIRECT" для всех компонентов, найденных
            # прямым поиском. Перезапишется ниже, если уйдём в retrieval.
            if components:
                for comp in components:
                    comp["status"] = "DIRECT"

            # 3.2 Retrieval — только если не нашли напрямую
            if not components:
                print("   прямого совпадения нет, запуск Retrieval...")
                try:
                    search_result = search.search(
                        query=f"{line_section} {equipment}",
                        expected_area=line_section,
                    )
                except FileNotFoundError as e:
                    # Индекс не построен — фатально не падаем, помечаем
                    # текущую строку как не найденную и логируем.
                    logger.critical(
                        None,
                        f"Retrieval недоступен: {e}",
                        {"area": line_section, "equipment": equipment},
                    )
                    search_result = {
                        "decision": "REJECT",
                        "confidence": 0.0,
                        "results": [],
                    }

                decision   = search_result["decision"]
                confidence = search_result["confidence"]
                results    = search_result["results"]
                stats[decision] += 1

                print(f"   Decision: {decision}, confidence={confidence:.3f}")

                if decision in ("ACCEPT", "REVIEW") and results:
                    best = results[0]
                    print(f"   используем: {best['equipment_name']} (area: {best['area']})")
                    components = query_service.get_components_by_id(
                        equipment_id=best["equipment_id"],
                        equipment_quantity=quantity,
                    )

                    # Е.1.1: подменить equipment в каждом компоненте на
                    # составное имя "<имя из input> — <имя из БД>".
                    # Это даёт инженеру видеть и оригинальный запрос,
                    # и то, какое оборудование retrieval подобрал.
                    # При случайном совпадении имён (например, после
                    # пробельной нормализации) — не дублируем.
                    db_name = best["equipment_name"]
                    if equipment.strip() == db_name.strip():
                        combined = equipment
                    else:
                        combined = f"{equipment} — {db_name}"
                    print(f"   составное имя: {combined}")
                    # Е.1.2: статус = RETRIEVAL_ACCEPT или RETRIEVAL_REVIEW
                    retrieval_status = f"RETRIEVAL_{decision}"
                    for comp in components:
                        comp["equipment"] = combined
                        comp["status"] = retrieval_status
                else:
                    print("   Retrieval не дал подходящего результата.")
                    components = []

            # 3.3 Если всё равно пусто — кладём пометку
            if not components:
                missing_blocks.append((line_section, equipment))
                logger.error(
                    None,
                    f"Не найден блок: {line_section} | {equipment}",
                    {"area": line_section, "equipment": equipment, "qty": quantity},
                )
                full_data.append({
                    "line_section":       line_section,
                    "equipment":          equipment,
                    "equipment_quantity": quantity,
                    "component_name":     "НЕ НАЙДЕНО В БД",
                    "component_quantity": None,
                    "unit":               None,
                    "cost_with_vat":      None,
                    "type":               "ОТСУТСТВУЕТ В БД",
                    # Е.1.2: статус = REJECT (не нашли ни прямым,
                    # ни через retrieval — либо retrieval вернул REJECT)
                    "status":             "REJECT",
                })
            else:
                full_data.extend(components)

        # 4. Генерация Excel
        generator = ExcelGenerator(str(template_path))
        output_file = generator.generate(
            data=full_data,
            output_path=str(output_path),
        )
        print(f"\nФайл создан: {output_file}")

        # 5. Сводка
        print("\n=== СТАТИСТИКА RETRIEVAL ===")
        for k in ("ACCEPT", "REVIEW", "REJECT"):
            print(f"  {k}: {stats[k]}")
        if missing_blocks:
            print("\nНе найдены блоки:")
            for area, eq in missing_blocks:
                print(f"  - {area} | {eq}")

        return 0

    except InputReaderError as e:
        print(f"\nОшибка во входном файле: {e}", file=sys.stderr)
        logger.critical(None, f"InputReaderError: {e}", {"input": str(input_path)})
        return 1
    except ExcelGeneratorError as e:
        print(f"\nОшибка генерации Excel: {e}", file=sys.stderr)
        logger.critical(None, f"ExcelGeneratorError: {e}", {"template": str(template_path)})
        return 1
    except Exception as e:
        print(f"\nНепредвиденная ошибка: {e}", file=sys.stderr)
        logger.critical(None, f"Непредвиденная ошибка: {e}", {})
        return 1
    finally:
        if query_service is not None:
            query_service.close()


if __name__ == "__main__":
    sys.exit(main())
