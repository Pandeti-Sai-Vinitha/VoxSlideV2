"""
Logging utilities for the PDF processing pipeline with SSE real-time streaming support.
"""
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime


class ImmediateFlushFileHandler(logging.FileHandler):
    """
    Custom FileHandler that flushes after every emit to ensure real-time log streaming.
    This is critical for SSE (Server-Sent Events) to receive logs immediately.
    """
    def emit(self, record):
        try:
            super().emit(record)
            self.flush()  # ✅ CRITICAL: Flush after every log entry
        except Exception:
            self.handleError(record)


def setup_logger(pdf_basename: str, log_file: str) -> logging.Logger:
    """
    Setup logger with immediate flushing for real-time SSE streaming.
    
    Args:
        pdf_basename: Name of the PDF file (used for logger name)
        log_file: Path to log file
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(pdf_basename)

    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)

    # Create log directory if it doesn't exist
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    # ✅ Use custom handler with immediate flush after every emit
    file_handler = ImmediateFlushFileHandler(log_file, encoding='utf-8', delay=False)
    file_handler.setLevel(logging.DEBUG)

    # ✅ Console handler for server-side feedback
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # ✅ Formatter with timestamp
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
