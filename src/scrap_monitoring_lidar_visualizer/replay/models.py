"""Immutable replay inventory and frame selection models."""

from __future__ import annotations

from dataclasses import dataclass

from scrap_monitoring_lidar_visualizer.contracts import Header, Observation


@dataclass(frozen=True, slots=True)
class RunSummary:
    header: Header
    first_header_offset: int
    observation_count: int = 0
    first_elapsed_s: float | None = None
    last_elapsed_s: float | None = None


@dataclass(frozen=True, slots=True)
class ReplayObservation:
    header: Header
    observation: Observation
    missing_sequences: int


@dataclass(frozen=True, slots=True)
class FrameTime:
    index: int
    output_s: float
    simulation_s: float


@dataclass(frozen=True, slots=True)
class SelectedFrame:
    time: FrameTime
    state: ReplayObservation


@dataclass(frozen=True, slots=True)
class ReplaySelection:
    run: RunSummary
    start_s: float
    end_s: float
    playback_duration_s: float
    time_scale: float
    fps: int
    frame_times: tuple[FrameTime, ...]
