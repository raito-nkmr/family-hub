import json
from pathlib import Path
from unittest.mock import Mock

from app.commands.check_photo_integrity import check_photo_integrity
from app.features.photos.registration import build_sidecar_metadata
from app.features.photos.storage import DerivativeNotFoundError
from tests.features.photos.factories import make_photo


def _write_photo_files(storage_root: Path, derivative_root: Path, photo: object) -> tuple[Path, Path, Path]:
    original_path = storage_root / photo.storage_key
    original_path.parent.mkdir(parents=True)
    original_path.write_bytes(b"photo-data")
    photo.size_bytes = original_path.stat().st_size
    photo.sha256 = "00" * 32

    derivative = photo.derivatives[0]
    derivative_path = derivative_root / derivative.storage_key
    derivative_path.parent.mkdir(parents=True)
    derivative_path.write_bytes(b"thumbnail")
    derivative.size_bytes = derivative_path.stat().st_size
    sidecar_path = original_path.with_suffix(".json")
    sidecar_path.write_text(json.dumps(build_sidecar_metadata(photo).as_json()), encoding="utf-8")
    return original_path, sidecar_path, derivative_path


def test_check_photo_integrity_reports_clean_files(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    derivative_root = tmp_path / "derivatives"
    photo = make_photo()
    original_path, _, derivative_path = _write_photo_files(storage_root, derivative_root, photo)
    session = Mock()
    session.scalars.return_value.all.return_value = [photo]
    storage = Mock()
    storage.get_original_path.return_value = original_path
    storage.get_derivative_path.return_value = derivative_path

    report = check_photo_integrity(session, storage, storage_root, derivative_root)

    assert report.clean
    assert report.checked_photos == 1
    assert report.checked_derivatives == 1


def test_check_photo_integrity_reports_missing_mismatched_and_orphan_files(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    derivative_root = tmp_path / "derivatives"
    photo = make_photo()
    original_path, sidecar_path, derivative_path = _write_photo_files(storage_root, derivative_root, photo)
    sidecar_path.write_text("{}", encoding="utf-8")
    orphan = storage_root / "originals" / "orphan.jpg"
    orphan.write_bytes(b"orphan")
    session = Mock()
    session.scalars.return_value.all.return_value = [photo]
    storage = Mock()
    storage.get_original_path.return_value = original_path
    storage.get_derivative_path.side_effect = DerivativeNotFoundError
    derivative_path.unlink()

    report = check_photo_integrity(session, storage, storage_root, derivative_root)

    assert {issue.code for issue in report.issues} == {
        "derivative_missing",
        "orphan_original",
        "sidecar_mismatch",
    }


def test_check_photo_integrity_verifies_hashes_only_when_requested(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    derivative_root = tmp_path / "derivatives"
    photo = make_photo()
    original_path, _, derivative_path = _write_photo_files(storage_root, derivative_root, photo)
    session = Mock()
    session.scalars.return_value.all.return_value = [photo]
    storage = Mock()
    storage.get_original_path.return_value = original_path
    storage.get_derivative_path.return_value = derivative_path

    normal_report = check_photo_integrity(session, storage, storage_root, derivative_root)
    hash_report = check_photo_integrity(
        session,
        storage,
        storage_root,
        derivative_root,
        verify_hashes=True,
    )

    assert normal_report.clean
    assert [issue.code for issue in hash_report.issues] == ["original_hash_mismatch"]


def test_check_photo_integrity_reports_orphan_incoming_parts(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    derivative_root = tmp_path / "derivatives"
    storage_part = storage_root / "incoming" / "orphan.part"
    derivative_part = derivative_root / "incoming" / "orphan.thumbnail.part"
    storage_part.parent.mkdir(parents=True)
    derivative_part.parent.mkdir(parents=True)
    storage_part.write_bytes(b"partial original")
    derivative_part.write_bytes(b"partial thumbnail")
    session = Mock()
    session.scalars.return_value.all.return_value = []

    report = check_photo_integrity(session, Mock(), storage_root, derivative_root)

    assert [(issue.code, issue.path) for issue in report.issues] == [
        ("orphan_part", str(derivative_part)),
        ("orphan_part", str(storage_part)),
    ]
