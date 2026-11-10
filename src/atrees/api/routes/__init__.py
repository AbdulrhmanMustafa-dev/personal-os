"""
API routes for ATREES.
"""

from atrees.api.routes import health, connectors, tasks, dashboard, sources, notifications

__all__ = ["health", "connectors", "tasks", "dashboard", "sources", "notifications"]