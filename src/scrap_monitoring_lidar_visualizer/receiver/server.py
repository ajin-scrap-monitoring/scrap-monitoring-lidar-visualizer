"""Single-producer TCP receiver with strict connection boundaries."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, replace

from scrap_monitoring_lidar_visualizer.contracts import (
    ContractError,
    ContractParser,
    Header,
    Observation,
)
from scrap_monitoring_lidar_visualizer.recording import AsyncRecordWriter
from scrap_monitoring_lidar_visualizer.state import (
    ExecutionState,
    StateError,
    accept_header,
    accept_observation,
    disconnect,
)

from .framing import LineFramer, LineFramingError


@dataclass(frozen=True, slots=True)
class ReceiverSnapshot:
    connections_accepted: int = 0
    connections_rejected: int = 0
    records_accepted: int = 0
    records_rejected: int = 0
    partial_lines_discarded: int = 0
    last_error: str | None = None


class _ConnectionRejected(ValueError):
    pass


class ObservationReceiver:
    def __init__(
        self,
        parser: ContractParser,
        *,
        recorder: AsyncRecordWriter | None = None,
        header_timeout_s: float = 5.0,
        on_observation: Callable[[ExecutionState], None] | None = None,
    ) -> None:
        if header_timeout_s <= 0:
            raise ValueError("header_timeout_s must be positive")
        self._parser = parser
        self._recorder = recorder
        self._header_timeout_s = header_timeout_s
        self._on_observation = on_observation
        self._active = False
        self.state = ExecutionState()
        self.snapshot = ReceiverSnapshot()

    async def handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        if self._active:
            self.snapshot = replace(
                self.snapshot,
                connections_rejected=self.snapshot.connections_rejected + 1,
                last_error="additional producer rejected",
            )
            writer.close()
            await writer.wait_closed()
            return
        self._active = True
        accepted_header = False
        framer = LineFramer()
        self.snapshot = replace(
            self.snapshot,
            connections_accepted=self.snapshot.connections_accepted + 1,
        )
        try:
            pending = await asyncio.wait_for(
                self._read_header(reader, framer), timeout=self._header_timeout_s
            )
            accepted_header = True
            for raw_line in pending:
                self._process_observation(raw_line)
            while data := await reader.read(65_536):
                for raw_line in framer.feed(data):
                    self._process_observation(raw_line)
        except TimeoutError:
            self._connection_error("header timeout")
        except (
            ContractError,
            LineFramingError,
            StateError,
            _ConnectionRejected,
        ) as error:
            self._connection_error(str(error))
        finally:
            if framer.discard_partial():
                self.snapshot = replace(
                    self.snapshot,
                    partial_lines_discarded=self.snapshot.partial_lines_discarded + 1,
                )
            if accepted_header:
                self.state = disconnect(self.state).state
                if self._on_observation is not None:
                    self._on_observation(self.state)
            self._active = False
            writer.close()
            await writer.wait_closed()

    async def _read_header(
        self, reader: asyncio.StreamReader, framer: LineFramer
    ) -> tuple[bytes, ...]:
        while data := await reader.read(65_536):
            records = framer.feed(data)
            if not records:
                continue
            parsed = self._parser.parse_line(records[0])
            if not isinstance(parsed.value, Header):
                raise _ConnectionRejected("first record must be a stream header")
            self.state = accept_header(self.state, parsed.value).state
            self._accept_raw(parsed.raw_line)
            return records[1:]
        raise _ConnectionRejected("connection ended before a stream header")

    def _process_observation(self, raw_line: bytes) -> None:
        try:
            parsed = self._parser.parse_line(raw_line)
            if not isinstance(parsed.value, Observation):
                raise StateError(
                    "record_type", "header is only valid as the first record"
                )
            self.state = accept_observation(self.state, parsed.value).state
        except (ContractError, StateError) as error:
            self.snapshot = replace(
                self.snapshot,
                records_rejected=self.snapshot.records_rejected + 1,
                last_error=str(error),
            )
            return
        self._accept_raw(parsed.raw_line)
        if self._on_observation is not None:
            self._on_observation(self.state)

    def _accept_raw(self, raw_line: bytes) -> None:
        self.snapshot = replace(
            self.snapshot,
            records_accepted=self.snapshot.records_accepted + 1,
        )
        if self._recorder is not None:
            self._recorder.submit(raw_line)

    def _connection_error(self, message: str) -> None:
        self.snapshot = replace(self.snapshot, last_error=message)
