import json
from pathlib import Path

import pytest

from scrap_monitoring_lidar_visualizer.limits import (
    MAX_FRAME_HEIGHT,
    MAX_FRAME_WIDTH,
    MAX_GRID_POINTS,
)
from scrap_monitoring_lidar_visualizer.runtime_probe import (
    MAX_FPS,
    MAX_FRAMES,
    ProbeConfig,
    _ffprobe,
    ffmpeg_command,
    synthetic_surface,
)


def test_probe_config_accepts_project_limits() -> None:
    ProbeConfig(
        width=MAX_FRAME_WIDTH,
        height=MAX_FRAME_HEIGHT,
        fps=MAX_FPS,
        frame_count=MAX_FRAMES,
    ).validate()


@pytest.mark.parametrize(
    "config",
    [
        ProbeConfig(width=641),
        ProbeConfig(height=361),
        ProbeConfig(fps=MAX_FPS + 1),
        ProbeConfig(frame_count=MAX_FRAMES + 1),
        ProbeConfig(width=0),
        ProbeConfig(grid_x=MAX_GRID_POINTS, grid_y=2),
    ],
)
def test_probe_config_rejects_invalid_limits(config: ProbeConfig) -> None:
    with pytest.raises(ValueError):
        config.validate()


def test_synthetic_surface_has_stable_dimensions() -> None:
    surface = synthetic_surface()
    assert surface.dimensions == (25, 33, 1)
    assert surface.n_points == 825
    assert surface.n_cells == 768


def test_ffmpeg_command_streams_bounded_raw_frames(tmp_path: Path) -> None:
    output = tmp_path / "probe.mp4"
    command = ffmpeg_command(ProbeConfig(), output)
    assert command[command.index("-i") + 1] == "pipe:0"
    assert command[command.index("-frames:v") + 1] == "10"
    assert command[-1] == str(output)


def test_ffprobe_rejects_unexpected_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    class Completed:
        stdout = json.dumps(
            {
                "streams": [
                    {
                        "codec_name": "h264",
                        "width": 640,
                        "height": 360,
                        "nb_read_frames": "9",
                    }
                ]
            }
        )

    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: Completed())
    with pytest.raises(RuntimeError, match="unexpected ffprobe result"):
        _ffprobe(Path("probe.mp4"), ProbeConfig())
