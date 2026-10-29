from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]


def test_there_is_exactly_one_alembic_head():
    config = Config(str(ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    assert len(heads) == 1, heads
    assert script.get_revision("0001_baseline") is not None
    assert script.get_revision("0002_integrity") is not None


def test_test_database_is_at_the_latest_revision(db):
    config = Config(str(ROOT / "alembic.ini"))
    expected = ScriptDirectory.from_config(config).get_current_head()
    actual = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert actual == expected
