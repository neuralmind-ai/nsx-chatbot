import logging
import os
from logging.handlers import TimedRotatingFileHandler

from settings import settings


def build_timed_logger(logger_name: str, filename: str) -> logging.Logger:
    """
    Returns a logger that logs to a file that is rotated daily
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    os.makedirs(f"{settings.log_path}/", exist_ok=True)
    path = f"{settings.log_path}/{filename}"
    handler = TimedRotatingFileHandler(path, when="d", interval=1, utc=True)
    logger.addHandler(handler)

    return logger
