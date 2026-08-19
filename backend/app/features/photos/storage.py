import hashlib
import json
import logging
import os
import re
import shutil
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from errno import EDQUOT, ENOSPC
from pathlib import Path, PurePosixPath
from secrets import compare_digest
from uuid import UUID

from app.core.config import Settings
from app.features.photos.thumbnails import (
    THUMBNAIL_CONTENT_TYPE,
    ThumbnailGenerationError,
    generate_thumbnail,
    generate_video_thumbnail,
)

logger = logging.getLogger(__name__)

STORAGE_MARKER_FILENAME = ".photo-storage-marker"
LINUX_MOUNTINFO_PATH = Path("/proc/self/mountinfo")
MOUNTINFO_ESCAPE_PATTERN = re.compile(r"\\([0-7]{3})")


class StorageStatusCode(StrEnum):
    AVAILABLE = "available"
    NOT_CONFIGURED = "not_configured"
    ROOT_NOT_FOUND = "root_not_found"
    ROOT_NOT_DIRECTORY = "root_not_directory"
    SYMLINK_NOT_ALLOWED = "symlink_not_allowed"
    NOT_MOUNT_POINT = "not_mount_point"
    MARKER_MISSING = "marker_missing"
    MARKER_MISMATCH = "marker_mismatch"
    READ_ONLY = "read_only"
    NOT_WRITABLE = "not_writable"
    INSUFFICIENT_SPACE = "insufficient_space"
    IO_ERROR = "io_error"


class PhotoStorageError(Exception):
    """Base error for failures while locating a stored original."""


class StorageUnavailableError(PhotoStorageError):
    def __init__(self, status: StorageStatusCode) -> None:
        super().__init__(f"Photo storage is unavailable: {status}")
        self.status = status


class InvalidStorageKeyError(PhotoStorageError):
    pass


class OriginalNotFoundError(PhotoStorageError):
    pass


class DerivativeNotFoundError(PhotoStorageError):
    pass


class UploadTooLargeError(PhotoStorageError):
    pass


class UploadOffsetMismatchError(PhotoStorageError):
    def __init__(self, actual_offset: int) -> None:
        super().__init__(f"Upload offset does not match stored content: {actual_offset}")
        self.actual_offset = actual_offset


@dataclass(frozen=True, slots=True)
class StagedUpload:
    photo_id: UUID
    path: Path
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class StagedDerivative:
    path: Path
    storage_key: str
    content_type: str
    width: int
    height: int
    size_bytes: int


@dataclass(frozen=True, slots=True)
class SidecarMetadata:
    photo_id: UUID
    uploaded_by_user_id: UUID
    uploaded_by_username: str
    memo: str | None
    memo_updated_by_user_id: UUID
    memo_updated_by_username: str
    memo_updated_at: datetime
    metadata_version: int
    sharing_audiences: tuple[dict[str, str | None], ...]
    original_filename: str
    storage_key: str
    content_type: str
    size_bytes: int
    sha256: str
    width: int
    height: int
    captured_at: datetime | None
    uploaded_at: datetime
    derivatives: tuple[dict[str, object], ...]
    captured_at_override: datetime | None = None
    lifecycle_state: str = "active"
    trashed_at: datetime | None = None
    trashed_by_user_id: UUID | None = None
    purge_after: datetime | None = None
    purge_requested_at: datetime | None = None

    def as_json(self) -> dict[str, object]:
        return {
            "schema_version": 7,
            "id": str(self.photo_id),
            "metadata_version": self.metadata_version,
            "asset": {
                "uploaded_by_user_id": str(self.uploaded_by_user_id),
                "uploaded_by_username": self.uploaded_by_username,
                "original_filename": self.original_filename,
                "storage_key": self.storage_key,
                "content_type": self.content_type,
                "size_bytes": self.size_bytes,
                "sha256": self.sha256,
                "width": self.width,
                "height": self.height,
                "captured_at": _isoformat_utc(self.captured_at),
                "captured_at_override": _isoformat_utc(self.captured_at_override),
                "uploaded_at": _isoformat_utc(self.uploaded_at),
                "derivatives": list(self.derivatives),
            },
            "metadata": {
                "memo": self.memo,
                "updated_by_user_id": str(self.memo_updated_by_user_id),
                "updated_by_username": self.memo_updated_by_username,
                "updated_at": _isoformat_utc(self.memo_updated_at),
            },
            "sharing": {"audiences": list(self.sharing_audiences)},
            "lifecycle": {
                "state": self.lifecycle_state,
                "trashed_at": _isoformat_utc(self.trashed_at),
                "trashed_by_user_id": str(self.trashed_by_user_id) if self.trashed_by_user_id else None,
                "purge_after": _isoformat_utc(self.purge_after),
                "purge_requested_at": _isoformat_utc(self.purge_requested_at),
            },
        }


@dataclass(frozen=True, slots=True)
class FinalizedUpload:
    original_path: Path
    sidecar_path: Path
    derivative_path: Path | None = None
    photo_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class StorageStatus:
    status: StorageStatusCode
    writable: bool
    free_bytes: int | None
    minimum_free_bytes: int | None
    total_bytes: int | None = None

    @property
    def available(self) -> bool:
        return self.status is StorageStatusCode.AVAILABLE


def _is_mount_point(path: Path) -> bool:
    try:
        mountinfo = LINUX_MOUNTINFO_PATH.read_text(encoding="utf-8", errors="surrogateescape")
    except OSError:
        return path.is_mount()

    for line in mountinfo.splitlines():
        fields = line.split()
        if len(fields) >= 5 and Path(_decode_mountinfo_path(fields[4])) == path:
            return True
    return path.is_mount()


def _decode_mountinfo_path(value: str) -> str:
    return MOUNTINFO_ESCAPE_PATTERN.sub(lambda match: chr(int(match.group(1), 8)), value)


def _is_read_only(path: Path) -> bool:
    return bool(os.statvfs(path).f_flag & os.ST_RDONLY)


def _is_writable(path: Path) -> bool:
    return os.access(path, os.W_OK | os.X_OK)


def _get_free_bytes(path: Path) -> int:
    return shutil.disk_usage(path).free


class PhotoStorage:
    def __init__(self, settings: Settings) -> None:
        self._root = settings.photo_storage_root
        self._derivative_root = settings.photo_derivative_root
        self._expected_marker = settings.photo_storage_marker
        self._maximum_upload_bytes = settings.photo_max_upload_bytes
        self._minimum_free_bytes = settings.photo_min_free_bytes
        self._upload_chunk_bytes = settings.photo_upload_chunk_bytes

    @property
    def maximum_upload_bytes(self) -> int | None:
        return self._maximum_upload_bytes

    def get_status(self) -> StorageStatus:
        return self._get_upload_status(self._maximum_upload_bytes)

    def get_read_status(self) -> StorageStatus:
        return self._get_read_status()

    def require_capacity(self, additional_bytes: int) -> None:
        self._require_upload_ready(additional_bytes)

    def get_resumable_offset(self, item_id: UUID) -> int:
        self._require_readable_storage()
        path = self._resumable_path(item_id, create_directory=False)
        try:
            if path.is_symlink():
                raise PhotoStorageError("Resumable upload must not be a symlink")
            return path.stat().st_size if path.exists() else 0
        except OSError as error:
            raise PhotoStorageError("Could not inspect resumable upload") from error

    def append_resumable_chunk(self, item_id: UUID, expected_offset: int, data: bytes, total_size: int) -> int:
        actual_offset = self.get_resumable_offset(item_id)
        if actual_offset != expected_offset:
            raise UploadOffsetMismatchError(actual_offset)
        if not data:
            return actual_offset
        self._require_upload_ready(len(data))
        if self._maximum_upload_bytes is None or total_size > self._maximum_upload_bytes:
            raise UploadTooLargeError("Uploaded file exceeds the configured size limit")
        path = self._resumable_path(item_id, create_directory=True)
        if actual_offset + len(data) > total_size:
            raise UploadTooLargeError("Chunk exceeds the declared file size")
        persist_started = time.perf_counter()
        try:
            with path.open("ab") as destination:
                destination.write(data)
                destination.flush()
                os.fsync(destination.fileno())
        except OSError as error:
            if error.errno in {ENOSPC, EDQUOT}:
                raise StorageUnavailableError(StorageStatusCode.INSUFFICIENT_SPACE) from error
            raise PhotoStorageError("Could not append resumable upload") from error
        next_offset = actual_offset + len(data)
        logger.info(
            "Resumable upload chunk synced item_id=%s expected_offset=%d next_offset=%d bytes=%d duration_ms=%.1f",
            item_id,
            expected_offset,
            next_offset,
            len(data),
            (time.perf_counter() - persist_started) * 1000,
        )
        return next_offset

    def resumable_as_staged(self, item_id: UUID, expected_size: int) -> StagedUpload:
        self._require_readable_storage()
        path = self._resumable_path(item_id, create_directory=False)
        digest = hashlib.sha256()
        size_bytes = 0
        try:
            with path.open("rb") as source:
                while chunk := source.read(self._upload_chunk_bytes):
                    size_bytes += len(chunk)
                    digest.update(chunk)
        except OSError as error:
            raise PhotoStorageError("Could not read completed resumable upload") from error
        if size_bytes != expected_size:
            raise UploadOffsetMismatchError(size_bytes)
        return StagedUpload(item_id, path, size_bytes, digest.hexdigest())

    def cleanup_resumable(self, item_id: UUID) -> None:
        if self._photo_storage_is_available():
            _unlink_if_possible(self._resumable_path(item_id, create_directory=False))

    def _resumable_path(self, item_id: UUID, *, create_directory: bool) -> Path:
        incoming = self._get_or_create_directory(PurePosixPath("incoming")) if create_directory else None
        if incoming is None:
            if self._root is None:
                raise StorageUnavailableError(StorageStatusCode.NOT_CONFIGURED)
            incoming = Path(os.path.abspath(self._root)) / "incoming"
        return incoming / f"{item_id}.part"

    def _get_upload_status(self, additional_bytes: int | None) -> StorageStatus:
        if (
            self._root is None
            or not self._expected_marker
            or self._maximum_upload_bytes is None
            or self._minimum_free_bytes is None
            or self._upload_chunk_bytes is None
            or additional_bytes is None
        ):
            return self._status(StorageStatusCode.NOT_CONFIGURED)

        return self._get_writable_storage_status(additional_bytes)

    def _get_writable_storage_status(self, additional_bytes: int) -> StorageStatus:
        if self._root is None or not self._expected_marker:
            return self._status(StorageStatusCode.NOT_CONFIGURED)

        status = self._get_read_status()
        if not status.available:
            return status

        root = Path(os.path.abspath(self._root))
        try:
            if _is_read_only(root):
                return self._status(StorageStatusCode.READ_ONLY)
            if not _is_writable(root):
                return self._status(StorageStatusCode.NOT_WRITABLE)
            for directory_name in ("originals", "incoming"):
                directory = root / directory_name
                if directory.is_symlink():
                    return self._status(StorageStatusCode.SYMLINK_NOT_ALLOWED)
                if directory.exists() and (not directory.is_dir() or not _is_writable(directory)):
                    return self._status(StorageStatusCode.NOT_WRITABLE)
            free_bytes = _get_free_bytes(root)
            total_bytes = shutil.disk_usage(root).total
        except OSError:
            return self._status(StorageStatusCode.IO_ERROR)

        required_free_bytes = (self._minimum_free_bytes or 0) + additional_bytes
        if free_bytes < required_free_bytes:
            return self._status(
                StorageStatusCode.INSUFFICIENT_SPACE,
                writable=True,
                free_bytes=free_bytes,
                total_bytes=total_bytes,
            )
        return self._status(StorageStatusCode.AVAILABLE, writable=True, free_bytes=free_bytes, total_bytes=total_bytes)

    def get_original_path(self, storage_key: str) -> Path:
        status = self._get_read_status()
        if not status.available:
            raise StorageUnavailableError(status.status)

        key = PurePosixPath(storage_key)
        if (
            key.is_absolute()
            or not key.parts
            or key.parts[0] != "originals"
            or ".." in key.parts
            or "\\" in storage_key
        ):
            raise InvalidStorageKeyError("Storage key must be a relative path below originals")

        if self._root is None:
            raise StorageUnavailableError(StorageStatusCode.NOT_CONFIGURED)

        root = Path(os.path.abspath(self._root))
        candidate = root.joinpath(*key.parts)
        try:
            current = root
            for part in key.parts:
                current /= part
                if current.is_symlink():
                    raise InvalidStorageKeyError("Symlinks are not allowed in original paths")

            resolved_candidate = candidate.resolve(strict=True)
            resolved_candidate.relative_to(root)
        except (FileNotFoundError, NotADirectoryError) as error:
            raise OriginalNotFoundError(f"Stored original does not exist: {storage_key}") from error
        except ValueError as error:
            raise InvalidStorageKeyError("Storage key resolves outside the storage root") from error
        except OSError as error:
            raise PhotoStorageError(f"Could not inspect stored original: {storage_key}") from error

        if not resolved_candidate.is_file():
            raise OriginalNotFoundError(f"Stored original is not a file: {storage_key}")
        return resolved_candidate

    def get_derivative_path(self, storage_key: str) -> Path:
        key = self._validate_derivative_key(storage_key)
        root = Path(os.path.abspath(self._derivative_root))
        candidate = root.joinpath(*key.parts)
        try:
            if root.is_symlink() or not root.is_dir():
                raise DerivativeNotFoundError("Photo derivative root is unavailable")
            current = root
            for part in key.parts:
                current /= part
                if current.is_symlink():
                    raise InvalidStorageKeyError("Symlinks are not allowed in derivative paths")
            resolved_candidate = candidate.resolve(strict=True)
            resolved_candidate.relative_to(root.resolve(strict=True))
        except (FileNotFoundError, NotADirectoryError) as error:
            raise DerivativeNotFoundError(f"Stored derivative does not exist: {storage_key}") from error
        except ValueError as error:
            raise InvalidStorageKeyError("Derivative key resolves outside the derivative root") from error
        except OSError as error:
            raise PhotoStorageError(f"Could not inspect stored derivative: {storage_key}") from error
        if not resolved_candidate.is_file():
            raise DerivativeNotFoundError(f"Stored derivative is not a file: {storage_key}")
        return resolved_candidate

    def _get_read_status(self) -> StorageStatus:
        if self._root is None or not self._expected_marker:
            return self._status(StorageStatusCode.NOT_CONFIGURED)

        root = Path(os.path.abspath(self._root))
        if not root.exists():
            return self._status(StorageStatusCode.ROOT_NOT_FOUND)
        if not root.is_dir():
            return self._status(StorageStatusCode.ROOT_NOT_DIRECTORY)

        try:
            resolved_root = root.resolve(strict=True)
        except OSError:
            return self._status(StorageStatusCode.IO_ERROR)

        if resolved_root != root:
            return self._status(StorageStatusCode.SYMLINK_NOT_ALLOWED)
        if not _is_mount_point(root):
            return self._status(StorageStatusCode.NOT_MOUNT_POINT)

        marker_path = root / STORAGE_MARKER_FILENAME
        if marker_path.is_symlink():
            return self._status(StorageStatusCode.SYMLINK_NOT_ALLOWED)
        if not marker_path.is_file():
            return self._status(StorageStatusCode.MARKER_MISSING)

        try:
            actual_marker = marker_path.read_bytes().strip()
        except OSError:
            return self._status(StorageStatusCode.IO_ERROR)
        if not compare_digest(actual_marker, self._expected_marker.encode("utf-8")):
            return self._status(StorageStatusCode.MARKER_MISMATCH)
        return self._status(StorageStatusCode.AVAILABLE)

    def stage_thumbnail(
        self,
        source_path: Path,
        storage_key: str,
        content_type: str = "image/jpeg",
    ) -> StagedDerivative:
        key = self._validate_derivative_key(storage_key)
        incoming = self._get_or_create_derivative_directory(PurePosixPath("incoming"))
        part_path = incoming / f"{key.stem}.thumbnail.part"
        _unlink_if_possible(part_path)
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
            _unlink_if_possible(derivative.path, photo_id=staged.photo_id)
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

    def cleanup_staged(self, staged: StagedUpload) -> None:
        photo_storage_available = self._photo_storage_is_available()
        self._unlink_photo_path_if_available(staged.path, photo_storage_available, photo_id=staged.photo_id)
        self._unlink_photo_path_if_available(
            staged.path.with_name(f"{staged.photo_id}.json.part"), photo_storage_available, photo_id=staged.photo_id
        )
        derivative_part = (
            Path(os.path.abspath(self._derivative_root)) / "incoming" / f"{staged.photo_id}.thumbnail.part"
        )
        _unlink_if_possible(derivative_part, photo_id=staged.photo_id)

    def cleanup_finalized(self, upload: FinalizedUpload) -> None:
        photo_storage_available = self._photo_storage_is_available()
        self._unlink_photo_path_if_available(upload.original_path, photo_storage_available, photo_id=upload.photo_id)
        self._unlink_photo_path_if_available(upload.sidecar_path, photo_storage_available, photo_id=upload.photo_id)
        if upload.derivative_path is not None:
            _unlink_if_possible(upload.derivative_path, photo_id=upload.photo_id)

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
                logger.exception("Photo storage file deletion failed photo_id=%s path=%s", photo_id, path)
                raise PhotoStorageError("Could not permanently delete photo files") from error

    def _require_upload_ready(self, additional_bytes: int | None) -> None:
        status = self._get_upload_status(additional_bytes)
        if not status.available:
            raise StorageUnavailableError(status.status)
        if self._maximum_upload_bytes is None or self._upload_chunk_bytes is None:
            raise StorageUnavailableError(StorageStatusCode.NOT_CONFIGURED)

    def _require_readable_storage(self) -> None:
        status = self._get_read_status()
        if not status.available:
            raise StorageUnavailableError(status.status)

    def _photo_storage_is_available(self) -> bool:
        status = self._get_read_status()
        if not status.available:
            logger.warning("Skipping photo-storage cleanup because storage is unavailable: %s", status.status)
            return False
        return True

    @staticmethod
    def _unlink_photo_path_if_available(path: Path, storage_available: bool, *, photo_id: UUID | None = None) -> None:
        if storage_available:
            _unlink_if_possible(path, photo_id=photo_id)

    def _require_writable_storage(self, additional_bytes: int) -> None:
        status = self._get_writable_storage_status(additional_bytes)
        if not status.available:
            raise StorageUnavailableError(status.status)

    def _get_or_create_directory(self, relative_path: PurePosixPath) -> Path:
        if self._root is None:
            raise StorageUnavailableError(StorageStatusCode.NOT_CONFIGURED)

        root = Path(os.path.abspath(self._root))
        directory = root
        try:
            for part in relative_path.parts:
                directory /= part
                if directory.is_symlink():
                    raise InvalidStorageKeyError("Symlinks are not allowed in storage directories")
                directory.mkdir(exist_ok=True)
                if not directory.is_dir():
                    raise PhotoStorageError("Storage path is not a directory")
            directory.resolve(strict=True).relative_to(root)
        except OSError as error:
            raise PhotoStorageError("Could not prepare storage directory") from error
        except ValueError as error:
            raise InvalidStorageKeyError("Storage directory resolves outside the storage root") from error
        return directory

    def _get_or_create_derivative_directory(self, relative_path: PurePosixPath) -> Path:
        root = Path(os.path.abspath(self._derivative_root))
        if root.is_symlink():
            raise InvalidStorageKeyError("Photo derivative root must not be a symlink")
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise PhotoStorageError("Could not prepare photo derivative root") from error
        if not root.is_dir():
            raise PhotoStorageError("Photo derivative root is not a directory")

        directory = root
        try:
            for part in relative_path.parts:
                directory /= part
                if directory.is_symlink():
                    raise InvalidStorageKeyError("Symlinks are not allowed in derivative directories")
                directory.mkdir(exist_ok=True)
                if not directory.is_dir():
                    raise PhotoStorageError("Derivative storage path is not a directory")
            directory.resolve(strict=True).relative_to(root.resolve(strict=True))
        except OSError as error:
            raise PhotoStorageError("Could not prepare derivative storage directory") from error
        except ValueError as error:
            raise InvalidStorageKeyError("Derivative directory resolves outside the derivative root") from error
        return directory

    def _validate_original_key(self, storage_key: str) -> PurePosixPath:
        key = PurePosixPath(storage_key)
        if (
            key.is_absolute()
            or len(key.parts) < 2
            or key.parts[0] != "originals"
            or ".." in key.parts
            or "\\" in storage_key
        ):
            raise InvalidStorageKeyError("Storage key must be a relative path below originals")
        return key

    @staticmethod
    def _validate_derivative_key(storage_key: str) -> PurePosixPath:
        key = PurePosixPath(storage_key)
        if (
            key.is_absolute()
            or len(key.parts) < 2
            or key.parts[0] != "thumbnails"
            or ".." in key.parts
            or "\\" in storage_key
        ):
            raise InvalidStorageKeyError("Storage key must be a relative path below thumbnails")
        return key

    def _status(
        self,
        status: StorageStatusCode,
        *,
        writable: bool = False,
        free_bytes: int | None = None,
        total_bytes: int | None = None,
    ) -> StorageStatus:
        return StorageStatus(
            status=status,
            writable=writable,
            free_bytes=free_bytes,
            minimum_free_bytes=self._minimum_free_bytes,
            total_bytes=total_bytes,
        )


def _isoformat_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Sidecar datetimes must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _unlink_if_possible(path: Path, *, photo_id: UUID | None = None) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as error:
        logger.warning(
            "Photo storage cleanup failed photo_id=%s path=%s error_type=%s",
            photo_id,
            path,
            type(error).__name__,
        )
