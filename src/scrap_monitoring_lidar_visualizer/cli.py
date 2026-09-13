"""Command-line entry point for live and replay operation."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from scrap_monitoring_lidar_visualizer.live import LiveConfig, run_live
from scrap_monitoring_lidar_visualizer.replay import ReplayConfig, run_replay

ENV_PREFIX = "LIDAR_VISUALIZER_"


def _environment_argument(
    environment: Mapping[str, str],
    name: str,
    default: Any = None,
    *,
    required: bool = False,
) -> dict[str, Any]:
    value = environment.get(f"{ENV_PREFIX}{name}", default)
    options: dict[str, Any] = {
        "default": value,
        "help": f"environment: {ENV_PREFIX}{name}",
    }
    if required:
        options["required"] = value is None
    return options


def build_parser(
    environment: Mapping[str, str] | None = None,
) -> argparse.ArgumentParser:
    values = os.environ if environment is None else environment
    parser = argparse.ArgumentParser(prog="lidar-visualizer")
    subparsers = parser.add_subparsers(dest="mode", required=True)
    live = subparsers.add_parser("live")
    live.add_argument(
        "--tcp-host",
        **_environment_argument(values, "TCP_HOST", required=True),
    )
    live.add_argument(
        "--tcp-port",
        type=int,
        **_environment_argument(values, "TCP_PORT", required=True),
    )
    live.add_argument(
        "--http-host",
        **_environment_argument(values, "HTTP_HOST", required=True),
    )
    live.add_argument(
        "--http-port",
        type=int,
        **_environment_argument(values, "HTTP_PORT", required=True),
    )
    live.add_argument(
        "--camera",
        choices=("isometric", "top"),
        **_environment_argument(values, "CAMERA", "isometric"),
    )
    live.add_argument(
        "--width",
        type=int,
        **_environment_argument(values, "WIDTH", 640),
    )
    live.add_argument(
        "--height",
        type=int,
        **_environment_argument(values, "HEIGHT", 360),
    )
    live.add_argument(
        "--record",
        type=Path,
        **_environment_argument(values, "RECORD_PATH"),
    )
    live.add_argument(
        "--record-max-records",
        type=int,
        **_environment_argument(values, "RECORD_MAX_RECORDS"),
    )
    live.add_argument(
        "--record-max-bytes",
        type=int,
        **_environment_argument(values, "RECORD_MAX_BYTES"),
    )
    replay = subparsers.add_parser("replay")
    replay.add_argument("input", type=Path)
    replay.add_argument(
        "--output",
        type=Path,
        **_environment_argument(values, "OUTPUT_PATH"),
    )
    replay.add_argument(
        "--http-host",
        **_environment_argument(values, "HTTP_HOST"),
    )
    replay.add_argument(
        "--http-port",
        type=int,
        **_environment_argument(values, "HTTP_PORT"),
    )
    replay.add_argument(
        "--run-id",
        **_environment_argument(values, "RUN_ID"),
    )
    replay.add_argument(
        "--start",
        type=float,
        **_environment_argument(values, "START_S"),
    )
    replay.add_argument(
        "--end",
        type=float,
        **_environment_argument(values, "END_S"),
    )
    timing = replay.add_mutually_exclusive_group()
    timing.add_argument(
        "--duration",
        type=float,
        **_environment_argument(values, "DURATION_S"),
    )
    timing.add_argument(
        "--time-scale",
        type=float,
        **_environment_argument(values, "TIME_SCALE"),
    )
    replay.add_argument(
        "--fps",
        type=int,
        **_environment_argument(values, "FPS", 10),
    )
    replay.add_argument(
        "--camera",
        choices=("isometric", "top"),
        **_environment_argument(values, "CAMERA", "isometric"),
    )
    replay.add_argument(
        "--width",
        type=int,
        **_environment_argument(values, "WIDTH", 640),
    )
    replay.add_argument(
        "--height",
        type=int,
        **_environment_argument(values, "HEIGHT", 360),
    )
    return parser


def main(
    arguments: Sequence[str] | None = None,
    *,
    environment: Mapping[str, str] | None = None,
) -> int:
    parser = build_parser(environment)
    args = parser.parse_args(arguments)
    try:
        if args.mode == "live":
            live_config = LiveConfig(
                tcp_host=args.tcp_host,
                tcp_port=args.tcp_port,
                http_host=args.http_host,
                http_port=args.http_port,
                camera=args.camera,
                width=args.width,
                height=args.height,
                record_path=args.record,
                record_max_records=args.record_max_records,
                record_max_bytes=args.record_max_bytes,
            )
            live_config.validate()
            return asyncio.run(run_live(live_config))
        replay_config = ReplayConfig(
            input_path=args.input,
            output_path=args.output,
            http_host=args.http_host,
            http_port=args.http_port,
            run_id=args.run_id,
            start_s=args.start,
            end_s=args.end,
            duration_s=args.duration,
            time_scale=args.time_scale,
            fps=args.fps,
            camera=args.camera,
            width=args.width,
            height=args.height,
        )
        return run_replay(replay_config)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
