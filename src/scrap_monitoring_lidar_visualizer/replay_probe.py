"""Exercise replay selection, rendering, MP4 and HTTP preview boundaries."""

from __future__ import annotations

import argparse
import asyncio
import json
import socket
from pathlib import Path

import uvicorn

from scrap_monitoring_lidar_visualizer.preview import (
    LatestFrameStore,
    create_preview_app,
)
from scrap_monitoring_lidar_visualizer.rendering.worker import LatestRenderWorker
from scrap_monitoring_lidar_visualizer.replay import (
    ReplayConfig,
    ReplayPreviewController,
    prepare_replay,
    run_replay,
)


async def _http_get(port: int, path: str) -> tuple[int, bytes]:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    writer.write(
        f"GET {path} HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n".encode()
    )
    await writer.drain()
    response = await reader.read()
    writer.close()
    await writer.wait_closed()
    head, body = response.split(b"\r\n\r\n", 1)
    status = int(head.decode("latin-1").split("\r\n", 1)[0].split()[1])
    return status, body


async def _preview_probe(input_path: Path, output_dir: Path) -> dict[str, object]:
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    port = int(listener.getsockname()[1])
    config = ReplayConfig(
        input_path=input_path,
        http_host="127.0.0.1",
        http_port=port,
        duration_s=0.2,
        fps=10,
    )
    selection = prepare_replay(config)
    frames = LatestFrameStore()
    worker = LatestRenderWorker(frames)
    worker.start()
    controller = ReplayPreviewController(config, selection, frames, worker)
    app = create_preview_app(frames, controller.status)
    server = uvicorn.Server(
        uvicorn.Config(app, lifespan="off", access_log=False, log_level="error")
    )
    server_task = asyncio.create_task(server.serve(sockets=[listener]))
    while not server.started:
        await asyncio.sleep(0.01)
    try:
        await controller.play()
        root_status, root_body = await _http_get(port, "/")
        frame_status, frame_body = await _http_get(port, "/frame.png")
        status_code, status_body = await _http_get(port, "/status")
        status = json.loads(status_body)
        if not frame_body.startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError("replay preview frame is not PNG")
        (output_dir / "replay-preview.png").write_bytes(frame_body)
        return {
            "root_status": root_status,
            "root_has_preview": b"/frame.png?revision=" in root_body,
            "frame_status": frame_status,
            "status_code": status_code,
            "playback_complete": status["playback_complete"],
            "playback_frame_count": status["playback_frame_count"],
            "rendered_sequence": status["rendered_sequence"],
        }
    finally:
        server.should_exit = True
        await server_task
        worker.close()


def run_probe(output_dir: Path, input_path: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=False)
    video_path = output_dir / "replay.mp4"
    run_replay(
        ReplayConfig(
            input_path=input_path,
            output_path=video_path,
            duration_s=0.3,
            fps=10,
        )
    )
    preview = asyncio.run(_preview_probe(input_path, output_dir))
    result: dict[str, object] = {
        "video_exists": video_path.is_file() and video_path.stat().st_size > 0,
        **preview,
    }
    (output_dir / "replay.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("/output/replay"))
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("/app/contracts/observation/v1/fixtures/observation.v1.jsonl"),
    )
    args = parser.parse_args()
    print(json.dumps(run_probe(args.output, args.input), sort_keys=True))


if __name__ == "__main__":
    main()
