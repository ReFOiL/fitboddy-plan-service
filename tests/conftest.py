from pathlib import Path
import os
import sys

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[1]
LIB_DIR = ROOT / "lib"
sys.path.insert(0, str(LIB_DIR))

TEST_DB_PATH = ROOT / "plan_service_test.db"
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{TEST_DB_PATH.as_posix()}"
os.environ["ALEMBIC_INI_PATH"] = str((ROOT / "alembic.ini").resolve())
os.environ["REQUIRE_PROFILE_COMPLETION"] = "false"

alembic_cfg = Config(os.environ["ALEMBIC_INI_PATH"])
alembic_cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
command.upgrade(alembic_cfg, "head")
