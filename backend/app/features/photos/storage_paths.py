import os
import re
import shutil
from pathlib import Path, PurePosixPath

from app.features.photos.storage_types import InvalidStorageKeyError, PhotoStorageError

LINUX_MOUNTINFO_PATH = Path("/proc/self/mountinfo")
MOUNTINFO_ESCAPE_PATTERN = re.compile(r"\\([0-7]{3})")


def is_mount_point(path: Path, *, mountinfo_path: Path = LINUX_MOUNTINFO_PATH) -> bool:
    try:
        mountinfo = mountinfo_path.read_text(encoding="utf-8", errors="surrogateescape")
    except OSError:
        return path.is_mount()

    for line in mountinfo.splitlines():
        fields = line.split()
        if len(fields) >= 5 and Path(decode_mountinfo_path(fields[4])) == path:
            return True
    return path.is_mount()


def decode_mountinfo_path(value: str) -> str:
    return MOUNTINFO_ESCAPE_PATTERN.sub(lambda match: chr(int(match.group(1), 8)), value)


def is_read_only(path: Path) -> bool:
    return bool(os.statvfs(path).f_flag & os.ST_RDONLY)


def is_writable(path: Path) -> bool:
    return os.access(path, os.W_OK | os.X_OK)


def get_free_bytes(path: Path) -> int:
    return shutil.disk_usage(path).free


def validate_original_key(storage_key: str) -> PurePosixPath:
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


def validate_derivative_key(storage_key: str) -> PurePosixPath:
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


def validate_path_components(candidate: Path, root: Path, description: str) -> None:
    try:
        current = root
        for part in candidate.relative_to(root).parts:
            current /= part
            if current.is_symlink():
                raise InvalidStorageKeyError(f"Symlinks are not allowed in {description} paths")
        candidate.parent.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError as error:
        raise InvalidStorageKeyError(f"{description.title()} path resolves outside its storage root") from error
    except OSError as error:
        raise PhotoStorageError(f"Could not inspect {description} path") from error
