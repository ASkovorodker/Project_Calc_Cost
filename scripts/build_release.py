"""
Подготовка release-bundle для PyInstaller (Этап Г → Этап Д).

Workflow по умолчанию:
  1. Удалить старые БД (data/database.db) и индекс (data/index/)
  2. Создать пустую БД по схеме (scripts/init_db.py)
  3. Запустить парсер на data/raw_projects/ → наполнить БД
  4. Построить FAISS-индекс из БД (scripts/build_index.py)
  5. Проверить наличие модели и шаблона, напечатать сводку размеров

После успешного завершения всё, что нужно PyInstaller, лежит в стандартных
местах config.py (DB_PATH / INDEX_PATH / INDEX_META_PATH / MODEL_PATH /
TEMPLATE_PATH).

Опции:
  --raw <path>     папка с историческими xlsx (по умолчанию data/raw_projects/)
  --skip-parse     пропустить парсинг (использовать существующую БД)
  --skip-index    пропустить построение индекса
  --no-clean       не удалять старые БД/индекс перед сборкой
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from project_calc.common.config import (
    DB_PATH, INDEX_PATH, INDEX_META_PATH, INDEX_DIR,
    MODEL_PATH, TEMPLATE_PATH,
)


# ============================================================
# Утилиты вывода
# ============================================================

def section(name: str) -> None:
    bar = "=" * 60
    print(f"\n{bar}\n  {name}\n{bar}")


def step(idx: int, total: int, desc: str) -> None:
    print(f"\n[{idx}/{total}] {desc}")


def folder_size_mb(p: Path) -> float:
    if not p.exists():
        return 0.0
    if p.is_file():
        return p.stat().st_size / (1024 * 1024)
    return sum(
        f.stat().st_size for f in p.rglob("*") if f.is_file()
    ) / (1024 * 1024)


def run_cmd(cmd: list[str], step_name: str) -> int:
    """Запустить подпроцесс и вернуть rc. Печатает команду перед запуском."""
    pretty = " ".join(cmd)
    print(f"  + {pretty}")
    return subprocess.run(cmd).returncode


# ============================================================
# CLI
# ============================================================

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python scripts/build_release.py",
        description="Подготовка артефактов для PyInstaller-сборки",
    )
    p.add_argument(
        "--raw",
        default=str(ROOT / "data" / "raw_projects"),
        help="Папка с историческими xlsx (по умолчанию data/raw_projects/)",
    )
    p.add_argument("--skip-parse", action="store_true",
                   help="Пропустить парсинг (использовать существующую БД)")
    p.add_argument("--skip-index", action="store_true",
                   help="Пропустить построение индекса")
    p.add_argument("--no-clean", action="store_true",
                   help="Не удалять старые БД/индекс перед сборкой")
    return p.parse_args()


# ============================================================
# main
# ============================================================

def main() -> int:
    args = parse_args()
    section("BUILD RELEASE")
    print(f"Корень проекта: {ROOT}")

    total = 5

    # ---------- 1. Clean ----------
    step(1, total, "Очистка старых артефактов")
    if args.no_clean:
        print("  пропущено (--no-clean)")
    else:
        cleaned = False
        if DB_PATH.exists():
            DB_PATH.unlink()
            print(f"  удалено  {DB_PATH}")
            cleaned = True
        # Журналы SQLite на всякий случай
        for suf in ("-journal", "-wal", "-shm"):
            j = DB_PATH.with_suffix(DB_PATH.suffix + suf)
            if j.exists():
                j.unlink()
                print(f"  удалено  {j}")
                cleaned = True
        if INDEX_DIR.exists():
            shutil.rmtree(INDEX_DIR)
            print(f"  удалена   {INDEX_DIR}")
            cleaned = True
        if not cleaned:
            print("  (нечего удалять)")

    # ---------- 2. Init DB ----------
    step(2, total, "Создание пустой БД")
    rc = run_cmd(
        [sys.executable, str(Path(__file__).parent / "init_db.py")],
        "init_db",
    )
    if rc != 0:
        section("FAILED on step 2 (init_db)")
        return rc

    # ---------- 3. Parse ----------
    step(3, total, "Парсинг исторических xlsx")
    if args.skip_parse:
        print("  пропущено (--skip-parse)")
    else:
        raw = Path(args.raw)
        if not raw.exists():
            print(f"FAIL: папка не найдена: {raw}", file=sys.stderr)
            return 1
        if not list(raw.glob("*.xlsx")):
            print(f"FAIL: в {raw} нет .xlsx файлов", file=sys.stderr)
            print("Положите исторические xlsx в data/raw_projects/", file=sys.stderr)
            return 1
        rc = run_cmd(
            [sys.executable, "-m", "project_calc.parser", "--input", str(raw)],
            "parser",
        )
        if rc != 0:
            section("FAILED on step 3 (parser)")
            return rc

    # ---------- 4. Index ----------
    step(4, total, "Построение FAISS-индекса")
    if args.skip_index:
        print("  пропущено (--skip-index)")
    else:
        rc = run_cmd(
            [sys.executable, str(Path(__file__).parent / "build_index.py")],
            "build_index",
        )
        if rc != 0:
            section("FAILED on step 4 (build_index)")
            return rc

    # ---------- 5. Сводка артефактов ----------
    step(5, total, "Проверка артефактов")

    artifacts = [
        ("БД",          DB_PATH),
        ("Index",       INDEX_PATH),
        ("Index meta",  INDEX_META_PATH),
        ("Model",       MODEL_PATH),
        ("Template",    TEMPLATE_PATH),
    ]

    print()
    print(f"  {'Артефакт':<14s} {'Размер':>11s}  {'Статус':<8s} Путь")
    print(f"  {'-'*14} {'-'*11}  {'-'*8} {'-'*40}")
    total_mb = 0.0
    missing: list[str] = []
    for name, path in artifacts:
        exists = path.exists()
        size = folder_size_mb(path) if exists else 0.0
        total_mb += size
        status = "OK" if exists else "MISSING"
        if not exists:
            missing.append(name)
        size_str = f"{size:>8.1f} MB" if exists else "—"
        print(f"  {name:<14s} {size_str:>11s}  {status:<8s} {path}")

    print()
    print(f"  ИТОГО (приблизительно идёт в bundle): {total_mb:,.1f} MB")
    print()

    if missing:
        section(f"WARNING: отсутствуют артефакты: {', '.join(missing)}")
        if "Model" in missing:
            print("Скачайте модель: python scripts/download_model.py")
        if "Template" in missing:
            print(f"Положите шаблон в {TEMPLATE_PATH}")
        return 1

    section("READY — артефакты на месте, можно запускать PyInstaller (Этап Д)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
