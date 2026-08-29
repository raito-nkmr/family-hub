import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo


class InvalidVideoError(Exception):
    """Raised when an uploaded file is not a supported video."""


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    content_type: str
    extension: str
    width: int
    height: int
    captured_at_original: datetime | None


VIDEO_CONTENT_TYPES = {
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/x-m4v": ".m4v",
}
_SUPPORTED_FORMATS_BY_CONTENT_TYPE = {
    "video/mp4": {"mp4"},
    "video/quicktime": {"mov"},
    # ffprobe identifies M4V files through the ISO-BMFF mp4 demuxer.
    "video/x-m4v": {"mov", "mp4"},
}
_FFPROBE_TIMEOUT_SECONDS = 30


def inspect_video(path: Path, declared_content_type: str, default_timezone: str) -> VideoMetadata:
    extension = VIDEO_CONTENT_TYPES.get(declared_content_type)
    if extension is None:
        raise InvalidVideoError("Uploaded video format is not supported")

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=format_name:format_tags=creation_time,com.apple.quicktime.creationdate:"
                "stream=codec_type,width,height:stream_tags=creation_time,com.apple.quicktime.creationdate,rotate:"
                "stream_side_data=rotation",
                "-of",
                "json",
                str(path),
            ],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            text=True,
            timeout=_FFPROBE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise InvalidVideoError("Could not inspect uploaded video") from error

    if result.returncode != 0:
        raise InvalidVideoError("Uploaded file is not a valid supported video")
    try:
        probe = json.loads(result.stdout)
        format_names = set(str(probe.get("format", {}).get("format_name", "")).split(","))
        stream = next(stream for stream in probe.get("streams", []) if stream.get("codec_type") == "video")
        width = int(stream["width"])
        height = int(stream["height"])
    except (KeyError, StopIteration, TypeError, ValueError, json.JSONDecodeError) as error:
        raise InvalidVideoError("Uploaded file does not contain a usable video stream") from error

    allowed_formats = _SUPPORTED_FORMATS_BY_CONTENT_TYPE[declared_content_type]
    if not format_names & allowed_formats or width <= 0 or height <= 0:
        raise InvalidVideoError("Uploaded video format is not supported")
    if _get_rotation(stream) % 180 == 90:
        width, height = height, width

    captured_at_original = _get_captured_at_original(probe, default_timezone)
    return VideoMetadata(
        content_type=declared_content_type,
        extension=extension,
        width=width,
        height=height,
        captured_at_original=captured_at_original,
    )


def _get_rotation(stream: dict[str, object]) -> int:
    side_data_list = stream.get("side_data_list")
    if isinstance(side_data_list, list):
        for side_data in side_data_list:
            if isinstance(side_data, dict) and "rotation" in side_data:
                try:
                    return round(float(side_data["rotation"])) % 360
                except (TypeError, ValueError):
                    continue

    tags = stream.get("tags")
    if isinstance(tags, dict) and "rotate" in tags:
        try:
            return round(float(tags["rotate"])) % 360
        except (TypeError, ValueError):
            pass
    return 0


def _get_captured_at_original(probe: dict[str, object], default_timezone: str) -> datetime | None:
    format_tags = probe.get("format", {}).get("tags", {}) if isinstance(probe.get("format"), dict) else {}
    if isinstance(format_tags, dict):
        for key in ("creation_time", "com.apple.quicktime.creationdate"):
            if not format_tags.get(key):
                continue
            parsed = _parse_creation_time(str(format_tags[key]), default_timezone)
            if parsed is not None:
                return parsed

    streams = probe.get("streams", [])
    if isinstance(streams, list):
        for stream in streams:
            if not isinstance(stream, dict):
                continue
            tags = stream.get("tags")
            if isinstance(tags, dict):
                for key in ("creation_time", "com.apple.quicktime.creationdate"):
                    if not tags.get(key):
                        continue
                    parsed = _parse_creation_time(str(tags[key]), default_timezone)
                    if parsed is not None:
                        return parsed
    return None


def _parse_creation_time(value: str, default_timezone: str) -> datetime | None:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(default_timezone))
    return parsed.astimezone(UTC)
