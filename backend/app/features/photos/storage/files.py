"""Sidecar, finalization, and deletion operations for photo storage."""

import json
import logging
import os
from pathlib import Path, PurePosixPath
from uuid import UUID

from app.features.photos.storage.types import (
    FinalizedUpload,
    InvalidStorageKeyError,
    PhotoStorageError,
    SidecarMetadata,
    StagedDerivative,
    StagedUpload,
    StorageStatusCode,
    StorageUnavailableError,
)
from app.features.photos.thumbnails import (
    THUMBNAIL_CONTENT_TYPE,
    ThumbnailGenerationError,
    generate_thumbnail,
    generate_video_thumbnail,
)

logger = logging.getLogger(__name__)


def _storage_logger() -> logging.Logger:
    # Resolve the facade logger at call time so existing callers can keep patching
    # the facade module's logger in tests and integrations.
    from app.features.photos.storage import facade as storage_module

    return storage_module.logger


class PhotoFileOperations:
    """Implementation mixin for photo-file lifecycle operations."""

    def stage_thumbnail(
        self,
        source_path: Path,
        storage_key: str,
        content_type: str = "image/jpeg",
    ) -> StagedDerivative:
        key = self._validate_derivative_key(storage_key)
        incoming = self._get_or_create_derivative_directory(PurePosixPath("incoming"))
        part_path = incoming / f"{key.stem}.thumbnail.part"
        self._unlink_if_possible(part_path)
        try:
            generator = generate_video_thumbnail if content_type.startswith("video/") else generate_thumbnail
            generated = generator(source_path, part_path)
        except ThumbnailGenerationError as error:
            raise PhotoStorageError("Could not generate photo thumbnail") from error
        return StagedDerivative(
            path=part_path,
            storage_key=str(key),
            content_type=THUMBNAIL_CONTENT_TYPE,
            width=generated.width,
            height=generated.height,
            size_bytes=generated.size_bytes,
        )

    def finalize_upload(
        self,
        staged: StagedUpload,
        derivative: StagedDerivative,
        metadata: SidecarMetadata,
    ) -> FinalizedUpload:
        storage_key = self._validate_original_key(metadata.storage_key)
        derivative_key = self._validate_derivative_key(derivative.storage_key)
        payload = json.dumps(metadata.as_json(), ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
        self._require_upload_ready(len(payload))
        destination_directory = self._get_or_create_directory(PurePosixPath(*storage_key.parts[:-1]))
        original_path = destination_directory / storage_key.name
        sidecar_path = original_path.with_suffix(".json")
        sidecar_part = staged.path.with_name(f"{staged.photo_id}.json.part")
        derivative_directory = self._get_or_create_derivative_directory(PurePosixPath(*derivative_key.parts[:-1]))
        derivative_path = derivative_directory / derivative_key.name

        if original_path.exists() or sidecar_path.exists() or derivative_path.exists():
            raise PhotoStorageError("Upload destination already exists")

        try:
            with sidecar_part.open("xb") as destination:
                destination.write(payload)
                destination.flush()
                os.fsync(destination.fileno())

            staged.path.replace(original_path)
            try:
                sidecar_part.replace(sidecar_path)
            except OSError:
                self._unlink_photo_path_if_available(
                    original_path, self._photo_storage_is_available(), photo_id=staged.photo_id
                )
                raise
            try:
                derivative.path.replace(derivative_path)
            except OSError:
                photo_storage_available = self._photo_storage_is_available()
                self._unlink_photo_path_if_available(original_path, photo_storage_available, photo_id=staged.photo_id)
                self._unlink_photo_path_if_available(sidecar_path, photo_storage_available, photo_id=staged.photo_id)
                raise
        except OSError as error:
            photo_storage_available = self._photo_storage_is_available()
            self._unlink_photo_path_if_available(staged.path, photo_storage_available, photo_id=staged.photo_id)
            self._unlink_photo_path_if_available(sidecar_part, photo_storage_available, photo_id=staged.photo_id)
            self._unlink_if_possible(derivative.path, photo_id=staged.photo_id)
            raise PhotoStorageError("Could not finalize uploaded photo") from error

        return FinalizedUpload(original_path, sidecar_path, derivative_path, staged.photo_id)

    def update_sidecar(self, metadata: SidecarMetadata) -> None:
        payload = json.dumps(metadata.as_json(), ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
        self._require_writable_storage(len(payload))
        original_path = self.get_original_path(metadata.storage_key)
        sidecar_path = original_path.with_suffix(".json")
        sidecar_part = sidecar_path.with_name(f"{metadata.photo_id}.json.part")
        if sidecar_path.is_symlink():
            raise InvalidStorageKeyError("Sidecar path must not be a symlink")

        try:
            with sidecar_part.open("xb") as destination:
                destination.write(payload)
                destination.flush()
                os.fsync(destination.fileno())
            sidecar_part.replace(sidecar_path)
        except OSError as error:
            self._unlink_photo_path_if_available(
                sidecar_part, self._photo_storage_is_available(), photo_id=metadata.photo_id
            )
            raise PhotoStorageError("Could not update photo sidecar") from error

    def cleanup_staged(self, staged: StagedUpload, *, preserve_resumable: bool = False) -> None:
        photo_storage_available = self._photo_storage_is_available()
        if not preserve_resumable:
            self._unlink_photo_path_if_available(staged.path, photo_storage_available, photo_id=staged.photo_id)
        self._unlink_photo_path_if_available(
            staged.path.with_name(f"{staged.photo_id}.json.part"), photo_storage_available, photo_id=staged.photo_id
        )
        derivative_part = (
            Path(os.path.abspath(self._derivative_root)) / "incoming" / f"{staged.photo_id}.thumbnail.part"
        )
        self._unlink_if_possible(derivative_part, photo_id=staged.photo_id)

    def cleanup_finalized(self, upload: FinalizedUpload) -> None:
        photo_storage_available = self._photo_storage_is_available()
        self._unlink_photo_path_if_available(upload.original_path, photo_storage_available, photo_id=upload.photo_id)
        self._unlink_photo_path_if_available(upload.sidecar_path, photo_storage_available, photo_id=upload.photo_id)
        if upload.derivative_path is not None:
            self._unlink_if_possible(upload.derivative_path, photo_id=upload.photo_id)

    def delete_photo_files(
        self,
        original_storage_key: str,
        derivative_storage_keys: tuple[str, ...],
        *,
        photo_id: UUID | None = None,
    ) -> None:
        """Permanently delete one photo's known files. Missing files are treated as already deleted."""
        status = self._get_writable_storage_status(0)
        if not status.available:
            raise StorageUnavailableError(status.status)
        original_key = self._validate_original_key(original_storage_key)
        if self._root is None:
            raise StorageUnavailableError(StorageStatusCode.NOT_CONFIGURED)
        root = Path(os.path.abspath(self._root))
        original_path = root.joinpath(*original_key.parts)
        sidecar_path = original_path.with_suffix(".json")
        derivative_root = Path(os.path.abspath(self._derivative_root))
        derivative_paths = [
            derivative_root.joinpath(*self._validate_derivative_key(key).parts) for key in derivative_storage_keys
        ]
        for path, expected_root in (
            (original_path, root),
            (sidecar_path, root),
            *((path, derivative_root) for path in derivative_paths),
        ):
            try:
                if path.is_symlink():
                    raise InvalidStorageKeyError("Photo files must not be symlinks")
                path.parent.resolve(strict=True).relative_to(expected_root.resolve(strict=True))
                path.unlink(missing_ok=True)
            except (FileNotFoundError, NotADirectoryError):
                continue
            except ValueError as error:
                raise InvalidStorageKeyError("Photo file resolves outside its storage root") from error
            except OSError as error:
                _storage_logger().exception("Photo storage file deletion failed photo_id=%s path=%s", photo_id, path)
                raise PhotoStorageError("Could not permanently delete photo files") from error

    def _unlink_photo_path_if_available(
        self, path: Path, storage_available: bool, *, photo_id: UUID | None = None
    ) -> None:
        if storage_available:
            self._unlink_if_possible(path, photo_id=photo_id)

    @staticmethod
    def _unlink_if_possible(path: Path, *, photo_id: UUID | None = None) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError as error:
            _storage_logger().warning(
                "Photo storage cleanup failed photo_id=%s path=%s error_type=%s",
                photo_id,
                path,
                type(error).__name__,
            )
