"""
Конфигурация project_calc.

В этом файле собраны все пути к ресурсам и хелперы для их разрешения
в двух режимах работы:

  * dev-режим (запуск из исходников): корень репозитория = базовая папка.
  * release-режим (PyInstaller exe): рядом с calculator.exe = базовая папка.

Дополнительно поддерживаются переменные окружения для override основных
путей. Это удобно для тестов, CI и тонкой настройки без правки кода.

Хелперы:
  * app_dir()       — место, где лежит exe (или корень репо).
                       Сюда пишутся пользовательские артефакты:
                       database.db, FAISS-индекс, input/output/logs, template.
  * bundle_dir()    — sys._MEIPASS (куда PyInstaller распаковывает --add-data)
                       или app_dir() в dev-режиме.
                       Нужно для ресурсов, упакованных внутрь бандла.
  * resource_path() — пробует bundle_dir() первым, потом app_dir().
                       Используется для ресурсов, которые могут лежать
                       как внутри бандла, так и рядом с exe (например, модель).
  * ensure_dirs()   — создать рабочие папки (data/input, data/output,
                       data/logs, родителя data/database.db).
                       Вызывается из __main__.py приложений.

Структура у пользователя (release):
    Project_Calc/
    ├── calculator.exe
    ├── _internal/                 ← PyInstaller --onedir (sys._MEIPASS)
    │   └── ...                       (зависимости, опционально модель)
    ├── template/
    │   └── template.xlsx          ← можно править вручную
    ├── models/                    ← опционально, если модель не в бандле
    │   └── multilingual-e5-base/
    └── data/
        ├── database.db            ← поставочная, read-only при работе
        ├── index/
        │   ├── equipment.index
        │   └── equipment_meta.json
        ├── input/
        │   └── input.xlsx         ← кладёт инженер
        ├── output/
        │   └── result.xlsx        ← появляется после запуска
        └── logs/
            └── log.txt
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Union

PathLike = Union[str, Path]


# ============================================================
# Базовые директории
# ============================================================

def app_dir() -> Path:
    """
    Корневая папка приложения.

    * release (PyInstaller-сборка): папка, где лежит calculator.exe.
    * dev (запуск из исходников): корень репозитория
      (поднимаемся на 2 уровня от project_calc/common/config.py).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[2]


def bundle_dir() -> Path:
    """
    Папка с упакованными в PyInstaller-бандл ресурсами.

    * release: sys._MEIPASS (для --onedir это _internal/).
    * dev: то же, что app_dir().
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return app_dir()


def resource_path(relative: PathLike) -> Path:
    """
    Разрешить путь к ресурсу, который может лежать либо в бандле,
    либо рядом с exe.

    Стратегия поиска:
      1. bundle_dir() / relative — приоритет PyInstaller-бандла,
      2. app_dir() / relative   — fallback на папку рядом с exe.

    Если ресурс не найден ни там, ни там, возвращается путь по app_dir()
    (как наиболее ожидаемый для пользователя). Сама проверка существования
    остаётся за вызывающим кодом — он лучше знает, что делать при отсутствии.
    """
    relative = Path(relative)
    bundled = bundle_dir() / relative
    if bundled.exists():
        return bundled
    return app_dir() / relative


# ============================================================
# Пути к артефактам
# ============================================================

# Корень пользовательских данных (рядом с exe). Override: DATA_DIR.
DATA_DIR: Path = Path(os.getenv("DATA_DIR", app_dir() / "data"))

# SQLite-БД. Override: DB_PATH.
DB_PATH: Path = Path(os.getenv("DB_PATH", DATA_DIR / "database.db"))

# FAISS-индекс. Override: INDEX_PATH, INDEX_META_PATH.
INDEX_DIR: Path       = DATA_DIR / "index"
INDEX_PATH: Path      = Path(os.getenv("INDEX_PATH",      INDEX_DIR / "equipment.index"))
INDEX_META_PATH: Path = Path(os.getenv("INDEX_META_PATH", INDEX_DIR / "equipment_meta.json"))

# ML-модель. Может быть в бандле (через --add-data) ИЛИ рядом с exe в models/.
# Override: MODEL_PATH.
MODEL_PATH: Path = Path(
    os.getenv("MODEL_PATH", resource_path("models/multilingual-e5-base"))
)

# Шаблон расчёта — рядом с exe, чтобы пользователь мог его править.
# Override: TEMPLATE_PATH.
TEMPLATE_PATH: Path = Path(
    os.getenv("TEMPLATE_PATH", app_dir() / "template" / "template.xlsx")
)

# Пользовательские файлы. Override: INPUT_PATH, OUTPUT_PATH, LOG_PATH.
INPUT_PATH: Path  = Path(os.getenv("INPUT_PATH",  DATA_DIR / "input"  / "input.xlsx"))
OUTPUT_PATH: Path = Path(os.getenv("OUTPUT_PATH", DATA_DIR / "output" / "result.xlsx"))
LOG_PATH: Path    = Path(os.getenv("LOG_PATH",    DATA_DIR / "logs"   / "log.txt"))


# ============================================================
# Утилиты
# ============================================================

def ensure_dirs() -> None:
    """
    Создать рабочие папки, в которые приложение пишет файлы.

    Вызывается из __main__.py приложений (parser, generator) до выполнения
    логики — гарантирует, что input/output/logs/data существуют.
    """
    for path in (
        INPUT_PATH.parent,
        OUTPUT_PATH.parent,
        LOG_PATH.parent,
        DB_PATH.parent,
    ):
        path.mkdir(parents=True, exist_ok=True)
