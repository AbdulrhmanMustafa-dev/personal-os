"""
Development server script for ATREES.

Runs the FastAPI server with auto-reload.
"""

import uvicorn
from atrees.config import get_settings
from atrees.core.logging import setup_logging

def main() -> None:
    """Run development server."""
    settings = get_settings()
    settings.DEBUG = True
    settings.LOG_LEVEL = "DEBUG"
    setup_logging()

    uvicorn.run(
        "atrees.api.main:create_app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        factory=True,
        log_level="debug",
    )


if __name__ == "__main__":
    main()