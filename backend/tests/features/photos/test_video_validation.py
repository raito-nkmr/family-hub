import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from app.features.photos.thumbnails import generate_video_thumbnail
from app.features.photos.video_validation import InvalidVideoError, inspect_video


def test_inspect_video_reads_dimensions_and_creation_time(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "clip.mov"
    path.write_bytes(b"video")
    probe = {
        "streams": [
            {
                "codec_type": "video",
                "width": 1920,
                "height": 1080,
                "tags": {"creation_time": "2026-07-14T12:00:00+09:00"},
            }
        ],
        "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "tags": {}},
    }
    monkeypatch.setattr(
        "app.features.photos.video_validation.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(probe)),
    )

    result = inspect_video(path, "video/quicktime", "Asia/Tokyo")

    assert result.content_type == "video/quicktime"
    assert result.extension == ".mov"
    assert (result.width, result.height) == (1920, 1080)
    assert result.captured_at_original == datetime(2026, 7, 14, 3, tzinfo=UTC)


def test_inspect_video_uses_rotation_for_display_dimensions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "portrait.mov"
    path.write_bytes(b"video")
    probe = {
        "streams": [
            {
                "codec_type": "video",
                "width": 1920,
                "height": 1080,
                "side_data_list": [{"side_data_type": "Display Matrix", "rotation": -90}],
            }
        ],
        "format": {"format_name": "mov"},
    }
    monkeypatch.setattr(
        "app.features.photos.video_validation.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(probe)),
    )

    result = inspect_video(path, "video/quicktime", "Asia/Tokyo")

    assert (result.width, result.height) == (1080, 1920)


def test_inspect_video_rejects_missing_video_stream(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"audio")
    monkeypatch.setattr(
        "app.features.photos.video_validation.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"streams": [{"codec_type": "audio"}], "format": {"format_name": "mp4"}}),
        ),
    )

    with pytest.raises(InvalidVideoError):
        inspect_video(path, "video/mp4", "Asia/Tokyo")


@pytest.mark.parametrize("format_name", ["3gp", "3g2", "m4a", "mj2"])
def test_inspect_video_rejects_unsupported_container(
    format_name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"video")
    probe = {
        "streams": [{"codec_type": "video", "width": 1920, "height": 1080}],
        "format": {"format_name": format_name},
    }
    monkeypatch.setattr(
        "app.features.photos.video_validation.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(probe)),
    )

    with pytest.raises(InvalidVideoError):
        inspect_video(path, "video/mp4", "Asia/Tokyo")


def test_generate_video_thumbnail_writes_webp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "clip.mp4"
    destination = tmp_path / "clip.webp"
    source.write_bytes(b"video")

    def run_ffmpeg(*args, **kwargs):
        Image.new("RGB", (480, 270), "navy").save(destination, format="WEBP")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("app.features.photos.thumbnails.subprocess.run", run_ffmpeg)

    result = generate_video_thumbnail(source, destination)

    assert (result.width, result.height) == (480, 270)
    assert result.size_bytes == destination.stat().st_size
