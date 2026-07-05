"""SQLite pragma configuration."""

import sqlite3


def apply_pragmas(connection: sqlite3.Connection) -> None:
    """Apply SQLite pragma settings."""
    pragmas = [
        ("PRAGMA journal_mode = WAL;", None),
        ("PRAGMA busy_timeout = 30000;", None),
        ("PRAGMA synchronous = NORMAL;", None),
        ("PRAGMA foreign_keys = ON;", None),
        ("PRAGMA cache_size = -10000;", None),  # 10MB cache
    ]
    
    for pragma, args in pragmas:
        try:
            connection.execute(pragma)
        except sqlite3.OperationalError:
            pass  # Some pragmas might not be supported in all environments