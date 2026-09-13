"""Stream rendered PNG frames to a protected H.264 MP4 output."""

from __future__ import annotations

import json
import os
import select
import subprocess
import time
import uuid
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scrap_monitoring_lidar_visualizer.limits import MAX_FPS, MAX_FRAMES
from scrap_monitoring_lidar_visualizer.preview import LatestFrameStore
from scrap_monitoring_lidar_visualizer.rendering import RenderConfig
from scrap_monitoring_lidar_visualizer.rendering.worker import (
    LatestRenderWorker,
    RenderRequest,
)
from scrap_monitoring_lidar_visualizer.replay.models import SelectedFrame


@dataclass(frozen=True, slots=True)
class VideoConfig:
    width: int
    height: int
    fps: int
    frame_count: int

    def validate(self) -> None:
        RenderConfig(width=self.width, height=self.height).validate()
        if self.width % 2 or self.height % 2:
            raise ValueError("MP4 width and height must be even for yuv420p")
        if self.fps <= 0 or self.fps > MAX_FPS:
            raise ValueError(f"fps must be between 1 and {MAX_FPS}")
        if self.frame_count <= 0 or self.frame_count > MAX_FRAMES:
            raise ValueError(f"frame count must be between 1 and {MAX_FRAMES}")


@dataclass(frozen=True, slots=True)
class VideoResult:
    path: Path
    codec: str
    width: int
    height: int
    fps: int
    frame_count: int


def ffmpeg_command(
    config: VideoConfig, output_path: Path, *, executable: str = "ffmpeg"
) -> list[str]:
    config.validate()
    return [
        executable,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "image2pipe",
        "-vcodec",
        "png",
        "-framerate",
        str(config.fps),
        "-i",
        "pipe:0",
        "-an",
        "-frames:v",
        str(config.frame_count),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-n",
        str(output_path),
    ]


def _temporary_path(parent: Path, output_name: str, suffix: str) -> Path:
    for _ in range(100):
        candidate = parent / f".{output_name}.{uuid.uuid4().hex}.{suffix}"
        if not os.path.lexists(candidate):
            return candidate
    raise RuntimeError("cannot allocate a temporary output path")


def _probe_video(
    path: Path,
    config: VideoConfig,
    *,
    executable: str = "ffprobe",
) -> VideoResult:
    command = [
        executable,
        "-v",
        "error",
        "-count_frames",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,width,height,nb_read_frames",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        payload: dict[str, Any] = json.loads(completed.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as error:
        raise RuntimeError("ffprobe validation failed") from error
    streams = payload.get("streams")
    if not isinstance(streams, list) or len(streams) != 1:
        raise RuntimeError("ffprobe did not return exactly one video stream")
    stream = streams[0]
    expected = {
        "codec_name": "h264",
        "width": config.width,
        "height": config.height,
        "nb_read_frames": str(config.frame_count),
    }
    if not isinstance(stream, dict) or any(
        stream.get(key) != value for key, value in expected.items()
    ):
        raise RuntimeError(f"unexpected ffprobe result: {stream!r}")
    return VideoResult(
        path=path,
        codec="h264",
        width=config.width,
        height=config.height,
        fps=config.fps,
        frame_count=config.frame_count,
    )


def _write_with_timeout(stream: Any, data: bytes, timeout_s: float = 60.0) -> None:
    descriptor = stream.fileno()
    os.set_blocking(descriptor, False)
    remaining = memoryview(data)
    deadline = time.monotonic() + timeout_s
    while remaining:
        timeout = deadline - time.monotonic()
        if timeout <= 0:
            raise TimeoutError("FFmpeg frame write timed out")
        _, writable, _ = select.select([], [descriptor], [], timeout)
        if not writable:
            raise TimeoutError("FFmpeg frame write timed out")
        try:
            written = os.write(descriptor, remaining)
        except BlockingIOError:
            continue
        remaining = remaining[written:]


def encode_png_frames(
    output_path: Path,
    frames: Iterable[bytes],
    config: VideoConfig,
    *,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
) -> VideoResult:
    config.validate()
    if output_path.suffix.lower() != ".mp4":
        raise ValueError("MP4 output path must use the .mp4 extension")
    if not output_path.parent.is_dir():
        raise ValueError("MP4 output parent directory does not exist")
    if os.path.lexists(output_path):
        raise FileExistsError(output_path)
    partial_path = _temporary_path(output_path.parent, output_path.name, "partial.mp4")
    log_path = _temporary_path(output_path.parent, output_path.name, "ffmpeg.log")
    process: subprocess.Popen[bytes] | None = None
    try:
        with log_path.open("x+b") as error_stream:
            try:
                process = subprocess.Popen(
                    ffmpeg_command(config, partial_path, executable=ffmpeg),
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=error_stream,
                )
            except OSError as error:
                raise RuntimeError("cannot start FFmpeg") from error
            if process.stdin is None:
                raise RuntimeError("cannot open FFmpeg input")
            count = 0
            try:
                for png in frames:
                    if count >= config.frame_count:
                        raise RuntimeError("renderer produced too many frames")
                    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
                        raise RuntimeError("renderer produced a non-PNG frame")
                    _write_with_timeout(process.stdin, png)
                    count += 1
                if count != config.frame_count:
                    raise RuntimeError(
                        f"renderer produced {count} of {config.frame_count} frames"
                    )
                process.stdin.close()
                process.stdin = None
                returncode = process.wait(timeout=60)
            except (BrokenPipeError, subprocess.TimeoutExpired, TimeoutError) as error:
                raise RuntimeError("FFmpeg did not accept all frames") from error
            if returncode != 0:
                error_stream.flush()
                error_stream.seek(0)
                message = (
                    error_stream.read(65_536).decode("utf-8", errors="replace").strip()
                )
                raise RuntimeError(
                    f"FFmpeg failed with exit code {returncode}: {message}"
                )
        result = _probe_video(partial_path, config, executable=ffprobe)
        try:
            os.link(partial_path, output_path)
        except FileExistsError:
            raise FileExistsError(output_path) from None
        partial_path.unlink()
        return VideoResult(
            path=output_path,
            codec=result.codec,
            width=result.width,
            height=result.height,
            fps=result.fps,
            frame_count=result.frame_count,
        )
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        partial_path.unlink(missing_ok=True)
        log_path.unlink(missing_ok=True)


def render_png_frames(
    frames: Iterable[SelectedFrame],
    config: RenderConfig,
    *,
    temp_dir: Path,
    timeout_s: float = 60.0,
) -> Iterator[bytes]:
    if timeout_s <= 0:
        raise ValueError("render timeout must be positive")
    store = LatestFrameStore()
    worker = LatestRenderWorker(store)
    worker.start()
    try:
        for frame in frames:
            state = frame.state
            before_revision = store.revision
            worker.submit(
                RenderRequest(
                    header=state.header,
                    observation=state.observation,
                    connected=False,
                    missing_sequences=state.missing_sequences,
                    config=config,
                    temp_dir=temp_dir,
                    connection_label="replay",
                    render_top_view=False,
                )
            )
            deadline = time.monotonic() + timeout_s
            while store.revision == before_revision:
                outcome = worker.poll()
                if outcome is not None and outcome.error is not None:
                    raise RuntimeError(f"renderer failed: {outcome.error}")
                if not worker.is_alive:
                    raise RuntimeError("renderer process stopped unexpectedly")
                if time.monotonic() >= deadline:
                    raise RuntimeError("renderer timed out")
                time.sleep(0.01)
            snapshot = store.get()
            if snapshot is None:
                raise RuntimeError("renderer returned no frame")
            yield snapshot.png
    finally:
        worker.close()
