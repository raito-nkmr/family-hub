from pathlib import Path

import pytest
from PIL import Image

from app.features.photos.thumbnails import ThumbnailGenerationError, generate_thumbnail


def test_generate_thumbnail_resizes_to_bounding_box_and_writes_webp(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    destination = tmp_path / "thumbnail.part"
    Image.new("RGB", (1200, 600), "navy").save(source)

    result = generate_thumbnail(source, destination)

    assert (result.width, result.height) == (480, 240)
    assert result.size_bytes == destination.stat().st_size
    with Image.open(destination) as thumbnail:
        assert thumbnail.format == "WEBP"
        assert thumbnail.size == (480, 240)


def test_generate_thumbnail_does_not_upscale_small_image(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    destination = tmp_path / "thumbnail.part"
    Image.new("RGB", (160, 120), "green").save(source)

    result = generate_thumbnail(source, destination)

    assert (result.width, result.height) == (160, 120)


def test_generate_thumbnail_uses_primary_mpo_image(tmp_path: Path) -> None:
    source = tmp_path / "iphone.jpeg"
    destination = tmp_path / "thumbnail.part"
    primary = Image.new("RGB", (800, 400), "red")
    secondary = Image.new("RGB", (200, 100), "blue")
    primary.save(source, format="MPO", save_all=True, append_images=[secondary])

    result = generate_thumbnail(source, destination)

    assert (result.width, result.height) == (480, 240)
    with Image.open(destination) as thumbnail:
        assert thumbnail.format == "WEBP"
        assert thumbnail.getpixel((0, 0))[0] > thumbnail.getpixel((0, 0))[2]


def test_generate_thumbnail_preserves_transparency(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    destination = tmp_path / "thumbnail.part"
    Image.new("RGBA", (32, 32), (0, 0, 0, 0)).save(source)

    generate_thumbnail(source, destination)

    with Image.open(destination) as thumbnail:
        assert thumbnail.convert("RGBA").getpixel((0, 0))[3] == 0


def test_generate_thumbnail_removes_partial_output_for_invalid_image(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    destination = tmp_path / "thumbnail.part"
    source.write_bytes(b"not an image")

    with pytest.raises(ThumbnailGenerationError):
        generate_thumbnail(source, destination)

    assert not destination.exists()
