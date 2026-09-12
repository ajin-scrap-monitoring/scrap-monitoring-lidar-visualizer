"""Command-line entry point for live and replay operation."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

from scrap_monitoring_lidar_visualizer.live import LiveConfig, run_live
from scrap_monitoring_lidar_visualizer.replay import ReplayConfig, run_replay


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
    replay = subparsers.add_parser("replay")
    replay.add_argument("input", type=Path)
    replay.add_argument("--output", type=Path)
    replay.add_argument("--http-host")
    replay.add_argument("--http-port", type=int)
    replay.add_argument("--run-id")
    replay.add_argument("--start", type=float)
    replay.add_argument("--end", type=float)
    timing = replay.add_mutually_exclusive_group()
    timing.add_argument("--duration", type=float)
    timing.add_argument("--time-scale", type=float)
    replay.add_argument("--fps", type=int, default=10)
    replay.add_argument("--camera", choices=("isometric", "top"), default="isometric")
    replay.add_argument("--width", type=int, default=640)
    replay.add_argument("--height", type=int, default=360)
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    parser = build_parser()
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
