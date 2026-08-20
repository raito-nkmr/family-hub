from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from uuid import UUID


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
    """Base error for failures while locating or writing stored photo files."""


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


def _isoformat_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Sidecar datetimes must be timezone-aware")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
