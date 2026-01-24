import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logger(name: str = "n8n_meeting_bot", log_file: str = None) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if logger.handlers:
        logger.handlers.clear()

    formatter = logging.Formatter(
        '%(asctime)s - [%(name)s] - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_file is None:
        log_dir = Path("app/logs")
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log"

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.propagate = False
    return logger


def get_logger(name: str = "n8n_meeting_bot") -> logging.Logger:
    logger = logging.getLogger(name)

    if not logger.handlers:
        return setup_logger(name)
    return logger
