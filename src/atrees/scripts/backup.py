"""
Backup script for ATREES.

Creates encrypted backups of the database.
"""

import asyncio
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from atrees.config import get_settings
from atrees.core.logging import setup_logging, get_logger
from atrees.core.security import EncryptionManager

logger = get_logger(__name__)


async def _async_main() -> None:
    """Create database backup."""
    import argparse

    parser = argparse.ArgumentParser(description="Create ATREES database backup")
    parser.add_argument("--output", "-o", type=Path, help="Output file path")
    parser.add_argument("--encrypt", action="store_true", default=True, help="Encrypt backup")
    parser.add_argument("--passphrase", help="Encryption passphrase (for age)")
    args = parser.parse_args()

    settings = get_settings()
    setup_logging()

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = settings.BACKUP_DIR / f"atrees_backup_{timestamp}.age"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Get database path
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite"):
        db_path = db_url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
    else:
        logger.error("backup_only_supported_for_sqlite")
        sys.exit(1)

    db_file = Path(db_path)
    if not db_file.exists():
        logger.error("database_file_not_found", path=str(db_file))
        sys.exit(1)

    logger.info("creating_backup", output=str(output_path))

    try:
        if args.encrypt:
            # Use age for encryption
            passphrase = args.passphrase or settings.privacy.BACKUP_PASSPHRASE
            if not passphrase:
                logger.error("no_passphrase_provided")
                sys.exit(1)

            # Create backup with age encryption
            cmd = ["age", "-p", "-e", "-o", str(output_path), str(db_file)]
            env = {"AGE_PASSPHRASE": passphrase.get_secret_value() if hasattr(passphrase, 'get_secret_value') else passphrase}
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error("age_encryption_failed", error=result.stderr)
                sys.exit(1)
        else:
            # Simple copy
            import shutil
            shutil.copy2(db_file, output_path)

        logger.info("backup_created_successfully", output=str(output_path), size=output_path.stat().st_size)
        print(f"Backup created: {output_path}")

    except Exception as e:
        logger.error("backup_failed", error=str(e))
        sys.exit(1)


def main() -> None:
    """Synchronous console-script entry point."""
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()