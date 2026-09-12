from pathlib import Path

import pytest

from scrap_monitoring_lidar_visualizer.cli import build_parser, main
from scrap_monitoring_lidar_visualizer.live import LiveConfig
from scrap_monitoring_lidar_visualizer.replay import ReplayConfig


def test_live_parser_requires_both_endpoints() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit) as caught:
        parser.parse_args(["live", "--tcp-host", "127.0.0.1"])
    assert caught.value.code == 2


def test_live_config_requires_complete_recording_limits() -> None:
    config = LiveConfig(
        tcp_host="127.0.0.1",
        tcp_port=7000,
        http_host="127.0.0.1",
        http_port=8000,
        record_path=Path("record.jsonl"),
    )
    with pytest.raises(ValueError, match="set together"):
        config.validate()


def test_live_config_rejects_shared_endpoint() -> None:
    assert (
        main(
            [
                "live",
                "--tcp-host",
                "127.0.0.1",
                "--tcp-port",
                "8000",
                "--http-host",
                "127.0.0.1",
                "--http-port",
                "8000",
            ]
        )
        == 2
    )


def test_replay_parser_rejects_duration_and_time_scale() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit) as caught:
        parser.parse_args(
            [
                "replay",
                "recording.jsonl",
                "--output",
                "video.mp4",
                "--duration",
                "1",
                "--time-scale",
                "2",
            ]
        )
    assert caught.value.code == 2


def test_replay_config_requires_exactly_one_output(tmp_path: Path) -> None:
    recording = tmp_path / "recording.jsonl"
    recording.write_bytes(
        Path("contracts/observation/v1/fixtures/observation.v1.jsonl").read_bytes()
    )

    with pytest.raises(ValueError, match="exactly one"):
        ReplayConfig(input_path=recording).validate()
    with pytest.raises(ValueError, match="exactly one"):
        ReplayConfig(
            input_path=recording,
            output_path=tmp_path / "video.mp4",
            http_host="127.0.0.1",
            http_port=8000,
        ).validate()


def test_replay_cli_reports_missing_output(tmp_path: Path) -> None:
    recording = tmp_path / "recording.jsonl"
    recording.write_bytes(
        Path("contracts/observation/v1/fixtures/observation.v1.jsonl").read_bytes()
    )

    assert main(["replay", str(recording)]) == 2
