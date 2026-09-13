"""Command-line entry point for live browser visualization."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from collections.abc import Mapping, Sequence
from typing import Any

from scrap_monitoring_lidar_visualizer.limits import (
    DEFAULT_FRAME_HEIGHT,
    DEFAULT_FRAME_WIDTH,
)
from scrap_monitoring_lidar_visualizer.live import LiveConfig, run_live

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
        **_environment_argument(values, "WIDTH", DEFAULT_FRAME_WIDTH),
    )
    live.add_argument(
        "--height",
        type=int,
        **_environment_argument(values, "HEIGHT", DEFAULT_FRAME_HEIGHT),
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
        live_config = LiveConfig(
            tcp_host=args.tcp_host,
            tcp_port=args.tcp_port,
            http_host=args.http_host,
            http_port=args.http_port,
            camera=args.camera,
            width=args.width,
            height=args.height,
        )
        live_config.validate()
        return asyncio.run(run_live(live_config))
    except (OSError, ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
