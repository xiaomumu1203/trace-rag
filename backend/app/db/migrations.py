
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import settings


def run_migrations() -> None:

    backend_dir = Path(__file__).resolve().parents[2]
    config = Config(str(backend_dir / "alembic.ini"))
    config.set_main_option(
        "sqlalchemy.url",
        settings.get_mysql_url().render_as_string(hide_password=False),
    )
    command.upgrade(config, "head")
