"""Single child process that renders only the newest pending snapshot."""

from __future__ import annotations

import multiprocessing as mp
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from queue import Empty, Full
from typing import Any

from scrap_monitoring_lidar_visualizer.contracts.models import Header, Observation
from scrap_monitoring_lidar_visualizer.geometry import build_scene_geometry
from scrap_monitoring_lidar_visualizer.preview import LatestFrameStore

from .renderer import RenderConfig, render_scene


@dataclass(frozen=True, slots=True)
class RenderRequest:
    header: Header
    observation: Observation
    connected: bool
    missing_sequences: int
    config: RenderConfig
    temp_dir: Path | None = None
    connection_label: str | None = None
    render_top_view: bool = True


@dataclass(frozen=True, slots=True)
class RenderOutcome:
    generation: int
    run_id: str
    sequence: int
    png: bytes | None
    top_png: bytes | None
    error: str | None


def _render(generation: int, request: RenderRequest) -> RenderOutcome:
    try:
        geometry = build_scene_geometry(request.header, request.observation)
        with tempfile.TemporaryDirectory(
            prefix="lidar-render-", dir=request.temp_dir
        ) as directory:
            path = Path(directory) / "frame.png"
            render_scene(
                path,
                request.header,
                request.observation,
                geometry,
                config=request.config,
                connected=request.connected,
                missing_sequences=request.missing_sequences,
                connection_label=request.connection_label,
            )
            png = path.read_bytes()
            if not request.render_top_view or request.config.camera == "top":
                top_png = png
            else:
                top_path = Path(directory) / "frame-top.png"
                render_scene(
                    top_path,
                    request.header,
                    request.observation,
                    geometry,
                    config=replace(request.config, camera="top"),
                    connected=request.connected,
                    missing_sequences=request.missing_sequences,
                    connection_label=request.connection_label,
                )
                top_png = top_path.read_bytes()
        return RenderOutcome(
            generation=generation,
            run_id=request.observation.run_id,
            sequence=request.observation.sequence,
            png=png,
            top_png=top_png,
            error=None,
        )
    except Exception as error:
        return RenderOutcome(
            generation=generation,
            run_id=request.observation.run_id,
            sequence=request.observation.sequence,
            png=None,
            top_png=None,
            error=str(error),
        )


def _worker_main(requests: Any, outcomes: Any) -> None:
    while True:
        envelope = requests.get()
        if envelope is None:
            return
        generation, request = envelope
        outcome = _render(generation, request)
        outcomes.put(outcome)


class LatestRenderWorker:
    def __init__(self, frames: LatestFrameStore) -> None:
        context = mp.get_context("spawn")
        self._requests = context.Queue(maxsize=1)
        self._outcomes = context.Queue(maxsize=1)
        self._process = context.Process(
            target=_worker_main,
            args=(self._requests, self._outcomes),
            name="lidar-renderer",
        )
        self._frames = frames
        self._generation = 0
        self._inflight = False
        self._pending: tuple[int, RenderRequest] | None = None
        self.last_error: str | None = None

    def start(self) -> None:
        self._process.start()

    @property
    def is_alive(self) -> bool:
        return self._process.is_alive()

    def submit(self, request: RenderRequest) -> None:
        self._pending = (self._generation, request)
        self._flush_pending()

    def _flush_pending(self) -> None:
        if self._pending is None or self._inflight:
            return
        try:
            self._requests.put_nowait(self._pending)
        except Full:
            return
        self._inflight = True
        self._pending = None

    def invalidate(self) -> None:
        self._generation += 1
        self._pending = None
        self.last_error = None

    def poll(self) -> RenderOutcome | None:
        latest: RenderOutcome | None = None
        while True:
            try:
                latest = self._outcomes.get_nowait()
            except Empty:
                break
            self._inflight = False
        self._flush_pending()
        if latest is None or latest.generation != self._generation:
            return None
        if latest.error is not None or latest.png is None or latest.top_png is None:
            self.last_error = latest.error or "renderer returned no frame"
            return latest
        self._frames.publish(
            latest.png,
            latest.top_png,
            run_id=latest.run_id,
            sequence=latest.sequence,
        )
        self.last_error = None
        return latest

    def close(self, timeout_s: float = 5.0) -> None:
        self._pending = None
        try:
            self._requests.put(None, timeout=timeout_s)
        except Full:
            pass
        self._process.join(timeout_s)
        if self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout_s)
        self._requests.close()
        self._outcomes.close()
