from pathlib import Path

import pytest

from scrap_monitoring_lidar_visualizer.cli import build_parser, main
from scrap_monitoring_lidar_visualizer.live import LiveConfig


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
