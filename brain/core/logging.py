"""Structured logging configuration."""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from brain.core.config import Config


class StructuredFormatter(logging.Formatter):
    """Structured JSON-like formatter."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured output."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields
        if hasattr(record, "instance_id"):
            log_data["instance_id"] = record.instance_id
        if hasattr(record, "mission_id"):
            log_data["mission_id"] = record.mission_id
        if hasattr(record, "approval_id"):
            log_data["approval_id"] = record.approval_id
        if hasattr(record, "event_type"):
            log_data["event_type"] = record.event_type
        
        # Add exception info
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return str(log_data)


def setup_logging(config: Config) -> None:
    """Setup logging configuration."""
    log_config = config.logging
    
    # Create logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_config.log_level.upper(), logging.INFO))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    if log_config.structured:
        console_handler.setFormatter(StructuredFormatter())
    else:
        console_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ))
    root_logger.addHandler(console_handler)
    
    # File handler
    if log_config.log_file:
        file_path = Path(log_config.log_file)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(file_path)
        if log_config.structured:
            file_handler.setFormatter(StructuredFormatter())
        else:
            file_handler.setFormatter(logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            ))
        root_logger.addHandler(file_handler)
    
    # Set SQLAlchemy logging level
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.INFO)
    
    # Log startup
    logger = logging.getLogger("brain.core.logging")
    logger.info("Logging configured", extra={
        "instance_id": config.system.instance_id,
        "log_level": log_config.log_level,
        "structured": log_config.structured,
    })