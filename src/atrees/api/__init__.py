"""
API layer for ATREES.

FastAPI application with routes for dashboard, connectors, tasks, and more.
"""

from atrees.api.main import create_app

__all__ = ["create_app"]