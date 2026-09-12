"""Pure replay window, timing and observation selection."""

from __future__ import annotations

import math
from collections.abc import Iterable, Iterator

from scrap_monitoring_lidar_visualizer.limits import MAX_FPS, MAX_FRAMES

from .models import (
    FrameTime,
    ReplayObservation,
    ReplaySelection,
    RunSummary,
    SelectedFrame,
)
from .reader import ReplayError


def select_run(summaries: tuple[RunSummary, ...], run_id: str | None) -> RunSummary:
    if run_id is None:
        if len(summaries) != 1:
            raise ReplayError("--run-id is required when the recording is ambiguous")
        if summaries[0].observation_count == 0:
            raise ReplayError(
                f"selected run has no observations: {summaries[0].header.run_id}"
            )
        return summaries[0]
    for summary in summaries:
        if summary.header.run_id == run_id:
            if summary.observation_count == 0:
                raise ReplayError(f"selected run has no observations: {run_id}")
            return summary
    raise ReplayError(f"run not found: {run_id}")


def build_selection(
    run: RunSummary,
    *,
    start_s: float | None,
    end_s: float | None,
    duration_s: float | None,
    time_scale: float | None,
    fps: int,
) -> ReplaySelection:
    if duration_s is not None and time_scale is not None:
        raise ReplayError("duration and time scale are mutually exclusive")
    if fps <= 0 or fps > MAX_FPS:
        raise ReplayError(f"fps must be between 1 and {MAX_FPS}")
    if run.first_elapsed_s is None or run.last_elapsed_s is None:
        raise ReplayError(f"selected run has no observations: {run.header.run_id}")
    start = run.first_elapsed_s if start_s is None else start_s
    end = run.last_elapsed_s if end_s is None else end_s
    if not math.isfinite(start) or not math.isfinite(end):
        raise ReplayError("replay interval must be finite")
    if start < run.first_elapsed_s:
        raise ReplayError("replay start is before the first observation")
    if end > run.last_elapsed_s:
        raise ReplayError("replay end is after the last observation")
    if start > end:
        raise ReplayError("replay start must not exceed end")
    span = end - start
    if duration_s is not None:
        if not math.isfinite(duration_s) or duration_s <= 0:
            raise ReplayError("duration must be finite and positive")
        playback_duration = duration_s
        scale = span / duration_s
    else:
        scale = 1.0 if time_scale is None else time_scale
        if not math.isfinite(scale) or scale <= 0:
            raise ReplayError("time scale must be finite and positive")
        playback_duration = span / scale if span > 0 else 1 / fps
    frame_count_value = playback_duration * fps
    if not math.isfinite(frame_count_value):
        raise ReplayError("frame count is not finite")
    if frame_count_value > MAX_FRAMES:
        raise ReplayError(f"frame count exceeds the configured limit: {MAX_FRAMES}")
    frame_count = math.ceil(frame_count_value)
    if frame_count <= 0:
        frame_count = 1
    frame_times = tuple(
        FrameTime(
            index=index,
            output_s=index / fps,
            simulation_s=min(end, start + (index / fps) * scale),
        )
        for index in range(frame_count)
    )
    return ReplaySelection(
        run=run,
        start_s=start,
        end_s=end,
        playback_duration_s=playback_duration,
        time_scale=scale,
        fps=fps,
        frame_times=frame_times,
    )


def select_frames(
    observations: Iterable[ReplayObservation], frame_times: Iterable[FrameTime]
) -> Iterator[SelectedFrame]:
    iterator = iter(observations)
    try:
        current = next(iterator)
    except StopIteration as error:
        raise ReplayError("selected run has no observations") from error
    upcoming = next(iterator, None)
    for frame_time in frame_times:
        if current.observation.scenario.elapsed_s > frame_time.simulation_s:
            raise ReplayError("replay start is before the first observation")
        while (
            upcoming is not None
            and upcoming.observation.scenario.elapsed_s <= frame_time.simulation_s
        ):
            current = upcoming
            upcoming = next(iterator, None)
        yield SelectedFrame(time=frame_time, state=current)
