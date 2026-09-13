"""Live receiver, renderer and preview process lifetime."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

import uvicorn

from scrap_monitoring_lidar_visualizer.contracts import ContractParser
from scrap_monitoring_lidar_visualizer.limits import (
    DEFAULT_FRAME_HEIGHT,
    DEFAULT_FRAME_WIDTH,
)
from scrap_monitoring_lidar_visualizer.preview import (
    LatestFrameStore,
    create_preview_app,
)
from scrap_monitoring_lidar_visualizer.receiver import ObservationReceiver
from scrap_monitoring_lidar_visualizer.rendering import RenderConfig
from scrap_monitoring_lidar_visualizer.rendering.worker import (
    LatestRenderWorker,
    RenderRequest,
)
from scrap_monitoring_lidar_visualizer.state import ExecutionState


@dataclass(frozen=True, slots=True)
class LiveConfig:
    tcp_host: str
    tcp_port: int
    http_host: str
    http_port: int
    camera: Literal["isometric", "top"] = "isometric"
    width: int = DEFAULT_FRAME_WIDTH
    height: int = DEFAULT_FRAME_HEIGHT

    def validate(self) -> None:
        if not self.tcp_host or not self.http_host:
            raise ValueError("listen hosts must not be empty")
        if not (1 <= self.tcp_port <= 65_535 and 1 <= self.http_port <= 65_535):
            raise ValueError("listen ports must be between 1 and 65535")
        if self.tcp_host == self.http_host and self.tcp_port == self.http_port:
            raise ValueError("TCP and HTTP endpoints must be different")
        RenderConfig(
            width=self.width, height=self.height, camera=self.camera
        ).validate()


class LiveCoordinator:
    def __init__(
        self,
        frames: LatestFrameStore,
        worker: LatestRenderWorker,
        render_config: RenderConfig,
    ) -> None:
        self._frames = frames
        self._worker = worker
        self._render_config = render_config
        self._receiver: ObservationReceiver | None = None
        self._state = ExecutionState()
        self._last_received_sequence: int | None = None
        self._last_valid_received_at: str | None = None

    def bind_receiver(self, receiver: ObservationReceiver) -> None:
        self._receiver = receiver

    def state_changed(self, state: ExecutionState) -> None:
        self._state = state
        observation = state.observation
        if observation is None:
            self._worker.invalidate()
            self._frames.clear()
            self._last_received_sequence = None
            self._last_valid_received_at = None
            return
        if observation.sequence != self._last_received_sequence:
            self._last_received_sequence = observation.sequence
            self._last_valid_received_at = datetime.now(UTC).isoformat()
        assert state.header is not None
        self._worker.submit(
            RenderRequest(
                header=state.header,
                observation=observation,
                connected=state.connected,
                config=self._render_config,
            )
        )

    def status(self) -> dict[str, Any]:
        observation = self._state.observation
        receiver_snapshot = (
            self._receiver.snapshot if self._receiver is not None else None
        )
        return {
            "connected": self._state.connected,
            "run_id": self._state.header.run_id
            if self._state.header is not None
            else None,
            "received_sequence": observation.sequence
            if observation is not None
            else None,
            "missing_sequences": self._state.missing_sequences,
            "connection_index": self._state.connection_index,
            "last_valid_received_at": self._last_valid_received_at,
            "records_accepted": (
                receiver_snapshot.records_accepted
                if receiver_snapshot is not None
                else 0
            ),
            "records_rejected": (
                receiver_snapshot.records_rejected
                if receiver_snapshot is not None
                else 0
            ),
            "render_error": self._worker.last_error,
        }


async def run_live(config: LiveConfig) -> int:
    config.validate()
    frames = LatestFrameStore()
    worker = LatestRenderWorker(frames)
    worker.start()
    coordinator = LiveCoordinator(
        frames,
        worker,
        RenderConfig(width=config.width, height=config.height, camera=config.camera),
    )
    receiver = ObservationReceiver(ContractParser(), on_state=coordinator.state_changed)
    coordinator.bind_receiver(receiver)
    try:
        tcp_server = await asyncio.start_server(
            receiver.handle_client, config.tcp_host, config.tcp_port
        )
    except Exception:
        worker.close()
        raise
    app = create_preview_app(frames, coordinator.status)
    uvicorn_server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=config.http_host,
            port=config.http_port,
            access_log=False,
            log_level="info",
            timeout_keep_alive=5,
        )
    )

    async def poll_renderer() -> None:
        while not uvicorn_server.should_exit:
            worker.poll()
            await asyncio.sleep(0.02)

    poll_task = asyncio.create_task(poll_renderer())
    try:
        async with tcp_server:
            await uvicorn_server.serve()
    finally:
        uvicorn_server.should_exit = True
        tcp_server.close()
        await tcp_server.wait_closed()
        await poll_task
        worker.poll()
        worker.close()
    return 0
