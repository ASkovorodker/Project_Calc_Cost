"""
Подключение к SQLite-БД project_calc.

На каждом подключении:
  * PRAGMA foreign_keys = ON — обязательно для каскадов и FK
    (в SQLite по умолчанию выключено, нужно включать в каждой сессии)
  * row_factory = sqlite3.Row — доступ к колонкам и по индексу,
    и по имени (row["id"]), легко конвертится в dict(row)
  * read_only=True открывает БД через URI file:...?mode=ro —
    в этом режиме генератор у пользователя гарантированно не модифицирует
    поставочную БД

Путь к БД определяется в порядке приоритета:
  1. явный аргумент db_path функции get_connection()
  2. переменная окружения DB_PATH
  3. fallback <cwd>/data/database.db (для разработки)

После Шага 4 (project_calc/common/config.py) вызывающий код может
импортировать DB_PATH из конфига и передавать его явным аргументом
либо полагаться на env DB_PATH, выставляемый при старте приложения.
Сам connection.py остаётся независимым от config.py для тестируемости.
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional, Union

PathLike = Union[str, Path]


class DatabaseConnectionError(Exception):
    """Ошибка подключения к БД (файла нет, нет прав и т.п.)."""


def _resolve_db_path(db_path: Optional[PathLike]) -> Path:
    """
    Выбор пути к БД:
      1. явный аргумент,
      2. env DB_PATH,
      3. <cwd>/data/database.db.
    """
    if db_path is not None:
        return Path(db_path)

    env_value = os.getenv("DB_PATH")
    if env_value:
        return Path(env_value)

    return Path.cwd() / "data" / "database.db"


def get_connection(
    db_path: Optional[PathLike] = None,
    read_only: bool = False,
) -> sqlite3.Connection:
    """
    Открыть соединение с SQLite-БД.

    :param db_path: явный путь к .db-файлу. Если None — берётся
        из переменной окружения DB_PATH или из fallback.
    :param read_only: открыть в режиме только для чтения. В этом режиме
        БД должна существовать, иначе DatabaseConnectionError.
        Для read-write режима родительская папка создаётся автоматически.
    :return: sqlite3.Connection с включёнными foreign keys и row_factory=Row.
    :raises DatabaseConnectionError: если read_only=True, а файла БД нет.
    """
    path = _resolve_db_path(db_path).resolve()

    if read_only:
        if not path.exists():
            raise DatabaseConnectionError(f"БД не найдена: {path}")
        # as_posix() — чтобы URI работал одинаково на Linux и Windows
        # (в Windows-путях обратные слеши в URI могут трактоваться неоднозначно).
        uri = f"file:{path.as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))

    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn
