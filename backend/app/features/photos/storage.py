import os
import re
import shutil
from pathlib import Path, PurePosixPath
from secrets import compare_digest
from uuid import UUID

from app.core.config import Settings
from app.features.photos import storage_paths
from app.features.photos.storage_files import PhotoFileOperations
from app.features.photos.storage_files import logger as storage_files_logger
from app.features.photos.storage_paths import (
    get_free_bytes,
    is_mount_point,
    is_read_only,
    is_writable,
    validate_derivative_key,
    validate_original_key,
    validate_path_components,
)
from app.features.photos.storage_types import (
    DerivativeNotFoundError,
    FinalizedUpload,
    InvalidStorageKeyError,
    OriginalNotFoundError,
    PhotoStorageError,
    SidecarMetadata,
    StagedDerivative,
    StagedUpload,
    StorageStatus,
    StorageStatusCode,
    StorageUnavailableError,
    UploadOffsetMismatchError,
    UploadTooLargeError,
)
from app.features.photos.storage_uploads import ResumableUploadOperations

logger = storage_files_logger

__all__ = [
    "DerivativeNotFoundError",
    "FinalizedUpload",
    "InvalidStorageKeyError",
    "OriginalNotFoundError",
    "PhotoFileOperations",
    "PhotoStorage",
    "PhotoStorageError",
    "ResumableUploadOperations",
    "SidecarMetadata",
    "StagedDerivative",
    "StagedUpload",
    "StorageStatus",
    "StorageStatusCode",
    "StorageUnavailableError",
    "UploadOffsetMismatchError",
    "UploadTooLargeError",
]

STORAGE_MARKER_FILENAME = ".photo-storage-marker"
LINUX_MOUNTINFO_PATH = storage_paths.LINUX_MOUNTINFO_PATH
MOUNTINFO_ESCAPE_PATTERN = storage_paths.MOUNTINFO_ESCAPE_PATTERN


def _decode_mountinfo_path(value: str) -> str:
    return storage_paths.decode_mountinfo_path(value)


def _is_mount_point(path: Path) -> bool:
    return is_mount_point(path, mountinfo_path=LINUX_MOUNTINFO_PATH)


def _is_read_only(path: Path) -> bool:
    return is_read_only(path)


def _is_writable(path: Path) -> bool:
    return is_writable(path)


def _get_free_bytes(path: Path) -> int:
    return get_free_bytes(path)


class PhotoStorage(ResumableUploadOperations, PhotoFileOperations):
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
            for directory_name in ("originals", "incoming", "database-backups"):
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

        candidate, _ = self.get_original_file_paths(storage_key)
        root = Path(os.path.abspath(self._root))
        try:
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

    def get_original_file_paths(self, storage_key: str) -> tuple[Path, Path]:
        """Return safe original and sidecar candidates without requiring either file to exist."""
        status = self._get_read_status()
        if not status.available:
            raise StorageUnavailableError(status.status)
        if self._root is None:
            raise StorageUnavailableError(StorageStatusCode.NOT_CONFIGURED)

        key = self._validate_original_key(storage_key)
        root = Path(os.path.abspath(self._root))
        candidate = root.joinpath(*key.parts)
        self._validate_path_components(candidate, root, "original")
        return candidate, candidate.with_suffix(".json")

    def get_derivative_path(self, storage_key: str) -> Path:
        candidate = self.get_derivative_file_path(storage_key)
        root = Path(os.path.abspath(self._derivative_root))
        try:
            if not root.is_dir():
                raise DerivativeNotFoundError("Photo derivative root is unavailable")
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

    def get_derivative_file_path(self, storage_key: str) -> Path:
        """Return a safe derivative candidate without requiring the file to exist."""
        key = self._validate_derivative_key(storage_key)
        root = Path(os.path.abspath(self._derivative_root))
        if root.is_symlink():
            raise InvalidStorageKeyError("Photo derivative root must not be a symlink")
        candidate = root.joinpath(*key.parts)
        self._validate_path_components(candidate, root, "derivative")
        return candidate

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

    def get_database_backup_directory(self, timestamp: str) -> Path:
        """Return a validated, writable directory for a database backup timestamp."""
        if re.fullmatch(r"\d{8}T\d{6}Z", timestamp) is None:
            raise InvalidStorageKeyError("Database backup timestamp is invalid")
        self._require_writable_storage(0)
        return self._get_or_create_directory(PurePosixPath("database-backups", timestamp[:4], timestamp[4:6]))

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
        return validate_original_key(storage_key)

    @staticmethod
    def _validate_path_components(candidate: Path, root: Path, description: str) -> None:
        validate_path_components(candidate, root, description)

    @staticmethod
    def _validate_derivative_key(storage_key: str) -> PurePosixPath:
        return validate_derivative_key(storage_key)

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
