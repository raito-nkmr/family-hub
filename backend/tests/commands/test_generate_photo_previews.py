from pathlib import Path
from unittest.mock import MagicMock

from app.commands.generate_photo_previews import generate_photo_previews
from app.features.photos.models import PhotoDerivative, PhotoDerivativeKind
from app.features.photos.storage.facade import PhotoStorage, PhotoStorageError
from app.features.photos.storage.types import StagedDerivative
from tests.features.photos.factories import make_photo


def test_generate_photo_previews_creates_missing_preview_and_updates_sidecar(tmp_path: Path) -> None:
    photo = make_photo()
    session = MagicMock()
    session.scalars.return_value.all.return_value = [photo]
    storage = MagicMock(spec=PhotoStorage)
    staged = StagedDerivative(
        path=tmp_path / "incoming" / "preview.part",
        storage_key=f"previews/2026/07/{photo.id}.webp",
        content_type="image/webp",
        width=1600,
        height=1200,
        size_bytes=48_000,
    )
    destination = tmp_path / "previews" / "2026" / "07" / f"{photo.id}.webp"
    storage.stage_preview.return_value = staged
    storage.finalize_staged_derivative.return_value = destination

    report = generate_photo_previews(session, storage)

    assert report.checked_photos == 1
    assert report.generated_previews == 1
    assert report.skipped_previews == 0
    assert report.failures == ()
    preview = photo.get_derivative(PhotoDerivativeKind.PREVIEW)
    assert preview is not None
    assert preview.storage_key == staged.storage_key
    assert preview.width == staged.width
    storage.update_sidecar.assert_called_once()
    sidecar = storage.update_sidecar.call_args.args[0]
    assert any(item["kind"] == "preview" for item in sidecar.derivatives)
    session.commit.assert_called_once_with()


def test_generate_photo_previews_skips_existing_file(tmp_path: Path) -> None:
    photo = make_photo()
    preview = PhotoDerivative(
        id=photo.id,
        photo_id=photo.id,
        kind=PhotoDerivativeKind.PREVIEW,
        storage_key=f"previews/2026/07/{photo.id}.webp",
        content_type="image/webp",
        width=1600,
        height=1200,
        size_bytes=48_000,
        created_at=photo.uploaded_at,
    )
    photo.derivatives.append(preview)
    session = MagicMock()
    session.scalars.return_value.all.return_value = [photo]
    storage = MagicMock(spec=PhotoStorage)
    storage.get_derivative_path.return_value = tmp_path / "preview.webp"

    report = generate_photo_previews(session, storage)

    assert report.generated_previews == 0
    assert report.skipped_previews == 1
    assert report.failures == ()
    storage.stage_preview.assert_not_called()
    session.commit.assert_not_called()


def test_generate_photo_previews_reports_failure_and_rolls_back(tmp_path: Path) -> None:
    photo = make_photo()
    session = MagicMock()
    session.scalars.return_value.all.return_value = [photo]
    storage = MagicMock(spec=PhotoStorage)
    storage.stage_preview.side_effect = PhotoStorageError("preview generation failed")

    report = generate_photo_previews(session, storage)

    assert report.generated_previews == 0
    assert report.skipped_previews == 0
    assert report.failures == (f"{photo.id}:PhotoStorageError",)
    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()
