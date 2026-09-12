from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from scrap_monitoring_lidar_visualizer.contracts import ContractParser
from scrap_monitoring_lidar_visualizer.receiver import ObservationReceiver
from scrap_monitoring_lidar_visualizer.recording import AsyncRecordWriter

CONTRACT_ROOT = Path("contracts/observation/v1")
FIXTURE_PATH = CONTRACT_ROOT / "fixtures/observation.v1.jsonl"


async def _start(
    receiver: ObservationReceiver,
) -> tuple[asyncio.Server, str, int]:
    server = await asyncio.start_server(receiver.handle_client, "127.0.0.1", 0)
    address = server.sockets[0].getsockname()
    return server, str(address[0]), int(address[1])


async def _send(host: str, port: int, chunks: tuple[bytes, ...]) -> bytes:
    reader, writer = await asyncio.open_connection(host, port)
    for chunk in chunks:
        writer.write(chunk)
        await writer.drain()
    writer.write_eof()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    return response


def _fixture_lines() -> tuple[bytes, bytes]:
    header, observation = FIXTURE_PATH.read_bytes().splitlines(keepends=True)
    return header, observation


def _observation(sequence: int, elapsed_s: float) -> bytes:
    _, line = _fixture_lines()
    document: dict[str, Any] = json.loads(line)
    document["sequence"] = sequence
    document["scenario"]["elapsed_s"] = elapsed_s
    return json.dumps(document, separators=(",", ":")).encode() + b"\n"


def test_receiver_handles_packet_boundaries_without_response(tmp_path: Path) -> None:
    async def exercise() -> None:
        path = tmp_path / "received.jsonl"
        recorder = AsyncRecordWriter(path, max_records=10, max_bytes=1_000_000)
        await recorder.start()
        receiver = ObservationReceiver(ContractParser(CONTRACT_ROOT), recorder=recorder)
        server, host, port = await _start(receiver)
        header, observation = _fixture_lines()
        payload = header + observation

        response = await _send(host, port, (payload[:11], payload[11:73], payload[73:]))
        await asyncio.sleep(0)
        snapshot = await recorder.close()
        server.close()
        await server.wait_closed()

        assert response == b""
        assert receiver.snapshot.records_accepted == 2
        assert receiver.state.observation is not None
        assert receiver.state.connected is False
        assert path.read_bytes() == payload
        assert snapshot.written_records == 2

    asyncio.run(exercise())


def test_receiver_rejects_invalid_record_and_keeps_connection() -> None:
    async def exercise() -> None:
        receiver = ObservationReceiver(ContractParser(CONTRACT_ROOT))
        server, host, port = await _start(receiver)
        header, _ = _fixture_lines()
        invalid = b'{"type":"load_model_observation"}\n'

        await _send(host, port, (header + invalid + _observation(2, 2.0),))
        server.close()
        await server.wait_closed()

        assert receiver.snapshot.records_rejected == 1
        assert receiver.snapshot.records_accepted == 2
        assert receiver.state.observation is not None
        assert receiver.state.observation.sequence == 2
        assert receiver.state.missing_sequences == 1

    asyncio.run(exercise())


def test_recording_limit_does_not_stop_live_state(tmp_path: Path) -> None:
    async def exercise() -> None:
        recorder = AsyncRecordWriter(
            tmp_path / "prefix.jsonl", max_records=1, max_bytes=1_000_000
        )
        await recorder.start()
        receiver = ObservationReceiver(ContractParser(CONTRACT_ROOT), recorder=recorder)
        server, host, port = await _start(receiver)
        header, observation = _fixture_lines()

        await _send(host, port, (header + observation,))
        snapshot = await recorder.close()
        server.close()
        await server.wait_closed()

        assert receiver.state.observation is not None
        assert receiver.state.observation.sequence == 1
        assert receiver.snapshot.records_accepted == 2
        assert snapshot.reason == "limit_reached"
        assert (tmp_path / "prefix.jsonl").read_bytes() == header

    asyncio.run(exercise())


def test_receiver_preserves_sequence_across_reconnection() -> None:
    async def exercise() -> None:
        receiver = ObservationReceiver(ContractParser(CONTRACT_ROOT))
        server, host, port = await _start(receiver)
        header, observation = _fixture_lines()

        await _send(host, port, (header + observation,))
        await _send(host, port, (header + _observation(3, 3.0),))
        server.close()
        await server.wait_closed()

        assert receiver.state.observation is not None
        assert receiver.state.observation.sequence == 3
        assert receiver.state.connection_index == 2
        assert receiver.state.missing_sequences == 1

    asyncio.run(exercise())


def test_receiver_discards_partial_line() -> None:
    async def exercise() -> None:
        receiver = ObservationReceiver(ContractParser(CONTRACT_ROOT))
        server, host, port = await _start(receiver)
        header, _ = _fixture_lines()

        await _send(host, port, (header + b'{"partial":',))
        server.close()
        await server.wait_closed()

        assert receiver.snapshot.partial_lines_discarded == 1
        assert receiver.snapshot.records_accepted == 1

    asyncio.run(exercise())


def test_receiver_rejects_additional_producer() -> None:
    async def exercise() -> None:
        receiver = ObservationReceiver(
            ContractParser(CONTRACT_ROOT), header_timeout_s=1
        )
        server, host, port = await _start(receiver)
        first_reader, first_writer = await asyncio.open_connection(host, port)
        await asyncio.sleep(0)
        second_reader, second_writer = await asyncio.open_connection(host, port)

        assert await asyncio.wait_for(second_reader.read(), timeout=1) == b""
        assert receiver.snapshot.connections_rejected == 1
        first_writer.close()
        await first_writer.wait_closed()
        second_writer.close()
        await second_writer.wait_closed()
        del first_reader
        server.close()
        await server.wait_closed()

    asyncio.run(exercise())
