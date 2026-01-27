"""Настройка логирования"""
import logging
import sys
from pathlib import Path

# Добавляем корневую директорию в путь для импорта config
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import LOG_LEVEL, LOG_FILE


def setup_logger(name: str) -> logging.Logger:
    """Создаёт и настраивает logger"""
    logger = logging.getLogger(name)

    # Проверяем, что handlers ещё не добавлены
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL))

    # Консоль handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Файл handler
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)

    # Формат
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
