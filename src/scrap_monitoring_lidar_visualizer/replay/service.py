"""Replay CLI configuration, preview playback and MP4 export orchestration."""

from __future__ import annotations

import asyncio
import json
import math
import os
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import uvicorn

from scrap_monitoring_lidar_visualizer.export import (
    VideoConfig,
    encode_png_frames,
    render_png_frames,
)
from scrap_monitoring_lidar_visualizer.limits import (
    DEFAULT_FPS,
    DEFAULT_FRAME_HEIGHT,
    DEFAULT_FRAME_WIDTH,
)
from scrap_monitoring_lidar_visualizer.preview import (
    LatestFrameStore,
    create_preview_app,
)
from scrap_monitoring_lidar_visualizer.rendering import RenderConfig
from scrap_monitoring_lidar_visualizer.rendering.worker import (
    LatestRenderWorker,
    RenderRequest,
)

from .models import ReplaySelection, SelectedFrame
from .reader import ReplayError, inspect_recording, iter_run_observations
from .schedule import build_selection, select_frames, select_run


@dataclass(frozen=True, slots=True)
class ReplayConfig:
    input_path: Path
    output_path: Path | None = None
    http_host: str | None = None
    http_port: int | None = None
    run_id: str | None = None
    start_s: float | None = None
    end_s: float | None = None
    duration_s: float | None = None
    time_scale: float | None = None
    fps: int = DEFAULT_FPS
    width: int = DEFAULT_FRAME_WIDTH
    height: int = DEFAULT_FRAME_HEIGHT
    camera: Literal["isometric", "top"] = "isometric"

    def validate(self) -> None:
        if not self.input_path.is_file():
            raise ReplayError(f"recording is not a file: {self.input_path}")
        preview_values = (self.http_host, self.http_port)
        preview_enabled = all(value is not None for value in preview_values)
        if any(value is not None for value in preview_values) and not preview_enabled:
            raise ReplayError("preview host and port must be set together")
        if (self.output_path is not None) == preview_enabled:
            raise ReplayError("select exactly one replay output: MP4 or HTTP preview")
        if self.http_host is not None and not self.http_host:
            raise ReplayError("preview host must not be empty")
        if self.http_port is not None and not (1 <= self.http_port <= 65_535):
            raise ReplayError("preview port must be between 1 and 65535")
        render_config = RenderConfig(
            width=self.width, height=self.height, camera=self.camera
        )
        render_config.validate()
        if self.output_path is not None:
            if self.input_path.resolve() == self.output_path.resolve():
                raise ReplayError("input and output paths must be different")
            VideoConfig(self.width, self.height, self.fps, 1).validate()
        elif self.fps <= 0:
            raise ReplayError("fps must be positive")
        for name, value in (
            ("start", self.start_s),
            ("end", self.end_s),
            ("duration", self.duration_s),
            ("time scale", self.time_scale),
        ):
            if value is not None and not math.isfinite(value):
                raise ReplayError(f"{name} must be finite")
        if self.duration_s is not None and self.time_scale is not None:
            raise ReplayError("duration and time scale are mutually exclusive")


def prepare_replay(config: ReplayConfig) -> ReplaySelection:
    config.validate()
    run = select_run(inspect_recording(config.input_path), config.run_id)
    selection = build_selection(
        run,
        start_s=config.start_s,
        end_s=config.end_s,
        duration_s=config.duration_s,
        time_scale=config.time_scale,
        fps=config.fps,
    )
    if not any(
        selection.start_s <= item.observation.scenario.elapsed_s <= selection.end_s
        for item in iter_run_observations(config.input_path, run.header.run_id)
    ):
        raise ReplayError("selected replay interval contains no observation")
    return selection


def _selected_frames(
    config: ReplayConfig, selection: ReplaySelection
) -> Iterator[SelectedFrame]:
    return select_frames(
        iter_run_observations(config.input_path, selection.run.header.run_id),
        selection.frame_times,
    )


class ReplayPreviewController:
    def __init__(
        self,
        config: ReplayConfig,
        selection: ReplaySelection,
        frames: LatestFrameStore,
        worker: LatestRenderWorker,
    ) -> None:
        self._config = config
        self._selection = selection
        self._frames = frames
        self._worker = worker
        self._frame_index: int | None = None
        self._sequence: int | None = None
        self._simulation_s: float | None = None
        self._missing_sequences = 0
        self._complete = False
        self._error: str | None = None

    def status(self) -> dict[str, Any]:
        return {
            "mode": "replay",
            "connected": False,
            "run_id": self._selection.run.header.run_id,
            "received_sequence": self._sequence,
            "missing_sequences": self._missing_sequences,
            "connection_index": None,
            "last_valid_received_at": None,
            "records_accepted": self._selection.run.observation_count,
            "records_rejected": 0,
            "recording": None,
            "playback_frame_index": self._frame_index,
            "playback_frame_count": len(self._selection.frame_times),
            "playback_simulation_s": self._simulation_s,
            "playback_complete": self._complete,
            "render_error": self._error or self._worker.last_error,
        }

    async def play(self) -> None:
        loop = asyncio.get_running_loop()
        started = loop.time()
        try:
            for selected in _selected_frames(self._config, self._selection):
                await asyncio.sleep(
                    max(0.0, started + selected.time.output_s - loop.time())
                )
                await self._render(selected)
            self._complete = True
        except Exception as error:
            self._error = str(error)
            raise

    async def _render(self, selected: SelectedFrame) -> None:
        state = selected.state
        before_revision = self._frames.revision
        self._worker.submit(
            RenderRequest(
                header=state.header,
                observation=state.observation,
                connected=False,
                missing_sequences=state.missing_sequences,
                config=RenderConfig(
                    width=self._config.width,
                    height=self._config.height,
                    camera=self._config.camera,
                ),
                connection_label="replay",
            )
        )
        deadline = asyncio.get_running_loop().time() + 60
        while self._frames.revision == before_revision:
            outcome = self._worker.poll()
            if outcome is not None and outcome.error is not None:
                raise RuntimeError(f"renderer failed: {outcome.error}")
            if not self._worker.is_alive:
                raise RuntimeError("renderer process stopped unexpectedly")
            if asyncio.get_running_loop().time() >= deadline:
                raise RuntimeError("renderer timed out")
            await asyncio.sleep(0.01)
        self._frame_index = selected.time.index
        self._sequence = state.observation.sequence
        self._simulation_s = selected.time.simulation_s
        self._missing_sequences = state.missing_sequences


async def run_replay_preview(config: ReplayConfig, selection: ReplaySelection) -> int:
    assert config.http_host is not None
    assert config.http_port is not None
    frames = LatestFrameStore()
    worker = LatestRenderWorker(frames)
    worker.start()
    controller = ReplayPreviewController(config, selection, frames, worker)
    app = create_preview_app(frames, controller.status)
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=config.http_host,
            port=config.http_port,
            access_log=False,
            log_level="info",
            timeout_keep_alive=5,
        )
    )

    async def playback() -> None:
        try:
            await controller.play()
        except Exception:
            server.should_exit = True
            raise

    task = asyncio.create_task(playback())
    try:
        await server.serve()
        if task.done():
            task.result()
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        worker.close()
    return 0


def run_replay(config: ReplayConfig) -> int:
    selection = prepare_replay(config)
    if config.output_path is None:
        return asyncio.run(run_replay_preview(config, selection))
    render_config = RenderConfig(
        width=config.width,
        height=config.height,
        camera=config.camera,
    )
    video_config = VideoConfig(
        width=config.width,
        height=config.height,
        fps=config.fps,
        frame_count=len(selection.frame_times),
    )
    png_frames = render_png_frames(
        _selected_frames(config, selection),
        render_config,
        temp_dir=config.output_path.parent,
    )
    result = encode_png_frames(config.output_path, png_frames, video_config)
    payload = asdict(result)
    payload["path"] = os.fspath(result.path)
    payload["run_id"] = selection.run.header.run_id
    payload["start_s"] = selection.start_s
    payload["end_s"] = selection.end_s
    payload["playback_duration_s"] = selection.playback_duration_s
    print(json.dumps(payload, sort_keys=True))
    return 0
