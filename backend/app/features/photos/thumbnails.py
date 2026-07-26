import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from warnings import catch_warnings, simplefilter

from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import open_heif

THUMBNAIL_CONTENT_TYPE = "image/webp"
THUMBNAIL_MAX_PIXELS = 480
THUMBNAIL_WEBP_QUALITY = 80
THUMBNAIL_WEBP_METHOD = 4


class ThumbnailGenerationError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ThumbnailMetadata:
    width: int
    height: int
    size_bytes: int


def generate_thumbnail(source_path: Path, destination_path: Path) -> ThumbnailMetadata:
    try:
        with catch_warnings():
            simplefilter("error", Image.DecompressionBombWarning)
            with _open_image(source_path) as source:
                source.load()
                oriented = ImageOps.exif_transpose(source)
                try:
                    oriented.thumbnail((THUMBNAIL_MAX_PIXELS, THUMBNAIL_MAX_PIXELS), Image.Resampling.LANCZOS)
                    output = _prepare_for_webp(oriented)
                    try:
                        with destination_path.open("xb") as destination:
                            output.save(
                                destination,
                                format="WEBP",
                                quality=THUMBNAIL_WEBP_QUALITY,
                                method=THUMBNAIL_WEBP_METHOD,
                            )
                            destination.flush()
                            os.fsync(destination.fileno())
                    finally:
                        output.close()
                    width, height = oriented.size
                finally:
                    if oriented is not source:
                        oriented.close()
        return ThumbnailMetadata(width=width, height=height, size_bytes=destination_path.stat().st_size)
    except (
        OSError,
        SyntaxError,
        ValueError,
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        destination_path.unlink(missing_ok=True)
        raise ThumbnailGenerationError("Could not generate photo thumbnail") from error


@contextmanager
def _open_image(path: Path) -> Iterator[Image.Image]:
    try:
        image = Image.open(path)
    except UnidentifiedImageError:
        heif_file = open_heif(path)
        with heif_file.to_pillow() as image:
            yield image
    else:
        with image:
            yield image


def _prepare_for_webp(image: Image.Image) -> Image.Image:
    if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
        return image.convert("RGBA")
    return image.convert("RGB")
