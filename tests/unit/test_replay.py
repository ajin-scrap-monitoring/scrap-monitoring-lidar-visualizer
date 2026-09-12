from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scrap_monitoring_lidar_visualizer.limits import MAX_FRAMES
from scrap_monitoring_lidar_visualizer.replay import (
    ReplayConfig,
    ReplayError,
    build_selection,
    inspect_recording,
    iter_run_observations,
    prepare_replay,
    select_frames,
    select_run,
)

FIXTURE = Path("contracts/observation/v1/fixtures/observation.v1.jsonl")


def _fixture_documents() -> tuple[dict[str, Any], dict[str, Any]]:
    header_line, observation_line = FIXTURE.read_text(encoding="utf-8").splitlines()
    return json.loads(header_line), json.loads(observation_line)


def _line(document: dict[str, Any]) -> bytes:
    return json.dumps(document, separators=(",", ":")).encode() + b"\n"


def _recording(tmp_path: Path, records: list[dict[str, Any]]) -> Path:
    path = tmp_path / "recording.jsonl"
    path.write_bytes(b"".join(_line(record) for record in records))
    return path


def _observation(
    source: dict[str, Any], sequence: int, elapsed_s: float
) -> dict[str, Any]:
    result = json.loads(json.dumps(source))
    result["sequence"] = sequence
    result["scenario"]["elapsed_s"] = elapsed_s
    return result


def test_recording_inventory_preserves_repeated_header_state(tmp_path: Path) -> None:
    header, observation = _fixture_documents()
    path = _recording(
        tmp_path,
        [
            header,
            _observation(observation, 1, 1.0),
            header,
            _observation(observation, 3, 3.0),
        ],
    )

    summaries = inspect_recording(path)
    states = tuple(iter_run_observations(path, "fixture-run-a"))

    assert len(summaries) == 1
    assert summaries[0].observation_count == 2
    assert summaries[0].first_header_offset == 0
    assert summaries[0].first_elapsed_s == 1.0
    assert summaries[0].last_elapsed_s == 3.0
    assert [state.observation.sequence for state in states] == [1, 3]
    assert states[-1].missing_sequences == 1


def test_multiple_runs_require_an_explicit_run_id(tmp_path: Path) -> None:
    header, observation = _fixture_documents()
    second_header = json.loads(json.dumps(header))
    second_header["run_id"] = "fixture-run-b"
    second_observation = _observation(observation, 1, 2.0)
    second_observation["run_id"] = "fixture-run-b"
    path = _recording(
        tmp_path,
        [header, observation, second_header, second_observation],
    )
    summaries = inspect_recording(path)

    with pytest.raises(ReplayError, match="--run-id is required"):
        select_run(summaries, None)

    assert select_run(summaries, "fixture-run-b").observation_count == 1


def test_frame_selection_uses_latest_sequence_at_same_time(tmp_path: Path) -> None:
    header, observation = _fixture_documents()
    path = _recording(
        tmp_path,
        [
            header,
            _observation(observation, 1, 1.0),
            _observation(observation, 2, 2.0),
            _observation(observation, 3, 2.0),
            _observation(observation, 4, 3.0),
        ],
    )
    run = select_run(inspect_recording(path), None)
    selection = build_selection(
        run,
        start_s=1.0,
        end_s=3.0,
        duration_s=2.0,
        time_scale=None,
        fps=2,
    )

    frames = tuple(
        select_frames(
            iter_run_observations(path, run.header.run_id), selection.frame_times
        )
    )

    assert [frame.time.simulation_s for frame in frames] == [1.0, 1.5, 2.0, 2.5]
    assert [frame.state.observation.sequence for frame in frames] == [1, 1, 3, 3]


def test_replay_window_rejects_invalid_ranges_and_limits(tmp_path: Path) -> None:
    header, observation = _fixture_documents()
    path = _recording(
        tmp_path,
        [header, observation, _observation(observation, 2, 2.0)],
    )
    run = select_run(inspect_recording(path), None)

    with pytest.raises(ReplayError, match="mutually exclusive"):
        build_selection(
            run,
            start_s=None,
            end_s=None,
            duration_s=1.0,
            time_scale=1.0,
            fps=10,
        )
    with pytest.raises(ReplayError, match="before the first"):
        build_selection(
            run,
            start_s=0.0,
            end_s=None,
            duration_s=None,
            time_scale=None,
            fps=10,
        )
    with pytest.raises(ReplayError, match="frame count"):
        build_selection(
            run,
            start_s=None,
            end_s=None,
            duration_s=(MAX_FRAMES + 1) / 10,
            time_scale=None,
            fps=10,
        )


def test_prepare_replay_rejects_interval_without_observation(tmp_path: Path) -> None:
    header, observation = _fixture_documents()
    path = _recording(
        tmp_path,
        [
            header,
            _observation(observation, 1, 1.0),
            _observation(observation, 2, 2.0),
        ],
    )

    with pytest.raises(ReplayError, match="contains no observation"):
        prepare_replay(
            ReplayConfig(
                input_path=path,
                output_path=tmp_path / "video.mp4",
                start_s=1.2,
                end_s=1.8,
            )
        )


def test_recording_rejects_incomplete_and_invalid_sequence(tmp_path: Path) -> None:
    header, observation = _fixture_documents()
    incomplete = tmp_path / "incomplete.jsonl"
    incomplete.write_bytes(_line(header) + b'{"type":')
    with pytest.raises(ReplayError, match="trailing LF"):
        inspect_recording(incomplete)

    duplicate = _recording(tmp_path, [header, observation, observation])
    with pytest.raises(ReplayError, match="sequence must increase"):
        inspect_recording(duplicate)
