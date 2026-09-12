"""Validate the headless rendering and video encoding runtime."""

from __future__ import annotations

import argparse
import json
import math
import os
import resource
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pyvista as pv
import vtk
from numpy.typing import NDArray

from scrap_monitoring_lidar_visualizer.limits import (
    DEFAULT_FPS,
    DEFAULT_FRAME_HEIGHT,
    DEFAULT_FRAME_WIDTH,
    MAX_FPS,
    MAX_FRAME_HEIGHT,
    MAX_FRAME_WIDTH,
    MAX_FRAMES,
    MAX_GRID_POINTS,
)

EXPECTED_RENDER_WINDOW = "vtkOSOpenGLRenderWindow"


@dataclass(frozen=True)
class ProbeConfig:
    """Bounded settings for the runtime probe."""

    width: int = DEFAULT_FRAME_WIDTH
    height: int = DEFAULT_FRAME_HEIGHT
    fps: int = DEFAULT_FPS
    frame_count: int = 10
    grid_x: int = 33
    grid_y: int = 25

    def validate(self) -> None:
        for name, value in asdict(self).items():
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.width > MAX_FRAME_WIDTH or self.height > MAX_FRAME_HEIGHT:
            raise ValueError("resolution exceeds the configured limit")
        if self.width % 2 or self.height % 2:
            raise ValueError("width and height must be even for yuv420p")
        if self.fps > MAX_FPS:
            raise ValueError("fps exceeds the configured limit")
        if self.frame_count > MAX_FRAMES:
            raise ValueError("frame count exceeds the configured limit")
        if self.grid_x < 2 or self.grid_y < 2:
            raise ValueError("grid dimensions must be at least two")
        if self.grid_x * self.grid_y > MAX_GRID_POINTS:
            raise ValueError("grid point count exceeds the configured limit")


@dataclass(frozen=True)
class ProbeResult:
    """Machine-readable evidence from one runtime probe."""

    display_present: bool
    euid: int
    gpu_device_present: bool
    render_window: str
    python_version: str
    pyvista_version: str
    vtk_version: str
    ffmpeg_version: str
    width: int
    height: int
    fps: int
    frame_count: int
    grid_points: int
    render_seconds: float
    encode_seconds: float
    max_rss_mib: float
    frame_path: str
    video_path: str


def synthetic_surface(x_count: int = 33, y_count: int = 25) -> pv.StructuredGrid:
    """Create a public deterministic surface for the environment probe."""
    x_values = np.linspace(-3.0, 3.0, x_count)
    y_values = np.linspace(-2.0, 2.0, y_count)
    x_grid, y_grid = np.meshgrid(x_values, y_values, indexing="xy")
    z_grid = 0.25 + 0.65 * np.exp(-0.24 * (x_grid**2 + y_grid**2))
    return pv.StructuredGrid(x_grid, y_grid, z_grid)


def ffmpeg_command(config: ProbeConfig, output_path: Path) -> list[str]:
    """Return the bounded raw-frame encoder command."""
    config.validate()
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pixel_format",
        "rgb24",
        "-video_size",
        f"{config.width}x{config.height}",
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
        str(output_path),
    ]


def _frame(plotter: pv.Plotter, config: ProbeConfig, index: int) -> NDArray[np.uint8]:
    angle = math.radians(35.0 + index * 2.0)
    plotter.camera_position = [
        (7.5 * math.cos(angle), 7.5 * math.sin(angle), 5.2),
        (0.0, 0.0, 0.2),
        (0.0, 0.0, 1.0),
    ]
    plotter.render()
    image = plotter.screenshot(return_img=True)
    if image is None or image.shape != (config.height, config.width, 3):
        raise RuntimeError("renderer returned an unexpected frame shape")
    return np.ascontiguousarray(image, dtype=np.uint8)


def _ffprobe(video_path: Path, config: ProbeConfig) -> None:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-count_frames",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,width,height,nb_read_frames",
        "-of",
        "json",
        str(video_path),
    ]
    output = subprocess.run(
        command, check=True, capture_output=True, text=True, timeout=30
    )
    payload: dict[str, Any] = json.loads(output.stdout)
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
    if stream != expected:
        raise RuntimeError(f"unexpected ffprobe result: {stream!r}")


def _runtime_preconditions() -> None:
    if "DISPLAY" in os.environ:
        raise RuntimeError("DISPLAY must be absent")
    if os.geteuid() == 0:
        raise RuntimeError("runtime probe must not run as root")
    if _gpu_device_present():
        raise RuntimeError("runtime probe must not have a GPU device")


def _gpu_device_present() -> bool:
    return Path("/dev/dri").exists() or any(Path("/dev").glob("nvidia*"))


def run_probe(output_dir: Path, config: ProbeConfig) -> ProbeResult:
    """Render a PNG and stream a short MP4 through FFmpeg."""
    config.validate()
    _runtime_preconditions()
    output_dir.mkdir(parents=True, exist_ok=False)
    frame_path = output_dir / "frame.png"
    video_path = output_dir / "probe.mp4"

    plotter = pv.Plotter(off_screen=True, window_size=[config.width, config.height])
    plotter.set_background("#101820")  # type: ignore[arg-type]
    plotter.add_mesh(
        synthetic_surface(config.grid_x, config.grid_y),
        color="#D6A85F",
        smooth_shading=False,
    )
    plotter.add_mesh(pv.Box(bounds=(-3.2, 3.2, -2.2, 2.2, 0.0, 0.06)), color="#3A4652")
    plotter.add_axes()  # type: ignore[call-arg]
    render_window = type(plotter.render_window).__name__
    if render_window != EXPECTED_RENDER_WINDOW:
        plotter.close()
        raise RuntimeError(f"unexpected render window: {render_window}")

    encode_started = time.perf_counter()
    process = subprocess.Popen(
        ffmpeg_command(config, video_path),
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    if process.stdin is None or process.stderr is None:
        plotter.close()
        raise RuntimeError("failed to open FFmpeg pipes")

    render_seconds = 0.0
    try:
        for index in range(config.frame_count):
            render_started = time.perf_counter()
            image = _frame(plotter, config, index)
            render_seconds += time.perf_counter() - render_started
            if index == 0:
                plotter.screenshot(str(frame_path))
            process.stdin.write(image.tobytes())
        process.stdin.close()
        returncode = process.wait(timeout=30)
        stderr = process.stderr.read().decode("utf-8", errors="replace")
    finally:
        plotter.close()
        if process.poll() is None:
            process.kill()
            process.wait()
    if returncode != 0:
        raise RuntimeError(
            f"FFmpeg failed with exit code {returncode}: {stderr.strip()}"
        )
    encode_seconds = time.perf_counter() - encode_started
    _ffprobe(video_path, config)

    ffmpeg_line = subprocess.run(
        ["ffmpeg", "-version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.splitlines()[0]
    result = ProbeResult(
        display_present="DISPLAY" in os.environ,
        euid=os.geteuid(),
        gpu_device_present=_gpu_device_present(),
        render_window=render_window,
        python_version=sys.version.split()[0],
        pyvista_version=pv.__version__,
        vtk_version=vtk.vtkVersion.GetVTKVersion(),
        ffmpeg_version=ffmpeg_line,
        width=config.width,
        height=config.height,
        fps=config.fps,
        frame_count=config.frame_count,
        grid_points=config.grid_x * config.grid_y,
        render_seconds=round(render_seconds, 6),
        encode_seconds=round(encode_seconds, 6),
        max_rss_mib=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 3),
        frame_path=frame_path.name,
        video_path=video_path.name,
    )
    (output_dir / "probe.json").write_text(
        json.dumps(asdict(result), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("/output/probe"))
    parser.add_argument("--frame-count", type=int, default=10)
    parser.add_argument("--grid-x", type=int, default=33)
    parser.add_argument("--grid-y", type=int, default=25)
    args = parser.parse_args()
    config = ProbeConfig(
        frame_count=args.frame_count,
        grid_x=args.grid_x,
        grid_y=args.grid_y,
    )
    result = run_probe(args.output, config)
    print(json.dumps(asdict(result), sort_keys=True))


if __name__ == "__main__":
    main()
