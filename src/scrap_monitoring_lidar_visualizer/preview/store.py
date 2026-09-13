"""Thread-safe latest-frame storage with no frame history."""

from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True, slots=True)
class FrameSnapshot:
    png: bytes
    top_png: bytes
    revision: int
    run_id: str
    sequence: int


class LatestFrameStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._revision = 0
        self._frame: FrameSnapshot | None = None

    def publish(
        self, png: bytes, top_png: bytes, *, run_id: str, sequence: int
    ) -> FrameSnapshot:
        with self._lock:
            self._revision += 1
            self._frame = FrameSnapshot(
                png=bytes(png),
                top_png=bytes(top_png),
                revision=self._revision,
                run_id=run_id,
                sequence=sequence,
            )
            return self._frame

    def clear(self) -> None:
        with self._lock:
            self._revision += 1
            self._frame = None

    def get(self) -> FrameSnapshot | None:
        with self._lock:
            return self._frame

    @property
    def revision(self) -> int:
        with self._lock:
            return self._revision
