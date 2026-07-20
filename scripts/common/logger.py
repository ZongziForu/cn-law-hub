"""Logging setup for crawlers."""

import logging
import sys
from pathlib import Path

from .text_utils import ensure_dir


def setup_logger(output_root: Path, name: str = "law_crawler") -> logging.Logger:
    ensure_dir(output_root)
    ensure_dir(output_root / "logs")
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers = []
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(output_root / "logs" / "run.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    return logger
