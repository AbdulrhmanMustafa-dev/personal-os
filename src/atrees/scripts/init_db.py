"""Initialize the versioned database schema and default preferences."""

import asyncio
import subprocess
import sys
from pathlib import Path

from sqlalchemy import select

from atrees.core.logging import get_logger, setup_logging
from atrees.database import get_session
from atrees.models.preferences import DEFAULT_PREFERENCES, UserPreference

logger = get_logger(__name__)


async def _insert_default_preferences() -> None:
    async with get_session() as db:
        for pref_data in DEFAULT_PREFERENCES:
            result = await db.execute(select(UserPreference).where(UserPreference.key == pref_data["key"]))
            if result.scalar_one_or_none() is None:
                db.add(UserPreference(**pref_data))
        await db.commit()


def main() -> None:
    """Apply Alembic migrations, then insert defaults (safe console entry point)."""
    setup_logging()
    project_root = Path(__file__).resolve().parents[3]
    logger.info("applying_database_migrations", project_root=str(project_root))
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=project_root,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(result.returncode)
    asyncio.run(_insert_default_preferences())
    logger.info("database_initialization_complete")


if __name__ == "__main__":
    main()
