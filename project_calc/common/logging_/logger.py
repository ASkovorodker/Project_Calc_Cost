"""
Логирование project_calc.

Лог пишется в файл по пути config.LOG_PATH (по умолчанию data/logs/log.txt).
В консоль сообщения не дублируются (propagate=False).

API через LoggerWrapper заточен под парсер: row_number-ориентированные
сообщения с payload (исходная строка Excel или контекст ошибки). Если
потребуется более общий интерфейс — берётся `wrapped.logger` напрямую.
"""
import logging

from project_calc.common.config import LOG_PATH


def get_logger():
    logger = logging.getLogger("project_calc")
    logger.setLevel(logging.INFO)

    # Чтобы при повторном вызове не добавлялись новые handler'ы
    if logger.handlers:
        return LoggerWrapper(logger)

    # На случай, если ensure_dirs() ещё не вызван
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    # Не дублируем сообщения в консоль через root-logger
    logger.propagate = False

    return LoggerWrapper(logger)


class LoggerWrapper:
    def __init__(self, logger):
        self.logger = logger

    def error(self, row_number, message, payload):
        self.logger.error(
            f"Row {row_number} | {message} | {payload}"
        )

    def critical(self, row_number, message, payload):
        self.logger.critical(
            f"Row {row_number} | {message} | {payload}"
        )
