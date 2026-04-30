from alembic import command
from alembic.config import Config


class AlembicMigrator:
    def __init__(self, alembic_ini_path: str, database_url: str) -> None:
        self._alembic_ini_path = alembic_ini_path
        self._database_url = database_url

    def upgrade_head(self) -> None:
        alembic_cfg = Config(self._alembic_ini_path)
        alembic_cfg.set_main_option("sqlalchemy.url", self._database_url)
        command.upgrade(alembic_cfg, "head")
