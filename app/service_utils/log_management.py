"""
Centralized logging management for the application.
Creates daily log files in the logs directory.
"""
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from pathlib import Path


# Create logs directory if it doesn't exist
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)


def setup_logger(name: str = None, level: int = logging.INFO) -> logging.Logger:
    """
    Set up a logger with both file and console handlers.
    Creates a new log file daily in the format: YYYY-MM-DD.log
    
    Args:
        name: Logger name (usually __name__ from the calling module)
        level: Logging level (default: INFO)
        
    Returns:
        Configured logger instance
    """
    # Use root logger if no name provided
    logger_name = name if name else 'lot21_backend'
    logger = logging.getLogger(logger_name)
    
    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(level)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # File handler - rotates daily at midnight
        log_file = LOGS_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log"
        file_handler = TimedRotatingFileHandler(
            filename=log_file,
            when='midnight',
            interval=1,
            backupCount=30,  # Keep 30 days of logs
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        file_handler.suffix = "%Y-%m-%d"  # Suffix for rotated files
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        
        # Add handlers to logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        # Prevent propagation to root logger to avoid duplicate logs
        logger.propagate = False
    
    return logger


def get_logger(name: str = None) -> logging.Logger:
    """
    Get a logger instance. If already configured, returns existing logger.
    Otherwise, configures a new logger.
    
    Args:
        name: Logger name (usually __name__ from the calling module)
        
    Returns:
        Logger instance
    """
    return setup_logger(name)


# Configure root logger on module import
setup_logger()
