from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from alembic import command
from app.core import config as config_module


def test_migration_history_has_single_head() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(backend_root / "alembic.ini")
    scripts = ScriptDirectory.from_config(config)

    assert scripts.get_heads() == ["20260715_01"]
    assert scripts.get_bases() == ["20260715_01"]
    assert [revision.revision for revision in scripts.walk_revisions()] == ["20260715_01"]


def test_full_migration_history_compiles_for_postgresql_offline(tmp_path, monkeypatch, capsys) -> None:
    backend_root = Path(__file__).resolve().parents[2]
    monkeypatch.setattr(config_module, "BACKEND_ENV_FILE", tmp_path / "missing.env")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://migration-test.invalid/family_hub")
    config = Config(backend_root / "alembic.ini")

    command.upgrade(config, "head", sql=True)

    sql = capsys.readouterr().out
    assert "CREATE TABLE photos" in sql
    assert "fk_albums_cover_album_photos" in sql
    assert "CREATE TABLE photo_activity_events" in sql
    assert "CREATE TABLE notification_deliveries" in sql
    assert "CREATE TABLE administrative_audit_events" in sql
    assert "uq_family_groups_name" in sql
