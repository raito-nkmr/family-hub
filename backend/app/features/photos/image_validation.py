from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from warnings import catch_warnings, simplefilter
from zoneinfo import ZoneInfo

from PIL import Image, UnidentifiedImageError
from PIL.ExifTags import Base
from pillow_heif import get_file_mimetype, open_heif


class InvalidImageError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ImageMetadata:
    content_type: str
    extension: str
    width: int
    height: int
    captured_at: datetime | None


_FORMAT_DETAILS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "MPO": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
}
_HEIF_DETAILS = {
    "image/heic": ".heic",
    "image/heif": ".heif",
}


def inspect_image(path: Path, declared_content_type: str, default_timezone: str) -> ImageMetadata:
    try:
        with catch_warnings():
            simplefilter("error", Image.DecompressionBombWarning)
            try:
                return _inspect_with_pillow(path, declared_content_type, default_timezone)
            except UnidentifiedImageError:
                return _inspect_heif(path, declared_content_type, default_timezone)
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise InvalidImageError("Uploaded file is not a valid supported image") from error


def _inspect_with_pillow(path: Path, declared_content_type: str, default_timezone: str) -> ImageMetadata:
    with Image.open(path) as image:
        details = _FORMAT_DETAILS.get(image.format or "")
        if details is None:
            raise InvalidImageError("Uploaded image format is not supported")
        content_type, extension = details
        if declared_content_type != content_type:
            raise InvalidImageError("Declared content type does not match uploaded image")

        image.load()
        width, height = image.size
        captured_at = _get_captured_at(image, default_timezone)
    return ImageMetadata(content_type, extension, width, height, captured_at)


def _inspect_heif(path: Path, declared_content_type: str, default_timezone: str) -> ImageMetadata:
    content_type = get_file_mimetype(path)
    extension = _HEIF_DETAILS.get(content_type)
    # HEIC is a HEIF profile and browsers use both registered MIME names for
    # the same container. Treat the pair as one declared/inspected MIME family.
    if extension is None or declared_content_type not in _HEIF_DETAILS:
        raise InvalidImageError("Uploaded image format is not supported")

    heif_file = open_heif(path)
    if Image.MAX_IMAGE_PIXELS is not None and heif_file.size[0] * heif_file.size[1] > Image.MAX_IMAGE_PIXELS:
        raise InvalidImageError("Uploaded image dimensions exceed the safety limit")
    with heif_file.to_pillow() as image:
        image.load()
        width, height = image.size
        captured_at = _get_captured_at(image, default_timezone)
    return ImageMetadata(content_type, extension, width, height, captured_at)


def _get_captured_at(image: Image.Image, default_timezone: str) -> datetime | None:
    try:
        exif = image.getexif()
        value = exif.get(Base.DateTimeOriginal) or exif.get(Base.DateTimeDigitized) or exif.get(Base.DateTime)
        if not value:
            return None
        date_text = _as_text(value)

        offset = exif.get(Base.OffsetTimeOriginal) or exif.get(Base.OffsetTimeDigitized) or exif.get(Base.OffsetTime)
        if offset:
            parsed = datetime.strptime(f"{date_text} {_as_text(offset)}", "%Y:%m:%d %H:%M:%S %z")
        else:
            parsed = datetime.strptime(date_text, "%Y:%m:%d %H:%M:%S").replace(tzinfo=ZoneInfo(default_timezone))
        return parsed.astimezone(UTC)
    except (UnicodeDecodeError, ValueError, TypeError):
        return None


def _as_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("ascii").strip("\x00 ")
    return str(value).strip("\x00 ")
