"""Compare the DB's applied Alembic revision(s) against the repo's migration heads.

Used by /health so a deployment is never reported ready before its own
migrations have actually been applied (Slice 7 contract §6.1).
"""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import Connection

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def get_head_revisions() -> set[str]:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    script = ScriptDirectory.from_config(config)
    return set(script.get_heads())


def get_current_db_revisions(connection: Connection) -> set[str]:
    try:
        rows = connection.execute(text("SELECT version_num FROM alembic_version")).fetchall()
    except Exception:
        # alembic_version does not exist yet — migrations have never run.
        return set()
    return {row[0] for row in rows}
