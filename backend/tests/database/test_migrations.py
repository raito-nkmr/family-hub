import os
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from alembic import command
from app.core import config as config_module


def test_migration_history_has_single_head() -> None:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(backend_root / "alembic.ini")
    scripts = ScriptDirectory.from_config(config)

    assert scripts.get_heads() == ["20260820_01"]
    assert scripts.get_bases() == ["20260715_01"]
    assert [revision.revision for revision in scripts.walk_revisions()] == [
        "20260820_01",
        "20260818_02",
        "20260818_01",
        "20260715_01",
    ]


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
    assert "ADD COLUMN must_change_password BOOLEAN DEFAULT false NOT NULL" in sql
    assert "fk_push_subscriptions_user_session_user_id_user_sessions" in sql
    assert "ALTER TABLE photos ALTER COLUMN width SET NOT NULL" in sql
    assert "ALTER TABLE photos ALTER COLUMN height SET NOT NULL" in sql


def test_full_migration_history_downgrade_compiles_for_postgresql_offline(tmp_path, monkeypatch, capsys) -> None:
    backend_root = Path(__file__).resolve().parents[2]
    monkeypatch.setattr(config_module, "BACKEND_ENV_FILE", tmp_path / "missing.env")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://migration-test.invalid/family_hub")
    config = Config(backend_root / "alembic.ini")

    command.downgrade(config, "head:base", sql=True)

    sql = capsys.readouterr().out
    assert "ALTER TABLE album_photos DROP CONSTRAINT fk_album_photos_photo_id_photos" in sql
    assert "ALTER TABLE albums DROP CONSTRAINT fk_albums_cover_album_photos" in sql
    assert "DROP TABLE album_photos" in sql
    assert "DROP TABLE photos" in sql


MIGRATION_TEST_DATABASE_URL = os.getenv("MIGRATION_TEST_DATABASE_URL")


@pytest.mark.integration
@pytest.mark.skipif(
    MIGRATION_TEST_DATABASE_URL is None,
    reason="MIGRATION_TEST_DATABASE_URL is not configured",
)
def test_upgrade_head_then_downgrade_base_on_postgresql(monkeypatch) -> None:
    assert MIGRATION_TEST_DATABASE_URL is not None
    backend_root = Path(__file__).resolve().parents[2]
    monkeypatch.setenv("DATABASE_URL", MIGRATION_TEST_DATABASE_URL)
    config = Config(backend_root / "alembic.ini")

    command.upgrade(config, "head")
    command.downgrade(config, "base")
