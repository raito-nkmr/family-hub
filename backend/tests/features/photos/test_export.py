from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile

from app.features.photos.export import stream_photo_export
from app.features.photos.service import PhotoExportEntry


def test_stream_photo_export_preserves_content_and_disambiguates_names(tmp_path) -> None:
    first_path = tmp_path / "first.jpg"
    second_path = tmp_path / "second.jpg"
    first_path.write_bytes(b"first original")
    second_path.write_bytes(b"second original")
    entries = [
        PhotoExportEntry(uuid4(), first_path, "旅行/写真.jpg"),
        PhotoExportEntry(uuid4(), second_path, "旅行\\写真.jpg"),
    ]

    exported = BytesIO(b"".join(stream_photo_export(entries)))

    with ZipFile(exported) as archive:
        assert archive.namelist() == ["旅行_写真.jpg", "旅行_写真 (2).jpg"]
        assert archive.read("旅行_写真.jpg") == b"first original"
        assert archive.read("旅行_写真 (2).jpg") == b"second original"
