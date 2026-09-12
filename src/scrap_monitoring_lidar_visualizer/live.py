"""Live receiver, renderer and preview process lifetime."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import uvicorn

from scrap_monitoring_lidar_visualizer.contracts import ContractParser
from scrap_monitoring_lidar_visualizer.preview import (
    LatestFrameStore,
    create_preview_app,
)
from scrap_monitoring_lidar_visualizer.receiver import ObservationReceiver
from scrap_monitoring_lidar_visualizer.recording import AsyncRecordWriter
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
    width: int = 640
    height: int = 360
    record_path: Path | None = None
    record_max_records: int | None = None
    record_max_bytes: int | None = None

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
        recording_values = (
            self.record_path,
            self.record_max_records,
            self.record_max_bytes,
        )
        if any(value is not None for value in recording_values) and not all(
            value is not None for value in recording_values
        ):
            raise ValueError(
                "record path, max records and max bytes must be set together"
            )
        if self.record_max_records is not None and self.record_max_records <= 0:
            raise ValueError("record max records must be positive")
        if self.record_max_bytes is not None and self.record_max_bytes <= 0:
            raise ValueError("record max bytes must be positive")


class LiveCoordinator:
    def __init__(
        self,
        frames: LatestFrameStore,
        worker: LatestRenderWorker,
        render_config: RenderConfig,
        recorder: AsyncRecordWriter | None,
    ) -> None:
        self._frames = frames
        self._worker = worker
        self._render_config = render_config
        self._recorder = recorder
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
                missing_sequences=state.missing_sequences,
                config=self._render_config,
            )
        )

    def status(self) -> dict[str, Any]:
        observation = self._state.observation
        receiver_snapshot = (
            self._receiver.snapshot if self._receiver is not None else None
        )
        recording = self._recorder.snapshot if self._recorder is not None else None
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
            "recording": asdict(recording) if recording is not None else None,
            "render_error": self._worker.last_error,
        }


async def run_live(config: LiveConfig) -> int:
    config.validate()
    recorder: AsyncRecordWriter | None = None
    if config.record_path is not None:
        assert config.record_max_records is not None
        assert config.record_max_bytes is not None
        recorder = AsyncRecordWriter(
            config.record_path,
            max_records=config.record_max_records,
            max_bytes=config.record_max_bytes,
        )
        await recorder.start()
    frames = LatestFrameStore()
    worker = LatestRenderWorker(frames)
    try:
        worker.start()
    except Exception:
        if recorder is not None:
            await recorder.close()
        raise
    coordinator = LiveCoordinator(
        frames,
        worker,
        RenderConfig(width=config.width, height=config.height, camera=config.camera),
        recorder,
    )
    receiver = ObservationReceiver(
        ContractParser(), recorder=recorder, on_state=coordinator.state_changed
    )
    coordinator.bind_receiver(receiver)
    try:
        tcp_server = await asyncio.start_server(
            receiver.handle_client, config.tcp_host, config.tcp_port
        )
    except Exception:
        worker.close()
        if recorder is not None:
            await recorder.close()
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
    exit_code = 0
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
        if recorder is not None:
            recording = await recorder.close()
            if recording.reason == "write_error":
                exit_code = 1
    return exit_code
