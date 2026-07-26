from __future__ import annotations

from collections.abc import Iterator
from queue import Full, Queue
from threading import Event, Thread
from zipfile import ZIP_STORED, ZipFile

from app.features.photos.service import PhotoExportEntry

_END = object()


class _ZipStreamBuffer:
    def __init__(self, queue: Queue[bytes | object], stopped: Event) -> None:
        self._queue = queue
        self._stopped = stopped
        self._position = 0

    def write(self, data: bytes) -> int:
        if data:
            while not self._stopped.is_set():
                try:
                    self._queue.put(bytes(data), timeout=0.1)
                    break
                except Full:
                    continue
            else:
                raise BrokenPipeError("Photo export response was closed")
            self._position += len(data)
        return len(data)

    def tell(self) -> int:
        return self._position

    def flush(self) -> None:
        pass


def _safe_archive_names(entries: list[PhotoExportEntry]) -> list[str]:
    names: list[str] = []
    used: set[str] = set()
    for entry in entries:
        normalized = "".join("_" if character in "/\\\0\r\n" else character for character in entry.original_filename)
        normalized = normalized.strip(" .") or str(entry.photo_id)
        candidate = normalized
        counter = 2
        while candidate.casefold() in used:
            dot = normalized.rfind(".")
            stem, suffix = (normalized[:dot], normalized[dot:]) if dot > 0 else (normalized, "")
            candidate = f"{stem} ({counter}){suffix}"
            counter += 1
        used.add(candidate.casefold())
        names.append(candidate)
    return names


def stream_photo_export(entries: list[PhotoExportEntry]) -> Iterator[bytes]:
    queue: Queue[bytes | object] = Queue(maxsize=8)
    stopped = Event()
    errors: list[BaseException] = []

    def produce() -> None:
        try:
            buffer = _ZipStreamBuffer(queue, stopped)
            with ZipFile(buffer, mode="w", compression=ZIP_STORED, allowZip64=True) as archive:
                for entry, archive_name in zip(entries, _safe_archive_names(entries), strict=True):
                    archive.write(entry.path, archive_name)
        except BaseException as error:  # pragma: no cover - surfaced to the response iterator
            errors.append(error)
        finally:
            while not stopped.is_set():
                try:
                    queue.put(_END, timeout=0.1)
                    break
                except Full:
                    continue

    producer = Thread(target=produce, name="photo-export", daemon=True)
    producer.start()
    try:
        while True:
            chunk = queue.get()
            if chunk is _END:
                break
            assert isinstance(chunk, bytes)
            yield chunk
    finally:
        stopped.set()
        producer.join(timeout=1)
    if errors:
        raise errors[0]
