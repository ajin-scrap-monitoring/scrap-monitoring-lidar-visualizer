"""Non-blocking bounded queue and ordered raw line writer."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

DEFAULT_QUEUE_RECORDS = 128
DEFAULT_QUEUE_BYTES = 8 * 1024 * 1024


def _write_all(stream: BinaryIO, raw_line: bytes) -> None:
    remaining = memoryview(raw_line)
    while remaining:
        written = stream.write(remaining)
        if written is None or written <= 0 or written > len(remaining):
            raise OSError("recording write made no progress")
        remaining = remaining[written:]


@dataclass(frozen=True, slots=True)
class RecordingSnapshot:
    accepting: bool
    accepted_records: int
    accepted_bytes: int
    queued_records: int
    queued_bytes: int
    written_records: int
    written_bytes: int
    reason: str | None
    error: str | None


class RecordBuffer:
    def __init__(
        self,
        *,
        max_records: int,
        max_bytes: int,
        queue_records: int = DEFAULT_QUEUE_RECORDS,
        queue_bytes: int = DEFAULT_QUEUE_BYTES,
    ) -> None:
        if min(max_records, max_bytes, queue_records, queue_bytes) <= 0:
            raise ValueError("recording and queue limits must be positive")
        self._max_records = max_records
        self._max_bytes = max_bytes
        self._queue_records = queue_records
        self._queue_bytes = queue_bytes
        self._items: deque[bytes] = deque()
        self._accepting = True
        self._accepted_records = 0
        self._accepted_bytes = 0
        self._queued_bytes = 0
        self._written_records = 0
        self._written_bytes = 0
        self._reason: str | None = None
        self._error: str | None = None

    def offer(self, raw_line: bytes) -> bool:
        if not self._accepting:
            return False
        if (
            self._accepted_records + 1 > self._max_records
            or self._accepted_bytes + len(raw_line) > self._max_bytes
        ):
            self.stop("limit_reached")
            return False
        if (
            len(self._items) + 1 > self._queue_records
            or self._queued_bytes + len(raw_line) > self._queue_bytes
        ):
            self.stop("queue_full")
            return False
        self._items.append(raw_line)
        self._accepted_records += 1
        self._accepted_bytes += len(raw_line)
        self._queued_bytes += len(raw_line)
        return True

    def pop(self) -> bytes | None:
        if not self._items:
            return None
        raw_line = self._items.popleft()
        self._queued_bytes -= len(raw_line)
        return raw_line

    def mark_written(self, raw_line: bytes) -> None:
        self._written_records += 1
        self._written_bytes += len(raw_line)

    def stop(self, reason: str, error: str | None = None) -> None:
        self._accepting = False
        if self._reason is None:
            self._reason = reason
            self._error = error

    def fail(self, error: str) -> None:
        if self._reason != "write_error":
            self._accepting = False
            self._reason = "write_error"
            self._error = error

    @property
    def empty(self) -> bool:
        return not self._items

    @property
    def accepting(self) -> bool:
        return self._accepting

    def snapshot(self) -> RecordingSnapshot:
        return RecordingSnapshot(
            accepting=self._accepting,
            accepted_records=self._accepted_records,
            accepted_bytes=self._accepted_bytes,
            queued_records=len(self._items),
            queued_bytes=self._queued_bytes,
            written_records=self._written_records,
            written_bytes=self._written_bytes,
            reason=self._reason,
            error=self._error,
        )


def _open_exclusive(path: Path) -> BinaryIO:
    return path.open("xb", buffering=0)


class AsyncRecordWriter:
    def __init__(
        self,
        path: Path,
        *,
        max_records: int,
        max_bytes: int,
        file_opener: Callable[[Path], BinaryIO] = _open_exclusive,
    ) -> None:
        self.path = path
        self._buffer = RecordBuffer(max_records=max_records, max_bytes=max_bytes)
        self._wake = asyncio.Event()
        self._close_requested = False
        self._file: BinaryIO | None = None
        self._task: asyncio.Task[None] | None = None
        self._file_opener = file_opener

    @property
    def snapshot(self) -> RecordingSnapshot:
        return self._buffer.snapshot()

    async def start(self) -> None:
        if self._task is not None:
            raise RuntimeError("record writer already started")
        if not self.path.parent.is_dir():
            raise ValueError("recording parent directory does not exist")
        self._file = await asyncio.to_thread(self._file_opener, self.path)
        self._task = asyncio.create_task(self._run())

    def submit(self, raw_line: bytes) -> bool:
        if self._task is None:
            raise RuntimeError("record writer is not started")
        accepted = self._buffer.offer(raw_line)
        if accepted or not self._buffer.accepting:
            self._wake.set()
        return accepted

    async def close(self) -> RecordingSnapshot:
        if self._task is None:
            return self.snapshot
        self._close_requested = True
        if self._buffer.accepting:
            self._buffer.stop("closed")
        self._wake.set()
        await self._task
        return self.snapshot

    async def _run(self) -> None:
        assert self._file is not None
        try:
            while True:
                raw_line = self._buffer.pop()
                if raw_line is not None:
                    try:
                        await asyncio.to_thread(_write_all, self._file, raw_line)
                    except OSError as error:
                        self._buffer.fail(str(error))
                        break
                    self._buffer.mark_written(raw_line)
                    continue
                if self._close_requested or not self._buffer.accepting:
                    break
                self._wake.clear()
                if not self._buffer.empty:
                    continue
                await self._wake.wait()
        finally:
            try:
                await asyncio.to_thread(self._file.close)
            except OSError as error:
                self._buffer.fail(str(error))
