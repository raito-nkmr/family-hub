from datetime import UTC, datetime
from pathlib import Path

import pytest
from PIL import Image
from PIL.ExifTags import Base
from pillow_heif import from_pillow

from app.features.photos.image_validation import InvalidImageError, inspect_image


def test_inspect_jpeg_extracts_dimensions_and_utc_capture_time(tmp_path: Path) -> None:
    path = tmp_path / "photo.jpg"
    exif = Image.Exif()
    exif[Base.DateTimeOriginal] = "2026:07:14 12:00:00"
    exif[Base.OffsetTimeOriginal] = "+09:00"
    Image.new("RGB", (8, 6), "red").save(path, format="JPEG", exif=exif)

    result = inspect_image(path, "image/jpeg", "Asia/Tokyo")

    assert result.content_type == "image/jpeg"
    assert result.extension == ".jpg"
    assert (result.width, result.height) == (8, 6)
    assert result.captured_at == datetime(2026, 7, 14, 3, tzinfo=UTC)


def test_inspect_jpeg_uses_exif_orientation_for_display_dimensions(tmp_path: Path) -> None:
    path = tmp_path / "portrait.jpg"
    exif = Image.Exif()
    exif[Base.Orientation] = 6
    Image.new("RGB", (8, 6), "red").save(path, format="JPEG", exif=exif)

    result = inspect_image(path, "image/jpeg", "Asia/Tokyo")

    assert (result.width, result.height) == (6, 8)


def test_inspect_mpo_accepts_primary_jpeg_image(tmp_path: Path) -> None:
    path = tmp_path / "iphone.jpeg"
    primary = Image.new("RGB", (8, 6), "red")
    secondary = Image.new("RGB", (4, 3), "blue")
    primary.save(path, format="MPO", save_all=True, append_images=[secondary])

    result = inspect_image(path, "image/jpeg", "Asia/Tokyo")

    assert result.content_type == "image/jpeg"
    assert result.extension == ".jpg"
    assert (result.width, result.height) == (8, 6)


def test_inspect_png_uses_default_timezone_for_naive_exif(tmp_path: Path) -> None:
    path = tmp_path / "photo.png"
    exif = Image.Exif()
    exif[Base.DateTimeOriginal] = "2026:07:14 12:00:00"
    Image.new("RGB", (5, 4), "blue").save(path, format="PNG", exif=exif)

    result = inspect_image(path, "image/png", "Asia/Tokyo")

    assert result.captured_at == datetime(2026, 7, 14, 3, tzinfo=UTC)


def test_inspect_heif_decodes_content(tmp_path: Path) -> None:
    path = tmp_path / "photo.heic"
    image = Image.new("RGB", (7, 3), "green")
    from_pillow(image).save(path)

    result = inspect_image(path, "image/heic", "Asia/Tokyo")

    assert result.content_type in {"image/heic", "image/heif"}
    assert result.extension in {".heic", ".heif"}
    assert (result.width, result.height) == (7, 3)


def test_inspect_image_rejects_mismatched_content_type(tmp_path: Path) -> None:
    path = tmp_path / "photo.jpg"
    Image.new("RGB", (2, 2), "red").save(path, format="JPEG")

    with pytest.raises(InvalidImageError):
        inspect_image(path, "image/png", "Asia/Tokyo")


def test_inspect_heif_accepts_equivalent_heif_mime_variant(tmp_path: Path) -> None:
    path = tmp_path / "photo.heic"
    from_pillow(Image.new("RGB", (3, 2), "green")).save(path)
    detected = inspect_image(path, "image/heic", "Asia/Tokyo")
    equivalent_declaration = "image/heif" if detected.content_type == "image/heic" else "image/heic"

    result = inspect_image(path, equivalent_declaration, "Asia/Tokyo")

    assert result.content_type == detected.content_type


def test_inspect_image_rejects_corrupt_file(tmp_path: Path) -> None:
    path = tmp_path / "photo.jpg"
    path.write_bytes(b"not an image")

    with pytest.raises(InvalidImageError):
        inspect_image(path, "image/jpeg", "Asia/Tokyo")
