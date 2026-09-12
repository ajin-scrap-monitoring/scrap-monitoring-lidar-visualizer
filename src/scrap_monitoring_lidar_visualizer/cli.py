"""Command-line entry point for live and replay operation."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

from scrap_monitoring_lidar_visualizer.live import LiveConfig, run_live


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lidar-visualizer")
    subparsers = parser.add_subparsers(dest="mode", required=True)
    live = subparsers.add_parser("live")
    live.add_argument("--tcp-host", required=True)
    live.add_argument("--tcp-port", required=True, type=int)
    live.add_argument("--http-host", required=True)
    live.add_argument("--http-port", required=True, type=int)
    live.add_argument("--camera", choices=("isometric", "top"), default="isometric")
    live.add_argument("--width", type=int, default=640)
    live.add_argument("--height", type=int, default=360)
    live.add_argument("--record", type=Path)
    live.add_argument("--record-max-records", type=int)
    live.add_argument("--record-max-bytes", type=int)
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(arguments)
    if args.mode != "live":
        parser.error("unsupported mode")
    config = LiveConfig(
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
    try:
        config.validate()
        return asyncio.run(run_live(config))
    except (OSError, ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
