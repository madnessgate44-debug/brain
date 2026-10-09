"""Runtime secret/config lookup without overriding real environment variables."""

import os
from functools import lru_cache
from dotenv import dotenv_values


@lru_cache(maxsize=1)
def _dotenv() -> dict[str, str | None]:
    """Read local .env values once; deployment environment always takes precedence."""
    return dotenv_values(".env")


def get_setting(name: str, default: str = "") -> str:
    """Read a setting from the process environment, then local .env, then default."""
    value = os.getenv(name)
    if value is None:
        value = _dotenv().get(name)
    return value if isinstance(value, str) and value else default
