"""Command-line interface for Brain."""

import sys
import argparse
import asyncio
from pathlib import Path

from brain.core.config import load_config
from brain.core.logging import setup_logging
from brain.db.session import DatabaseSessionManager
from brain.services.boot_service import BootService


def main() -> None:
    """Entry point for CLI."""
    parser = argparse.ArgumentParser(description="Brain V1")
    parser.add_argument("--version", action="store_true", help="Show version")
    parser.add_argument("--serve", action="store_true", help="Start the server")
    
    args = parser.parse_args()
    
    if args.version:
        from brain import __version__
        print(f"Brain V1 {__version__}")
        return
    
    if args.serve:
        # Start the server
        import uvicorn
        uvicorn.run(
            "brain.api.app:create_app",
            host="0.0.0.0",
            port=8000,
            reload=True,
        )
        return
    
    # Default: show help
    parser.print_help()


if __name__ == "__main__":
    main()