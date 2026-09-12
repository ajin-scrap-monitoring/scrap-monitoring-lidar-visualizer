"""Sequentially validate recordings and expose bounded run metadata."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from scrap_monitoring_lidar_visualizer.contracts import (
    ContractError,
    ContractParser,
    Header,
    Observation,
)
from scrap_monitoring_lidar_visualizer.contracts.parser import MAX_RECORD_BYTES
from scrap_monitoring_lidar_visualizer.state import (
    ExecutionState,
    StateError,
    accept_header,
    accept_observation,
    disconnect,
)

from .models import ReplayObservation, RunSummary

MAX_REPLAY_RUNS = 10_000


class ReplayError(ValueError):
    """A recording or replay selection error."""


@dataclass(frozen=True, slots=True)
class _ValidatedRecord:
    offset: int
    kind: Literal["header", "observation"]
    state: ExecutionState


class _RecordingState:
    def __init__(self) -> None:
        self._states: dict[str, ExecutionState] = {}
        self._active_run_id: str | None = None

    def accept(self, value: Header | Observation, offset: int) -> _ValidatedRecord:
        try:
            if isinstance(value, Header):
                self._disconnect_active()
                previous = self._states.get(value.run_id, ExecutionState())
                state = accept_header(previous, value).state
                if (
                    value.run_id not in self._states
                    and len(self._states) >= MAX_REPLAY_RUNS
                ):
                    raise ReplayError(
                        "recording run count exceeds the configured limit"
                    )
                self._states[value.run_id] = state
                self._active_run_id = value.run_id
                return _ValidatedRecord(offset, "header", state)
            if self._active_run_id is None:
                raise StateError("header_required", "observation requires a header")
            state = accept_observation(self._states[self._active_run_id], value).state
            self._states[self._active_run_id] = state
            return _ValidatedRecord(offset, "observation", state)
        except StateError as error:
            raise ReplayError(f"invalid recording at byte {offset}: {error}") from error

    def _disconnect_active(self) -> None:
        if self._active_run_id is None:
            return
        active = self._states[self._active_run_id]
        if active.connected:
            self._states[self._active_run_id] = disconnect(active).state


def _validated_records(
    path: Path, parser: ContractParser
) -> Iterator[_ValidatedRecord]:
    state = _RecordingState()
    try:
        with path.open("rb") as stream:
            while True:
                offset = stream.tell()
                raw_line = stream.readline(MAX_RECORD_BYTES + 1)
                if not raw_line:
                    break
                if len(raw_line) > MAX_RECORD_BYTES:
                    raise ReplayError(
                        f"invalid recording at byte {offset}: record byte limit exceeded"
                    )
                try:
                    value = parser.parse_line(raw_line).value
                except ContractError as error:
                    raise ReplayError(
                        f"invalid recording at byte {offset}: {error}"
                    ) from error
                yield state.accept(value, offset)
    except OSError as error:
        raise ReplayError(f"cannot read recording: {path}") from error


def inspect_recording(
    path: Path, parser: ContractParser | None = None
) -> tuple[RunSummary, ...]:
    if not path.is_file():
        raise ReplayError(f"recording is not a file: {path}")
    summaries: dict[str, RunSummary] = {}
    for record in _validated_records(path, parser or ContractParser()):
        state = record.state
        assert state.header is not None
        run_id = state.header.run_id
        if run_id not in summaries:
            summaries[run_id] = RunSummary(
                header=state.header,
                first_header_offset=record.offset,
            )
        if record.kind == "observation":
            assert state.observation is not None
            elapsed_s = state.observation.scenario.elapsed_s
            summary = summaries[run_id]
            summaries[run_id] = replace(
                summary,
                observation_count=summary.observation_count + 1,
                first_elapsed_s=(
                    elapsed_s
                    if summary.first_elapsed_s is None
                    else summary.first_elapsed_s
                ),
                last_elapsed_s=elapsed_s,
            )
    if not summaries:
        raise ReplayError("recording contains no stream header")
    return tuple(summaries.values())


def iter_run_observations(
    path: Path,
    run_id: str,
    parser: ContractParser | None = None,
) -> Iterator[ReplayObservation]:
    for record in _validated_records(path, parser or ContractParser()):
        if record.kind != "observation":
            continue
        state = record.state
        assert state.header is not None
        assert state.observation is not None
        if state.header.run_id == run_id:
            yield ReplayObservation(
                header=state.header,
                observation=state.observation,
                missing_sequences=state.missing_sequences,
            )
