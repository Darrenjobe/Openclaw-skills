"""
Shared utilities used across Openclaw skills.
"""

import logging
import sys
from pathlib import Path


def setup_logging(name: str, log_dir: Path | None = None, level: int = logging.INFO) -> logging.Logger:
    """
    Create a logger that writes to both stdout and an optional log file.

    Args:
        name:    Logger / skill name.
        log_dir: Directory for log files. If None, logs only to stdout.
        level:   Logging level (default INFO).
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    if not logger.handlers:
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        logger.addHandler(sh)

        if log_dir is not None:
            ensure_dir(log_dir)
            fh = logging.FileHandler(log_dir / f"{name}.log")
            fh.setFormatter(fmt)
            logger.addHandler(fh)

    return logger


def ensure_dir(path: Path) -> Path:
    """Create a directory (and parents) if it doesn't already exist."""
    path.mkdir(parents=True, exist_ok=True)
    return path
