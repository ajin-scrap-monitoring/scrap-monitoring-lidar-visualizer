"""Single child process that renders only the newest pending snapshot."""

from __future__ import annotations

import multiprocessing as mp
import tempfile
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class RenderOutcome:
    generation: int
    run_id: str
    sequence: int
    png: bytes | None
    error: str | None


def _render(generation: int, request: RenderRequest) -> RenderOutcome:
    try:
        geometry = build_scene_geometry(request.header, request.observation)
        with tempfile.TemporaryDirectory(prefix="lidar-render-") as directory:
            path = Path(directory) / "frame.png"
            render_scene(
                path,
                request.header,
                request.observation,
                geometry,
                config=request.config,
                connected=request.connected,
                missing_sequences=request.missing_sequences,
            )
            png = path.read_bytes()
        return RenderOutcome(
            generation=generation,
            run_id=request.observation.run_id,
            sequence=request.observation.sequence,
            png=png,
            error=None,
        )
    except Exception as error:
        return RenderOutcome(
            generation=generation,
            run_id=request.observation.run_id,
            sequence=request.observation.sequence,
            png=None,
            error=str(error),
        )


def _worker_main(requests: Any, outcomes: Any) -> None:
    while True:
        envelope = requests.get()
        if envelope is None:
            return
        generation, request = envelope
        outcome = _render(generation, request)
        try:
            outcomes.put_nowait(outcome)
        except Full:
            try:
                outcomes.get_nowait()
            except Empty:
                pass
            outcomes.put_nowait(outcome)


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
        self.last_error: str | None = None

    def start(self) -> None:
        self._process.start()

    def submit(self, request: RenderRequest) -> None:
        envelope = (self._generation, request)
        try:
            self._requests.put_nowait(envelope)
            return
        except Full:
            pass
        try:
            self._requests.get_nowait()
        except Empty:
            pass
        try:
            self._requests.put_nowait(envelope)
        except Full:
            pass

    def invalidate(self) -> None:
        self._generation += 1
        while True:
            try:
                self._requests.get_nowait()
            except Empty:
                break
        while True:
            try:
                self._outcomes.get_nowait()
            except Empty:
                break

    def poll(self) -> RenderOutcome | None:
        latest: RenderOutcome | None = None
        while True:
            try:
                latest = self._outcomes.get_nowait()
            except Empty:
                break
        if latest is None or latest.generation != self._generation:
            return None
        if latest.error is not None or latest.png is None:
            self.last_error = latest.error or "renderer returned no frame"
            return latest
        self._frames.publish(latest.png, run_id=latest.run_id, sequence=latest.sequence)
        self.last_error = None
        return latest

    def close(self, timeout_s: float = 5.0) -> None:
        while True:
            try:
                self._requests.get_nowait()
            except Empty:
                break
        try:
            self._requests.put_nowait(None)
        except Full:
            pass
        self._process.join(timeout_s)
        if self._process.is_alive():
            self._process.terminate()
            self._process.join(timeout_s)
        self._requests.close()
        self._outcomes.close()
