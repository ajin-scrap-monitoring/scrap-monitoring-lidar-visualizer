from __future__ import annotations

import asyncio
import io
from pathlib import Path

import pytest

from scrap_monitoring_lidar_visualizer.recording import AsyncRecordWriter, RecordBuffer


def test_record_buffer_preserves_accepted_prefix_at_record_limit() -> None:
    buffer = RecordBuffer(
        max_records=2, max_bytes=100, queue_records=4, queue_bytes=100
    )

    assert buffer.offer(b"one\n") is True
    assert buffer.offer(b"two\n") is True
    assert buffer.offer(b"three\n") is False
    assert buffer.pop() == b"one\n"
    assert buffer.pop() == b"two\n"
    assert buffer.pop() is None
    assert buffer.snapshot().reason == "limit_reached"


def test_record_buffer_stops_when_queue_is_full() -> None:
    buffer = RecordBuffer(
        max_records=10, max_bytes=100, queue_records=1, queue_bytes=100
    )

    assert buffer.offer(b"one\n") is True
    assert buffer.offer(b"two\n") is False
    assert buffer.snapshot().reason == "queue_full"


def test_record_buffer_applies_whole_line_byte_limit() -> None:
    buffer = RecordBuffer(max_records=10, max_bytes=8)

    assert buffer.offer(b"1234\n") is True
    assert buffer.offer(b"5678\n") is False
    assert buffer.snapshot().accepted_bytes == 5


def test_async_writer_writes_lines_in_order(tmp_path: Path) -> None:
    async def exercise() -> None:
        path = tmp_path / "record.jsonl"
        writer = AsyncRecordWriter(path, max_records=2, max_bytes=100)
        await writer.start()
        assert writer.submit(b"one\n") is True
        assert writer.submit(b"two\n") is True
        assert writer.submit(b"three\n") is False
        snapshot = await writer.close()

        assert path.read_bytes() == b"one\ntwo\n"
        assert snapshot.written_records == 2
        assert snapshot.reason == "limit_reached"

    asyncio.run(exercise())


def test_async_writer_protects_existing_file(tmp_path: Path) -> None:
    async def exercise() -> None:
        path = tmp_path / "record.jsonl"
        path.write_bytes(b"existing")
        writer = AsyncRecordWriter(path, max_records=1, max_bytes=10)
        with pytest.raises(FileExistsError):
            await writer.start()
        assert path.read_bytes() == b"existing"

    asyncio.run(exercise())


def test_async_writer_reports_write_failure(tmp_path: Path) -> None:
    class FailingFile(io.BytesIO):
        def write(self, data: bytes, /) -> int:
            del data
            raise OSError("storage unavailable")

    async def exercise() -> None:
        writer = AsyncRecordWriter(
            tmp_path / "record.jsonl",
            max_records=2,
            max_bytes=100,
            file_opener=lambda _: FailingFile(),
        )
        await writer.start()
        assert writer.submit(b"one\n") is True
        snapshot = await writer.close()

        assert snapshot.reason == "write_error"
        assert snapshot.error == "storage unavailable"
        assert snapshot.written_records == 0

    asyncio.run(exercise())


def test_async_writer_retries_short_writes(tmp_path: Path) -> None:
    class ShortWritingFile(io.BytesIO):
        def write(self, data: bytes, /) -> int:
            return super().write(data[:2])

        def close(self) -> None:
            pass

    async def exercise() -> None:
        stream = ShortWritingFile()
        writer = AsyncRecordWriter(
            tmp_path / "record.jsonl",
            max_records=1,
            max_bytes=100,
            file_opener=lambda _: stream,
        )
        await writer.start()
        assert writer.submit(b"record\n") is True
        snapshot = await writer.close()

        assert stream.getvalue() == b"record\n"
        assert snapshot.written_records == 1
        assert snapshot.written_bytes == 7

    asyncio.run(exercise())


def test_async_writer_reports_close_failure(tmp_path: Path) -> None:
    class CloseFailingFile(io.BytesIO):
        attempts = 0

        def close(self) -> None:
            self.attempts += 1
            if self.attempts == 1:
                raise OSError("close failed")
            super().close()

    async def exercise() -> None:
        stream = CloseFailingFile()
        writer = AsyncRecordWriter(
            tmp_path / "record.jsonl",
            max_records=1,
            max_bytes=100,
            file_opener=lambda _: stream,
        )
        await writer.start()
        assert writer.submit(b"record\n") is True
        snapshot = await writer.close()

        assert snapshot.reason == "write_error"
        assert snapshot.error == "close failed"

    asyncio.run(exercise())
