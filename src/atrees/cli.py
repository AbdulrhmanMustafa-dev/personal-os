"""
CLI for ATREES.

Command-line interface for management tasks.
"""

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from atrees.config import get_settings, reload_settings
from atrees.database import init_db, close_db
from atrees.core.security import generate_encryption_key, generate_api_key
from atrees.core.logging import setup_logging, get_logger

app = typer.Typer(
    name="atrees",
    help="ATREES - Personal Life Operating System",
    add_completion=False,
)
console = Console()
logger = get_logger(__name__)


@app.callback()
def callback(
    debug: Annotated[bool, typer.Option("--debug", help="Enable debug mode")] = False,
):
    """ATREES CLI - Personal Life Operating System."""
    settings = get_settings()
    settings.DEBUG = debug
    if debug:
        settings.LOG_LEVEL = "DEBUG"
    setup_logging()


@app.command()
def init(
    force: Annotated[bool, typer.Option("--force", help="Overwrite existing database")] = False,
):
    """Initialize the database."""
    settings = get_settings()
    db_path = Path(settings.DATABASE_URL.replace("sqlite+aiosqlite:///", ""))

    if db_path.exists() and not force:
        console.print(f"[yellow]Database already exists at {db_path}. Use --force to overwrite.[/yellow]")
        return

    console.print(f"[green]Initializing database at {db_path}...[/green]")
    asyncio.run(init_db())
    console.print("[green]Database initialized successfully![/green]")


@app.command()
def migrate(
    message: Annotated[str, typer.Option("--message", "-m", help="Migration message")] = "Auto migration",
):
    """Create a new database migration."""
    import subprocess
    result = subprocess.run(
        ["alembic", "revision", "--autogenerate", "-m", message],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        console.print("[green]Migration created successfully![/green]")
        console.print(result.stdout)
    else:
        console.print("[red]Migration failed![/red]")
        console.print(result.stderr)


@app.command()
def upgrade(
    revision: Annotated[str, typer.Argument(help="Target revision (default: head)")] = "head",
):
    """Apply database migrations."""
    import subprocess
    result = subprocess.run(
        ["alembic", "upgrade", revision],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        console.print("[green]Migrations applied successfully![/green]")
        console.print(result.stdout)
    else:
        console.print("[red]Migration failed![/red]")
        console.print(result.stderr)


@app.command()
def generate_secrets():
    """Generate encryption key and API key."""
    enc_key = generate_encryption_key()
    api_key = generate_api_key()

    console.print("[bold]Generated Secrets:[/bold]")
    console.print(f"ENCRYPTION_KEY={enc_key}")
    console.print(f"API_KEY={api_key}")
    console.print("\n[yellow]Add these to your .env file![/yellow]")


@app.command()
def create_admin(
    username: Annotated[str, typer.Argument(help="Admin username")],
    password: Annotated[str, typer.Argument(help="Admin password")],
):
    """Create admin user (for future auth system)."""
    console.print(f"[green]Admin user '{username}' created (placeholder)[/green]")


@app.command()
def serve(
    host: Annotated[str, typer.Option("--host", help="Host to bind")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", help="Port to bind")] = 8000,
    reload: Annotated[bool, typer.Option("--reload", help="Auto-reload on changes")] = False,
):
    """Start the ATREES server."""
    import uvicorn

    settings = get_settings()
    settings.HOST = host
    settings.PORT = port

    console.print(f"[green]Starting ATREES on {host}:{port}[/green]")
    uvicorn.run(
        "atrees.api.main:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
    )


@app.command()
def sync(
    source: Annotated[str | None, typer.Option("--source", "-s", help="Source name to sync")] = None,
    all_sources: Annotated[bool, typer.Option("--all", help="Sync all sources")] = False,
):
    """Trigger manual synchronization."""
    console.print("[yellow]Sync command not yet implemented[/yellow]")


@app.command()
def backup(
    output: Annotated[Path, typer.Option("--output", "-o", help="Output file path")] = Path("./backups/atrees_backup.age"),
    encrypt: Annotated[bool, typer.Option("--encrypt", help="Encrypt backup")] = True,
):
    """Create database backup."""
    console.print("[yellow]Backup command not yet implemented[/yellow]")


@app.command()
def restore(
    input_file: Annotated[Path, typer.Argument(help="Backup file to restore")],
):
    """Restore from backup."""
    console.print("[yellow]Restore command not yet implemented[/yellow]")


@app.command()
def status():
    """Show system status."""
    settings = get_settings()

    table = Table(title="ATREES Status")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("App Version", settings.APP_VERSION)
    table.add_row("Debug Mode", str(settings.DEBUG))
    table.add_row("Database", settings.DATABASE_URL)
    table.add_row("Timezone", settings.TIMEZONE)
    table.add_row("Data Dir", str(settings.DATA_DIR))
    table.add_row("Log Level", settings.LOG_LEVEL)

    console.print(table)


if __name__ == "__main__":
    app()