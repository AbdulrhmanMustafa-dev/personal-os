"""
Database migration script for ATREES.

Runs Alembic migrations programmatically.
"""

import asyncio
import subprocess
import sys
from pathlib import Path

from atrees.core.logging import setup_logging, get_logger

logger = get_logger(__name__)


def main() -> None:
    """Run database migrations."""
    setup_logging()
    logger.info("running_migrations")

    # Get project root (where alembic.ini is)
    project_root = Path(__file__).parent.parent.parent.parent

    # Run alembic upgrade
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        logger.info("migrations_applied_successfully")
        print(result.stdout)
    else:
        logger.error("migrations_failed", error=result.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()