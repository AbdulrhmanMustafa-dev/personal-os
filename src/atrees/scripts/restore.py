"""
Restore script for ATREES.

Restores database from encrypted backup.
"""

import asyncio
import subprocess
import sys
from pathlib import Path

from atrees.config import get_settings
from atrees.core.logging import setup_logging, get_logger

logger = get_logger(__name__)


async def _async_main() -> None:
    """Restore database from backup."""
    import argparse

    parser = argparse.ArgumentParser(description="Restore ATREES database from backup")
    parser.add_argument("input_file", type=Path, help="Backup file to restore")
    parser.add_argument("--passphrase", help="Decryption passphrase (for age)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing database")
    args = parser.parse_args()

    settings = get_settings()
    setup_logging()

    input_path = args.input_file
    if not input_path.exists():
        logger.error("backup_file_not_found", path=str(input_path))
        sys.exit(1)

    # Get database path
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite"):
        db_path = db_url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
    else:
        logger.error("restore_only_supported_for_sqlite")
        sys.exit(1)

    db_file = Path(db_path)

    if db_file.exists() and not args.force:
        logger.error("database_exists_use_force", path=str(db_file))
        sys.exit(1)

    logger.info("restoring_backup", input=str(input_path), output=str(db_file))

    try:
        # Check if encrypted with age
        if input_path.suffix == ".age":
            passphrase = args.passphrase or settings.privacy.BACKUP_PASSPHRASE
            if not passphrase:
                logger.error("no_passphrase_provided")
                sys.exit(1)

            # Decrypt with age
            cmd = ["age", "-d", "-o", str(db_file), str(input_path)]
            env = {"AGE_PASSPHRASE": passphrase.get_secret_value() if hasattr(passphrase, 'get_secret_value') else passphrase}
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error("age_decryption_failed", error=result.stderr)
                sys.exit(1)
        else:
            # Simple copy
            import shutil
            shutil.copy2(input_path, db_file)

        logger.info("restore_completed_successfully", output=str(db_file))
        print(f"Database restored: {db_file}")

    except Exception as e:
        logger.error("restore_failed", error=str(e))
        sys.exit(1)


def main() -> None:
    """Synchronous console-script entry point."""
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()