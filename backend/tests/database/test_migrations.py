import os
import re
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

    assert scripts.get_heads() == ["20260821_03_household"]
    assert scripts.get_bases() == ["20260821_01_core"]
    assert [revision.revision for revision in scripts.walk_revisions()] == [
        "20260821_03_household",
        "20260821_02_media",
        "20260821_01_core",
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
    assert "must_change_password BOOLEAN DEFAULT 'false' NOT NULL" in sql
    assert "fk_push_subscriptions_user_session_user_id_user_sessions" in sql
    assert "width INTEGER NOT NULL" in sql
    assert "height INTEGER NOT NULL" in sql
    assert "captured_at_original TIMESTAMP WITH TIME ZONE" in sql
    assert "effective_captured_at TIMESTAMP WITH TIME ZONE" in sql
    assert "ix_photos_sort_date_id" in sql
    assert "effective_captured_at TIMESTAMP WITH TIME ZONE NOT NULL" in sql
    assert "activity_operation_id UUID NOT NULL" in sql
    assert "ix_photo_activity_events_activity_operation_id" in sql
    assert "CREATE TABLE chore_categories" in sql
    assert "CREATE TABLE chore_tasks" in sql
    assert "CREATE TABLE chore_completions" in sql
    assert "category_id UUID NOT NULL" in sql
    assert "uq_chore_categories_group_name_ci" in sql
    assert "fk_chore_tasks_category_id_chore_categories" in sql
    assert "timezone VARCHAR(64) DEFAULT 'Asia/Tokyo' NOT NULL" in sql
    assert "task_name VARCHAR(120) NOT NULL" in sql
    assert "ck_chore_tasks_task_name_length" in sql
    assert "last_used_at TIMESTAMP WITH TIME ZONE NOT NULL" in sql
    assert "invitee_user_id UUID NOT NULL" in sql
    assert "invited_by_user_id UUID NOT NULL" in sql
    assert "pk_family_group_membership_invitations" in sql
    assert "task_name_snapshot VARCHAR(120) NOT NULL" in sql
    assert "category_name_snapshot VARCHAR(40) NOT NULL" in sql
    assert "ix_chore_completions_completed_at_task_id" in sql
    assert "sort_order INTEGER DEFAULT 0 NOT NULL" in sql
    assert "ix_chore_categories_group_sort_order" in sql
    assert "ck_chore_tasks_category" not in sql
    assert "ALTER TABLE chore_completions ADD COLUMN task_name_snapshot" not in sql
    assert re.search(r"\b(?:INSERT INTO|UPDATE|DELETE FROM)\s+(?!alembic_version\b)", sql, re.IGNORECASE) is None


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
    assert "DROP TABLE chore_categories" in sql
    assert "DROP COLUMN timezone" in sql


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
