import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from PIL import Image

from app.core.config import Settings
from app.features.photos import storage as storage_module
from app.features.photos.storage import (
    FinalizedUpload,
    InvalidStorageKeyError,
    OriginalNotFoundError,
    PhotoStorage,
    PhotoStorageError,
    SidecarMetadata,
    StagedDerivative,
    StorageStatusCode,
    StorageUnavailableError,
    UploadOffsetMismatchError,
)

EXPECTED_MARKER = "test-storage-marker"
MINIMUM_FREE_BYTES = 1_024
MAXIMUM_UPLOAD_BYTES = 1_024


def make_settings(
    root: Path | None,
    *,
    maximum_upload_bytes: int = MAXIMUM_UPLOAD_BYTES,
    chunk_bytes: int = 3,
) -> Settings:
    return Settings(
        photo_storage_root=root,
        photo_derivative_root=(root / "derivatives" if root is not None else tmp_path_placeholder()),
        photo_storage_marker=EXPECTED_MARKER,
        photo_max_upload_bytes=maximum_upload_bytes,
        photo_min_free_bytes=MINIMUM_FREE_BYTES,
        photo_upload_chunk_bytes=chunk_bytes,
    )


def tmp_path_placeholder() -> Path:
    return Path("/tmp/photo-derivatives-not-used")


def write_marker(root: Path, marker: str = EXPECTED_MARKER) -> None:
    (root / storage_module.STORAGE_MARKER_FILENAME).write_text(marker, encoding="utf-8")


def test_storage_is_not_configured_without_root() -> None:
    status = PhotoStorage(make_settings(None)).get_status()

    assert status.status is StorageStatusCode.NOT_CONFIGURED
    assert status.available is False


def test_storage_rejects_non_mount_point(tmp_path: Path) -> None:
    write_marker(tmp_path)

    status = PhotoStorage(make_settings(tmp_path)).get_status()

    assert status.status is StorageStatusCode.NOT_MOUNT_POINT


def test_mount_point_check_detects_bind_mount_from_linux_mountinfo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mountinfo_path = tmp_path / "mountinfo"
    mount_path = tmp_path / "bind-mount"
    mount_path.mkdir()
    mountinfo_path.write_text(
        f"49 48 259:2 /source/path {mount_path} rw,nosuid - ext4 /dev/nvme0n1p2 rw\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(storage_module, "LINUX_MOUNTINFO_PATH", mountinfo_path)

    assert storage_module._is_mount_point(mount_path) is True


def test_mount_point_check_decodes_escaped_mountinfo_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mountinfo_path = tmp_path / "mountinfo"
    mount_path = tmp_path / "bind mount"
    mount_path.mkdir()
    escaped_path = str(mount_path).replace(" ", r"\040")
    mountinfo_path.write_text(
        f"49 48 259:2 /source/path {escaped_path} rw,nosuid - ext4 /dev/nvme0n1p2 rw\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(storage_module, "LINUX_MOUNTINFO_PATH", mountinfo_path)

    assert storage_module._is_mount_point(mount_path) is True


def test_mount_point_check_rejects_path_missing_from_linux_mountinfo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mountinfo_path = tmp_path / "mountinfo"
    mountinfo_path.write_text("", encoding="utf-8")
    monkeypatch.setattr(storage_module, "LINUX_MOUNTINFO_PATH", mountinfo_path)

    assert storage_module._is_mount_point(tmp_path) is False


def test_storage_requires_marker_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(storage_module, "_is_mount_point", lambda path: True)

    status = PhotoStorage(make_settings(tmp_path)).get_status()

    assert status.status is StorageStatusCode.MARKER_MISSING


def test_storage_rejects_symlinked_root(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    symlink = tmp_path / "storage-link"
    symlink.symlink_to(target, target_is_directory=True)

    status = PhotoStorage(make_settings(symlink)).get_status()

    assert status.status is StorageStatusCode.SYMLINK_NOT_ALLOWED


def test_storage_rejects_marker_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_marker(tmp_path, "different-marker")
    monkeypatch.setattr(storage_module, "_is_mount_point", lambda path: True)

    status = PhotoStorage(make_settings(tmp_path)).get_status()

    assert status.status is StorageStatusCode.MARKER_MISMATCH


def test_storage_rejects_read_only_mount(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_marker(tmp_path)
    monkeypatch.setattr(storage_module, "_is_mount_point", lambda path: True)
    monkeypatch.setattr(storage_module, "_is_read_only", lambda path: True)

    status = PhotoStorage(make_settings(tmp_path)).get_status()

    assert status.status is StorageStatusCode.READ_ONLY


def test_storage_rejects_non_writable_mount(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_marker(tmp_path)
    monkeypatch.setattr(storage_module, "_is_mount_point", lambda path: True)
    monkeypatch.setattr(storage_module, "_is_read_only", lambda path: False)
    monkeypatch.setattr(storage_module, "_is_writable", lambda path: False)

    status = PhotoStorage(make_settings(tmp_path)).get_status()

    assert status.status is StorageStatusCode.NOT_WRITABLE


@pytest.mark.parametrize("directory_name", ["originals", "incoming"])
def test_storage_rejects_non_writable_storage_directory(
    directory_name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_marker(tmp_path)
    directory = tmp_path / directory_name
    directory.mkdir()
    monkeypatch.setattr(storage_module, "_is_mount_point", lambda path: True)
    monkeypatch.setattr(storage_module, "_is_read_only", lambda path: False)
    monkeypatch.setattr(storage_module, "_is_writable", lambda path: path != directory)

    status = PhotoStorage(make_settings(tmp_path)).get_status()

    assert status.status is StorageStatusCode.NOT_WRITABLE


@pytest.mark.parametrize("directory_name", ["originals", "incoming"])
def test_storage_rejects_symlinked_storage_directory(
    directory_name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_marker(tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    (tmp_path / directory_name).symlink_to(target, target_is_directory=True)
    monkeypatch.setattr(storage_module, "_is_mount_point", lambda path: True)
    monkeypatch.setattr(storage_module, "_is_read_only", lambda path: False)
    monkeypatch.setattr(storage_module, "_is_writable", lambda path: True)

    status = PhotoStorage(make_settings(tmp_path)).get_status()

    assert status.status is StorageStatusCode.SYMLINK_NOT_ALLOWED


def test_storage_reports_insufficient_space(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_marker(tmp_path)
    monkeypatch.setattr(storage_module, "_is_mount_point", lambda path: True)
    monkeypatch.setattr(storage_module, "_is_read_only", lambda path: False)
    monkeypatch.setattr(storage_module, "_is_writable", lambda path: True)
    free_bytes = MINIMUM_FREE_BYTES + MAXIMUM_UPLOAD_BYTES - 1
    monkeypatch.setattr(storage_module, "_get_free_bytes", lambda path: free_bytes)

    status = PhotoStorage(make_settings(tmp_path)).get_status()

    assert status.status is StorageStatusCode.INSUFFICIENT_SPACE
    assert status.available is False
    assert status.writable is True
    assert status.free_bytes == free_bytes


def test_storage_is_available_when_all_checks_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_marker(tmp_path)
    monkeypatch.setattr(storage_module, "_is_mount_point", lambda path: True)
    monkeypatch.setattr(storage_module, "_is_read_only", lambda path: False)
    monkeypatch.setattr(storage_module, "_is_writable", lambda path: True)
    free_bytes = MINIMUM_FREE_BYTES + MAXIMUM_UPLOAD_BYTES
    monkeypatch.setattr(storage_module, "_get_free_bytes", lambda path: free_bytes)

    status = PhotoStorage(make_settings(tmp_path)).get_status()

    assert status.status is StorageStatusCode.AVAILABLE
    assert status.available is True
    assert status.writable is True
    assert status.free_bytes == free_bytes


def make_available_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PhotoStorage:
    write_marker(tmp_path)
    monkeypatch.setattr(storage_module, "_is_mount_point", lambda path: True)
    monkeypatch.setattr(storage_module, "_is_read_only", lambda path: False)
    monkeypatch.setattr(storage_module, "_is_writable", lambda path: True)
    monkeypatch.setattr(
        storage_module,
        "_get_free_bytes",
        lambda path: MINIMUM_FREE_BYTES + MAXIMUM_UPLOAD_BYTES + 4_096,
    )
    return PhotoStorage(make_settings(tmp_path))


def test_get_original_path_returns_file_below_originals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = make_available_storage(tmp_path, monkeypatch)
    original = tmp_path / "originals" / "2026" / "07" / "photo.jpg"
    original.parent.mkdir(parents=True)
    original.write_bytes(b"photo")

    result = storage.get_original_path("originals/2026/07/photo.jpg")

    assert result == original


@pytest.mark.parametrize(
    ("read_only", "writable", "free_bytes"),
    [
        (True, True, MINIMUM_FREE_BYTES + MAXIMUM_UPLOAD_BYTES),
        (False, False, MINIMUM_FREE_BYTES + MAXIMUM_UPLOAD_BYTES),
        (False, True, MINIMUM_FREE_BYTES),
    ],
)
def test_get_original_path_remains_available_when_uploads_are_unavailable(
    read_only: bool,
    writable: bool,
    free_bytes: int,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = make_available_storage(tmp_path, monkeypatch)
    original = tmp_path / "originals" / "photo.jpg"
    original.parent.mkdir()
    original.write_bytes(b"photo")
    monkeypatch.setattr(storage_module, "_is_read_only", lambda path: read_only)
    monkeypatch.setattr(storage_module, "_is_writable", lambda path: writable)
    monkeypatch.setattr(storage_module, "_get_free_bytes", lambda path: free_bytes)

    assert storage.get_status().available is False
    assert storage.get_original_path("originals/photo.jpg") == original


@pytest.mark.parametrize(
    "storage_key",
    ["../photo.jpg", "originals/../../photo.jpg", "/originals/photo.jpg", "other/photo.jpg", r"originals\photo.jpg"],
)
def test_get_original_path_rejects_unsafe_keys(
    storage_key: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = make_available_storage(tmp_path, monkeypatch)

    with pytest.raises(InvalidStorageKeyError):
        storage.get_original_path(storage_key)


def test_get_original_path_rejects_symlink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = make_available_storage(tmp_path, monkeypatch)
    originals = tmp_path / "originals"
    originals.mkdir()
    target = tmp_path / "target.jpg"
    target.write_bytes(b"photo")
    (originals / "photo.jpg").symlink_to(target)

    with pytest.raises(InvalidStorageKeyError):
        storage.get_original_path("originals/photo.jpg")


def test_get_original_path_reports_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = make_available_storage(tmp_path, monkeypatch)

    with pytest.raises(OriginalNotFoundError):
        storage.get_original_path("originals/missing.jpg")


def test_get_original_path_requires_available_storage(tmp_path: Path) -> None:
    storage = PhotoStorage(make_settings(tmp_path))

    with pytest.raises(StorageUnavailableError) as error:
        storage.get_original_path("originals/photo.jpg")

    assert error.value.status is StorageStatusCode.NOT_MOUNT_POINT


def test_stage_and_get_thumbnail_uses_derivative_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = make_available_storage(tmp_path, monkeypatch)
    source = tmp_path / "source.jpg"
    Image.new("RGB", (960, 480), "navy").save(source)
    photo_id = uuid4()
    storage_key = f"thumbnails/2026/07/{photo_id}.webp"

    staged = storage.stage_thumbnail(source, storage_key)
    staged.path.parent.mkdir(parents=True, exist_ok=True)
    destination = tmp_path / "derivatives" / storage_key
    destination.parent.mkdir(parents=True, exist_ok=True)
    staged.path.replace(destination)

    assert (staged.width, staged.height) == (480, 240)
    assert staged.content_type == "image/webp"
    assert storage.get_derivative_path(storage_key) == destination


@pytest.mark.parametrize("storage_key", ["../photo.webp", "/thumbnails/photo.webp", "originals/photo.jpg"])
def test_get_derivative_path_rejects_unsafe_keys(
    storage_key: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = make_available_storage(tmp_path, monkeypatch)

    with pytest.raises(InvalidStorageKeyError):
        storage.get_derivative_path(storage_key)


def test_resumable_upload_appends_chunks_and_builds_staged_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = make_available_storage(tmp_path, monkeypatch)
    item_id = uuid4()

    assert storage.append_resumable_chunk(item_id, 0, b"pho", 5) == 3
    assert storage.append_resumable_chunk(item_id, 3, b"to", 5) == 5

    staged = storage.resumable_as_staged(item_id, 5)
    assert staged.photo_id == item_id
    assert staged.path.read_bytes() == b"photo"
    assert staged.sha256 == hashlib.sha256(b"photo").hexdigest()


def test_resumable_upload_validates_offset_for_empty_chunks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = make_available_storage(tmp_path, monkeypatch)
    item_id = uuid4()

    assert storage.append_resumable_chunk(item_id, 0, b"", 5) == 0

    with pytest.raises(UploadOffsetMismatchError) as error:
        storage.append_resumable_chunk(item_id, 1, b"", 5)

    assert error.value.actual_offset == 0


def test_resumable_upload_reports_actual_offset_after_interruption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = make_available_storage(tmp_path, monkeypatch)
    item_id = uuid4()
    storage.append_resumable_chunk(item_id, 0, b"pho", 5)

    with pytest.raises(UploadOffsetMismatchError) as error:
        storage.append_resumable_chunk(item_id, 0, b"to", 5)

    assert error.value.actual_offset == 3
    assert storage.get_resumable_offset(item_id) == 3


def test_resumable_read_does_not_use_a_missing_hdd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = PhotoStorage(make_settings(tmp_path))
    write_marker(tmp_path)
    monkeypatch.setattr(storage_module, "_is_mount_point", lambda path: False)
    item_id = uuid4()
    part = tmp_path / "incoming" / f"{item_id}.part"
    part.parent.mkdir()
    part.write_bytes(b"photo")

    with pytest.raises(StorageUnavailableError) as error:
        storage.resumable_as_staged(item_id, 5)

    assert error.value.status is StorageStatusCode.NOT_MOUNT_POINT


def test_resumable_cleanup_keeps_partial_file_when_hdd_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = PhotoStorage(make_settings(tmp_path))
    write_marker(tmp_path)
    monkeypatch.setattr(storage_module, "_is_mount_point", lambda path: False)
    item_id = uuid4()
    part = tmp_path / "incoming" / f"{item_id}.part"
    part.parent.mkdir()
    part.write_bytes(b"photo")

    storage.cleanup_resumable(item_id)

    assert part.read_bytes() == b"photo"


def test_finalized_cleanup_never_deletes_hdd_files_when_hdd_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = PhotoStorage(make_settings(tmp_path))
    write_marker(tmp_path)
    monkeypatch.setattr(storage_module, "_is_mount_point", lambda path: False)
    original = tmp_path / "originals" / "photo.jpg"
    sidecar = tmp_path / "originals" / "photo.json"
    derivative = tmp_path / "derivatives" / "thumbnails" / "photo.webp"
    original.parent.mkdir(parents=True)
    derivative.parent.mkdir(parents=True)
    original.write_bytes(b"photo")
    sidecar.write_bytes(b"metadata")
    derivative.write_bytes(b"thumbnail")

    storage.cleanup_finalized(FinalizedUpload(original, sidecar, derivative))

    assert original.exists()
    assert sidecar.exists()
    assert not derivative.exists()


def test_cleanup_resumable_removes_partial_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = make_available_storage(tmp_path, monkeypatch)
    item_id = uuid4()
    storage.append_resumable_chunk(item_id, 0, b"photo", 5)

    storage.cleanup_resumable(item_id)

    assert storage.get_resumable_offset(item_id) == 0


def make_staged_derivative(root: Path, photo_id) -> StagedDerivative:
    path = root / "derivatives" / "incoming" / f"{photo_id}.thumbnail.part"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"thumbnail")
    return StagedDerivative(
        path=path,
        storage_key=f"thumbnails/2026/07/{photo_id}.webp",
        content_type="image/webp",
        width=480,
        height=360,
        size_bytes=9,
    )


def make_sidecar(
    photo_id,
    storage_key: str,
    size_bytes: int,
    sha256: str,
    derivative: StagedDerivative,
) -> SidecarMetadata:
    updater_id = uuid4()
    updated_at = datetime(2026, 7, 14, 4, tzinfo=UTC)
    return SidecarMetadata(
        photo_id=photo_id,
        uploaded_by_user_id=uuid4(),
        uploaded_by_username="owner",
        memo=None,
        memo_updated_by_user_id=updater_id,
        memo_updated_by_username="owner",
        memo_updated_at=updated_at,
        metadata_version=1,
        sharing_audiences=(),
        original_filename="original.jpg",
        storage_key=storage_key,
        content_type="image/jpeg",
        size_bytes=size_bytes,
        sha256=sha256,
        width=640,
        height=480,
        captured_at=None,
        uploaded_at=updated_at,
        derivatives=(
            {
                "kind": "thumbnail",
                "storage_key": derivative.storage_key,
                "content_type": derivative.content_type,
                "width": derivative.width,
                "height": derivative.height,
                "size_bytes": derivative.size_bytes,
            },
        ),
    )


def test_finalize_upload_moves_original_and_writes_sidecar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = make_available_storage(tmp_path, monkeypatch)
    photo_id = uuid4()
    storage.append_resumable_chunk(photo_id, 0, b"photo", 5)
    staged = storage.resumable_as_staged(photo_id, 5)
    derivative = make_staged_derivative(tmp_path, photo_id)
    storage_key = f"originals/2026/07/{photo_id}.jpg"
    metadata = make_sidecar(photo_id, storage_key, staged.size_bytes, staged.sha256, derivative)

    result = storage.finalize_upload(staged, derivative, metadata)

    assert result.original_path.read_bytes() == b"photo"
    sidecar_payload = json.loads(result.sidecar_path.read_text(encoding="utf-8"))
    assert sidecar_payload == {
        "schema_version": 7,
        "id": str(photo_id),
        "metadata_version": 1,
        "asset": {
            "uploaded_by_user_id": str(metadata.uploaded_by_user_id),
            "uploaded_by_username": "owner",
            "original_filename": "original.jpg",
            "storage_key": storage_key,
            "content_type": "image/jpeg",
            "size_bytes": 5,
            "sha256": staged.sha256,
            "width": 640,
            "height": 480,
            "captured_at": None,
            "captured_at_override": None,
            "uploaded_at": "2026-07-14T04:00:00Z",
            "derivatives": [
                {
                    "kind": "thumbnail",
                    "storage_key": derivative.storage_key,
                    "content_type": "image/webp",
                    "width": 480,
                    "height": 360,
                    "size_bytes": 9,
                }
            ],
        },
        "metadata": {
            "memo": None,
            "updated_by_user_id": str(metadata.memo_updated_by_user_id),
            "updated_by_username": "owner",
            "updated_at": "2026-07-14T04:00:00Z",
        },
        "sharing": {"audiences": []},
        "lifecycle": {
            "state": "active",
            "trashed_at": None,
            "trashed_by_user_id": None,
            "purge_after": None,
            "purge_requested_at": None,
        },
    }
    assert result.derivative_path is not None
    assert result.derivative_path.read_bytes() == b"thumbnail"
    assert not staged.path.exists()
    assert not (tmp_path / "incoming" / f"{photo_id}.json.part").exists()


def test_update_sidecar_replaces_metadata_atomically(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = make_available_storage(tmp_path, monkeypatch)
    photo_id = uuid4()
    storage.append_resumable_chunk(photo_id, 0, b"photo", 5)
    staged = storage.resumable_as_staged(photo_id, 5)
    derivative = make_staged_derivative(tmp_path, photo_id)
    metadata = make_sidecar(
        photo_id,
        f"originals/2026/07/{photo_id}.jpg",
        staged.size_bytes,
        staged.sha256,
        derivative,
    )
    finalized = storage.finalize_upload(staged, derivative, metadata)

    group_id = uuid4()
    storage.update_sidecar(
        replace(
            metadata,
            memo="北海道旅行",
            metadata_version=2,
            sharing_audiences=({"type": "group", "id": str(group_id)},),
        )
    )

    payload = json.loads(finalized.sidecar_path.read_text(encoding="utf-8"))
    assert payload["metadata_version"] == 2
    assert payload["metadata"]["memo"] == "北海道旅行"
    assert payload["sharing"]["audiences"] == [{"type": "group", "id": str(group_id)}]
    assert not finalized.sidecar_path.with_name(f"{photo_id}.json.part").exists()


def test_existing_photo_operations_do_not_require_upload_configuration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_marker(tmp_path)
    monkeypatch.setattr(storage_module, "_is_mount_point", lambda path: True)
    monkeypatch.setattr(storage_module, "_is_read_only", lambda path: False)
    monkeypatch.setattr(storage_module, "_is_writable", lambda path: True)
    monkeypatch.setattr(storage_module, "_get_free_bytes", lambda path: 4_096)
    settings = Settings(
        photo_storage_root=tmp_path,
        photo_derivative_root=tmp_path / "derivatives",
        photo_storage_marker=EXPECTED_MARKER,
    )
    storage = PhotoStorage(settings)
    photo_id = uuid4()
    storage_key = f"originals/2026/07/{photo_id}.jpg"
    original = tmp_path / storage_key
    original.parent.mkdir(parents=True)
    original.write_bytes(b"photo")
    derivative = make_staged_derivative(tmp_path, photo_id)
    stored_derivative = settings.photo_derivative_root / derivative.storage_key
    stored_derivative.parent.mkdir(parents=True, exist_ok=True)
    stored_derivative.write_bytes(b"thumbnail")
    metadata = make_sidecar(photo_id, storage_key, 5, hashlib.sha256(b"photo").hexdigest(), derivative)

    storage.update_sidecar(metadata)
    storage.delete_photo_files(storage_key, (derivative.storage_key,))

    assert not original.exists()
    assert not original.with_suffix(".json").exists()
    assert not stored_derivative.exists()


def test_finalize_upload_removes_original_when_sidecar_rename_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = make_available_storage(tmp_path, monkeypatch)
    photo_id = uuid4()
    storage.append_resumable_chunk(photo_id, 0, b"photo", 5)
    staged = storage.resumable_as_staged(photo_id, 5)
    derivative = make_staged_derivative(tmp_path, photo_id)
    storage_key = f"originals/2026/07/{photo_id}.jpg"
    original_replace = Path.replace

    def replace_with_sidecar_failure(path: Path, target: Path) -> Path:
        if path.name.endswith(".json.part"):
            raise OSError("simulated sidecar rename failure")
        return original_replace(path, target)

    monkeypatch.setattr(Path, "replace", replace_with_sidecar_failure)

    with pytest.raises(PhotoStorageError):
        storage.finalize_upload(
            staged,
            derivative,
            make_sidecar(photo_id, storage_key, staged.size_bytes, staged.sha256, derivative),
        )

    assert not (tmp_path / storage_key).exists()
    assert not staged.path.exists()
    assert not (tmp_path / "incoming" / f"{photo_id}.json.part").exists()


def test_delete_photo_files_logs_photo_id_and_path_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = make_available_storage(tmp_path, monkeypatch)
    photo_id = uuid4()
    target = tmp_path / "originals" / "2026" / "08" / f"{photo_id}.jpg"
    target.parent.mkdir(parents=True)
    logger = MagicMock()
    monkeypatch.setattr(storage_module, "logger", logger)

    def fail_unlink(self: Path, *, missing_ok: bool = False) -> None:
        raise OSError("simulated deletion failure")

    monkeypatch.setattr(Path, "unlink", fail_unlink)

    with pytest.raises(PhotoStorageError):
        storage.delete_photo_files(f"originals/2026/08/{photo_id}.jpg", (), photo_id=photo_id)

    logger.exception.assert_called_once_with("Photo storage file deletion failed photo_id=%s path=%s", photo_id, target)
