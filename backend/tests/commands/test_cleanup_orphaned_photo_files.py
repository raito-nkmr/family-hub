import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

from app.commands.cleanup_orphaned_photo_files import cleanup_orphaned_photo_files


def _empty_database_session() -> Mock:
    session = Mock()
    session.scalars.return_value.all.return_value = []
    return session


def _write_orphan_files(storage_root: Path, derivative_root: Path) -> tuple[Path, Path]:
    original = storage_root / "originals" / "2026" / "08" / "orphan.jpg"
    derivative = derivative_root / "thumbnails" / "2026" / "08" / "orphan.webp"
    original.parent.mkdir(parents=True)
    derivative.parent.mkdir(parents=True)
    original.write_bytes(b"orphan original")
    derivative.write_bytes(b"orphan derivative")
    return original, derivative


def test_cleanup_orphaned_photo_files_requires_explicit_empty_database_permission(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    derivative_root = tmp_path / "derivatives"
    original, derivative = _write_orphan_files(storage_root, derivative_root)
    now = datetime(2026, 8, 22, 12, tzinfo=UTC)
    old_timestamp = (now - timedelta(days=2)).timestamp()
    os.utime(original, (old_timestamp, old_timestamp))
    os.utime(derivative, (old_timestamp, old_timestamp))

    report = cleanup_orphaned_photo_files(
        _empty_database_session(),
        Mock(),
        storage_root,
        derivative_root,
        apply=True,
        now=now,
    )

    assert report.blocked_reason is not None
    assert report.removed == ()
    assert original.exists()
    assert derivative.exists()


def test_cleanup_orphaned_photo_files_removes_old_files_and_keeps_recent_files(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    derivative_root = tmp_path / "derivatives"
    original, derivative = _write_orphan_files(storage_root, derivative_root)
    storage_part = storage_root / "incoming" / "orphan.part"
    derivative_part = derivative_root / "incoming" / "orphan.thumbnail.part"
    storage_part.parent.mkdir(parents=True)
    derivative_part.parent.mkdir(parents=True)
    storage_part.write_bytes(b"orphan upload")
    derivative_part.write_bytes(b"orphan thumbnail")
    recent = storage_root / "originals" / "2026" / "08" / "recent.jpg"
    recent.write_bytes(b"recent orphan")
    now = datetime(2026, 8, 22, 12, tzinfo=UTC)
    old_timestamp = (now - timedelta(days=2)).timestamp()
    recent_timestamp = (now - timedelta(hours=1)).timestamp()
    os.utime(original, (old_timestamp, old_timestamp))
    os.utime(derivative, (old_timestamp, old_timestamp))
    os.utime(storage_part, (old_timestamp, old_timestamp))
    os.utime(derivative_part, (old_timestamp, old_timestamp))
    os.utime(recent, (recent_timestamp, recent_timestamp))

    report = cleanup_orphaned_photo_files(
        _empty_database_session(),
        Mock(),
        storage_root,
        derivative_root,
        apply=True,
        allow_empty_database=True,
        now=now,
    )

    assert {candidate.path for candidate in report.removed} == {
        original,
        derivative,
        storage_part,
        derivative_part,
    }
    assert {candidate.path for candidate in report.skipped_recent} == {recent}
    assert not original.exists()
    assert not derivative.exists()
    assert not storage_part.exists()
    assert not derivative_part.exists()
    assert recent.exists()


def test_cleanup_orphaned_photo_files_dry_run_does_not_delete_files(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    derivative_root = tmp_path / "derivatives"
    original, derivative = _write_orphan_files(storage_root, derivative_root)
    now = datetime(2026, 8, 22, 12, tzinfo=UTC)
    old_timestamp = (now - timedelta(days=2)).timestamp()
    os.utime(original, (old_timestamp, old_timestamp))
    os.utime(derivative, (old_timestamp, old_timestamp))

    report = cleanup_orphaned_photo_files(
        _empty_database_session(),
        Mock(),
        storage_root,
        derivative_root,
        now=now,
    )

    assert len(report.eligible_candidates) == 2
    assert report.removed == ()
    assert original.exists()
    assert derivative.exists()
