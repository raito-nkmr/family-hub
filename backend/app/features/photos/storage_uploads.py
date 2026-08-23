"""Resumable upload operations used by the photo-storage facade."""

import hashlib
import logging
import os
import time
from errno import EDQUOT, ENOSPC
from pathlib import Path, PurePosixPath
from uuid import UUID

from app.features.photos.storage_types import (
    PhotoStorageError,
    StagedUpload,
    StorageStatusCode,
    StorageUnavailableError,
    UploadOffsetMismatchError,
    UploadTooLargeError,
)

logger = logging.getLogger(__name__)


class ResumableUploadOperations:
    """Implementation mixin for the public resumable-upload methods."""

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

    def append_resumable_file(self, item_id: UUID, expected_offset: int, source_path: Path, total_size: int) -> int:
        actual_offset = self.get_resumable_offset(item_id)
        if actual_offset != expected_offset:
            raise UploadOffsetMismatchError(actual_offset)
        try:
            source_size = source_path.stat().st_size
        except OSError as error:
            raise PhotoStorageError("Could not inspect upload chunk") from error
        if source_size == 0:
            return actual_offset
        self._require_upload_ready(source_size)
        if self._maximum_upload_bytes is None or total_size > self._maximum_upload_bytes:
            raise UploadTooLargeError("Uploaded file exceeds the configured size limit")
        if actual_offset + source_size > total_size:
            raise UploadTooLargeError("Chunk exceeds the declared file size")
        path = self._resumable_path(item_id, create_directory=True)
        persist_started = time.perf_counter()
        bytes_written = 0
        try:
            with source_path.open("rb") as source, path.open("ab") as destination:
                read_size = self._upload_chunk_bytes or 1024 * 1024
                while chunk := source.read(read_size):
                    destination.write(chunk)
                    bytes_written += len(chunk)
                destination.flush()
                os.fsync(destination.fileno())
        except OSError as error:
            if error.errno in {ENOSPC, EDQUOT}:
                raise StorageUnavailableError(StorageStatusCode.INSUFFICIENT_SPACE) from error
            raise PhotoStorageError("Could not append resumable upload") from error
        if bytes_written != source_size:
            raise PhotoStorageError("Upload chunk changed while it was being read")
        next_offset = actual_offset + bytes_written
        logger.info(
            "Resumable upload chunk synced item_id=%s expected_offset=%d next_offset=%d bytes=%d duration_ms=%.1f",
            item_id,
            expected_offset,
            next_offset,
            bytes_written,
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
            self._unlink_if_possible(self._resumable_path(item_id, create_directory=False))

    def _resumable_path(self, item_id: UUID, *, create_directory: bool) -> Path:
        incoming = self._get_or_create_directory(PurePosixPath("incoming")) if create_directory else None
        if incoming is None:
            if self._root is None:
                raise StorageUnavailableError(StorageStatusCode.NOT_CONFIGURED)
            incoming = Path(os.path.abspath(self._root)) / "incoming"
        return incoming / f"{item_id}.part"
