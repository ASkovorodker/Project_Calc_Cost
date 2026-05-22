"""
Entry-point парсера. Парсер — инструмент разработчика для наполнения
SQLite-БД историческими расчётами. На машине пользователя он отсутствует.

Запуск:
    python -m project_calc.parser --input data/raw_projects/
    python -m project_calc.parser --input path/to/single.xlsx --dry-run
    python -m project_calc.parser --input ./files --db /tmp/test.db

Pipeline:
    ExcelReader → Validator → Normalizer → группировка по
    (area, equipment_name) → DBWriter.write_equipment(area, eq, items)

Ошибки:
    * невалидная строка Excel — лог.error, строка пропускается,
      остальные строки в её группе всё равно собираются и пишутся;
    * ошибка записи блока (IntegrityError, FK и т.п.) — лог.critical,
      блок пропускается, парсер продолжает со следующим оборудованием.

Схема:
    Если БД пустая или таблиц нет, init_sqlite.sql применяется
    автоматически (CREATE TABLE IF NOT EXISTS идемпотентно).
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

from project_calc.common.config import ensure_dirs
from project_calc.common.db.connection import get_connection
from project_calc.common.logging_.logger import get_logger
from project_calc.parser.excel.reader import ExcelReader
from project_calc.parser.validation.validator import Validator, ValidationError
from project_calc.parser.normalize.normalizer import Normalizer
from project_calc.parser.db_writer import DBWriter


SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent
    / "common" / "db" / "schema" / "init_sqlite.sql"
)


# ============================================================
# CLI
# ============================================================

def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m project_calc.parser",
        description="Парсер исторических расчётов в SQLite-БД project_calc",
    )
    p.add_argument(
        "--input",
        required=True,
        help="Путь к .xlsx файлу или к папке с .xlsx",
    )
    p.add_argument(
        "--db",
        help="Override пути к БД (иначе берётся из config.DB_PATH / env DB_PATH)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Прогнать чтение и валидацию, ничего не писать в БД",
    )
    return p.parse_args(argv)


# ============================================================
# Сбор файлов
# ============================================================

def collect_xlsx_files(input_path: Path) -> list[Path]:
    """Собрать список xlsx-файлов из файла или папки.

    Игнорирует lock-файлы Excel (`~$<имя>.xlsx`).
    """
    if input_path.is_file():
        if input_path.suffix.lower() != ".xlsx":
            raise SystemExit(f"Файл не .xlsx: {input_path}")
        return [input_path]

    if input_path.is_dir():
        files = sorted(input_path.glob("*.xlsx"))
        files = [f for f in files if not f.name.startswith("~$")]
        if not files:
            raise SystemExit(f"В папке нет .xlsx файлов: {input_path}")
        return files

    raise SystemExit(f"Путь не найден: {input_path}")


# ============================================================
# Применение схемы
# ============================================================

def ensure_schema(conn) -> None:
    """Применить init_sqlite.sql. Идемпотентно (CREATE IF NOT EXISTS)."""
    if not SCHEMA_PATH.exists():
        raise SystemExit(f"Не найден файл схемы: {SCHEMA_PATH}")
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema_sql)
    conn.commit()


# ============================================================
# Обработка одного файла
# ============================================================

def _empty_stats() -> dict:
    return {
        "rows_total":       0,
        "rows_valid":       0,
        "rows_failed":      0,
        "groups":           0,
        "equipment_new":    0,
        "components_added": 0,
        "costs_upserted":   0,
        "groups_failed":    0,
    }


def process_file(
    file_path: Path,
    validator: Validator,
    normalizer: Normalizer,
    writer: Optional[DBWriter],
    logger,
) -> dict:
    """Прочитать xlsx, провалидировать, нормализовать, сгруппировать
    и записать в БД (если writer != None). Возвращает stats."""
    stats = _empty_stats()

    reader = ExcelReader(str(file_path))
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)

    for raw in reader.read_rows():
        stats["rows_total"] += 1
        try:
            validated = validator.validate(raw)
            normalized = normalizer.normalize(validated)
        except ValidationError as e:
            stats["rows_failed"] += 1
            logger.error(
                raw.get("row_number"),
                str(e),
                {"file": file_path.name, "raw": raw},
            )
            continue
        except Exception as e:
            stats["rows_failed"] += 1
            logger.critical(
                raw.get("row_number"),
                f"Непредвиденная ошибка нормализации: {e}",
                {"file": file_path.name, "raw": raw},
            )
            continue

        stats["rows_valid"] += 1
        key = (normalized["area"], normalized["equipment_name"])
        groups[key].append(normalized)

    stats["groups"] = len(groups)

    if writer is None:
        return stats

    for (area, eq), items in groups.items():
        try:
            res = writer.write_equipment(area, eq, items)
        except Exception as e:
            stats["groups_failed"] += 1
            logger.critical(
                None,
                f"Ошибка записи блока: {e}",
                {
                    "file":      file_path.name,
                    "area":      area,
                    "equipment": eq,
                    "n_items":   len(items),
                },
            )
            continue

        if res["equipment_new"]:
            stats["equipment_new"] += 1
        stats["components_added"] += res["components_added"]
        stats["costs_upserted"]   += res["costs_upserted"]

    return stats


# ============================================================
# main
# ============================================================

def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    if args.db:
        os.environ["DB_PATH"] = args.db

    ensure_dirs()
    logger = get_logger()

    input_path = Path(args.input).resolve()
    files = collect_xlsx_files(input_path)
    print(f"Найдено .xlsx файлов: {len(files)}")

    validator  = Validator()
    normalizer = Normalizer()

    conn = None
    writer = None
    if not args.dry_run:
        conn = get_connection()
        ensure_schema(conn)
        writer = DBWriter(conn)

    total = _empty_stats()
    total["files"] = 0

    try:
        for f in files:
            print(f"\n--- {f.name} ---")
            s = process_file(f, validator, normalizer, writer, logger)
            total["files"] += 1
            for k in s:
                total[k] += s[k]
            print(
                f"  строк всего/валидно/брак: "
                f"{s['rows_total']}/{s['rows_valid']}/{s['rows_failed']}"
            )
            print(
                f"  групп: {s['groups']}, "
                f"новых equipment: {s['equipment_new']}, "
                f"брак блоков: {s['groups_failed']}"
            )
            print(
                f"  components: +{s['components_added']}, "
                f"costs upserted: {s['costs_upserted']}"
            )
    finally:
        if conn is not None:
            conn.close()

    print("\n=== ИТОГО ===")
    for k, v in total.items():
        print(f"  {k:20s} {v}")
    if args.dry_run:
        print("\n[DRY-RUN] данные в БД не записаны")

    # Код возврата: ненулевой, если есть ошибки записи блоков
    return 1 if total["groups_failed"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
