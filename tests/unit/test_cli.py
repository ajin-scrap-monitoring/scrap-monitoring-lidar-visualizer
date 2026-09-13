from pathlib import Path

import pytest

from scrap_monitoring_lidar_visualizer.cli import build_parser, main
from scrap_monitoring_lidar_visualizer.live import LiveConfig
from scrap_monitoring_lidar_visualizer.replay import ReplayConfig


def test_live_parser_requires_both_endpoints() -> None:
    parser = build_parser({})
    with pytest.raises(SystemExit) as caught:
        parser.parse_args(["live", "--tcp-host", "127.0.0.1"])
    assert caught.value.code == 2


def test_live_parser_reads_environment_configuration() -> None:
    parser = build_parser(
        {
            "LIDAR_VISUALIZER_TCP_HOST": "0.0.0.0",
            "LIDAR_VISUALIZER_TCP_PORT": "7000",
            "LIDAR_VISUALIZER_HTTP_HOST": "0.0.0.0",
            "LIDAR_VISUALIZER_HTTP_PORT": "8000",
            "LIDAR_VISUALIZER_CAMERA": "top",
            "LIDAR_VISUALIZER_WIDTH": "1280",
            "LIDAR_VISUALIZER_HEIGHT": "720",
            "LIDAR_VISUALIZER_RECORD_PATH": "/output/observations.ndjson",
            "LIDAR_VISUALIZER_RECORD_MAX_RECORDS": "100000",
            "LIDAR_VISUALIZER_RECORD_MAX_BYTES": "104857600",
        }
    )

    args = parser.parse_args(["live"])

    assert args.tcp_host == "0.0.0.0"
    assert args.tcp_port == 7000
    assert args.http_host == "0.0.0.0"
    assert args.http_port == 8000
    assert args.camera == "top"
    assert args.width == 1280
    assert args.height == 720
    assert args.record == Path("/output/observations.ndjson")
    assert args.record_max_records == 100000
    assert args.record_max_bytes == 104857600


def test_cli_arguments_override_environment_configuration() -> None:
    parser = build_parser(
        {
            "LIDAR_VISUALIZER_TCP_HOST": "environment-host",
            "LIDAR_VISUALIZER_TCP_PORT": "invalid",
            "LIDAR_VISUALIZER_HTTP_HOST": "environment-http-host",
            "LIDAR_VISUALIZER_HTTP_PORT": "9000",
            "LIDAR_VISUALIZER_CAMERA": "top",
        }
    )

    args = parser.parse_args(
        [
            "live",
            "--tcp-host",
            "cli-host",
            "--tcp-port",
            "7000",
            "--http-host",
            "cli-http-host",
            "--http-port",
            "8000",
            "--camera",
            "isometric",
        ]
    )

    assert args.tcp_host == "cli-host"
    assert args.tcp_port == 7000
    assert args.http_host == "cli-http-host"
    assert args.http_port == 8000
    assert args.camera == "isometric"


def test_replay_parser_reads_environment_configuration() -> None:
    parser = build_parser(
        {
            "LIDAR_VISUALIZER_OUTPUT_PATH": "/output/replay.mp4",
            "LIDAR_VISUALIZER_RUN_ID": "fixture-run-a",
            "LIDAR_VISUALIZER_START_S": "1.5",
            "LIDAR_VISUALIZER_END_S": "3.5",
            "LIDAR_VISUALIZER_TIME_SCALE": "2.0",
            "LIDAR_VISUALIZER_FPS": "20",
            "LIDAR_VISUALIZER_CAMERA": "top",
            "LIDAR_VISUALIZER_WIDTH": "1280",
            "LIDAR_VISUALIZER_HEIGHT": "720",
        }
    )

    args = parser.parse_args(["replay", "/input/observations.ndjson"])

    assert args.input == Path("/input/observations.ndjson")
    assert args.output == Path("/output/replay.mp4")
    assert args.run_id == "fixture-run-a"
    assert args.start == 1.5
    assert args.end == 3.5
    assert args.time_scale == 2.0
    assert args.fps == 20
    assert args.camera == "top"
    assert args.width == 1280
    assert args.height == 720


def test_parser_rejects_invalid_environment_number() -> None:
    parser = build_parser(
        {
            "LIDAR_VISUALIZER_TCP_HOST": "0.0.0.0",
            "LIDAR_VISUALIZER_TCP_PORT": "invalid",
            "LIDAR_VISUALIZER_HTTP_HOST": "0.0.0.0",
            "LIDAR_VISUALIZER_HTTP_PORT": "8000",
        }
    )

    with pytest.raises(SystemExit) as caught:
        parser.parse_args(["live"])

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
            ],
            environment={},
        )
        == 2
    )


def test_replay_parser_rejects_duration_and_time_scale() -> None:
    parser = build_parser({})
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

    assert main(["replay", str(recording)], environment={}) == 2
