from __future__ import annotations

import json
from pathlib import Path

import pytest

from scrap_monitoring_lidar_visualizer.export import (
    VideoConfig,
    encode_png_frames,
    ffmpeg_command,
)
from scrap_monitoring_lidar_visualizer.export.video import _probe_video
from scrap_monitoring_lidar_visualizer.limits import MAX_FPS, MAX_FRAMES


def test_video_config_accepts_project_limits() -> None:
    VideoConfig(width=3840, height=2160, fps=MAX_FPS, frame_count=MAX_FRAMES).validate()


@pytest.mark.parametrize(
    "config",
    [
        VideoConfig(width=641, height=360, fps=10, frame_count=1),
        VideoConfig(width=640, height=361, fps=10, frame_count=1),
        VideoConfig(width=640, height=360, fps=MAX_FPS + 1, frame_count=1),
        VideoConfig(width=640, height=360, fps=10, frame_count=MAX_FRAMES + 1),
    ],
)
def test_video_config_rejects_invalid_limits(config: VideoConfig) -> None:
    with pytest.raises(ValueError):
        config.validate()


def test_ffmpeg_command_streams_png_frames_without_overwrite(tmp_path: Path) -> None:
    output = tmp_path / "video.mp4"
    command = ffmpeg_command(VideoConfig(640, 360, 10, 3), output)

    assert command[command.index("-i") + 1] == "pipe:0"
    assert command[command.index("-frames:v") + 1] == "3"
    assert "-n" in command
    assert command[-1] == str(output)


def test_existing_output_is_protected_before_frames_are_consumed(
    tmp_path: Path,
) -> None:
    output = tmp_path / "video.mp4"
    output.write_bytes(b"keep")
    consumed = False

    def frames():
        nonlocal consumed
        consumed = True
        yield b"\x89PNG\r\n\x1a\n"

    with pytest.raises(FileExistsError):
        encode_png_frames(output, frames(), VideoConfig(640, 360, 10, 1))

    assert output.read_bytes() == b"keep"
    assert consumed is False


def test_output_path_must_be_mp4_in_existing_directory(tmp_path: Path) -> None:
    config = VideoConfig(640, 360, 10, 1)
    with pytest.raises(ValueError, match=".mp4 extension"):
        encode_png_frames(tmp_path / "video.avi", (), config)
    with pytest.raises(ValueError, match="parent directory"):
        encode_png_frames(tmp_path / "missing" / "video.mp4", (), config)


def test_ffprobe_rejects_unexpected_frame_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Completed:
        stdout = json.dumps(
            {
                "streams": [
                    {
                        "codec_name": "h264",
                        "width": 640,
                        "height": 360,
                        "nb_read_frames": "2",
                    }
                ]
            }
        )

    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: Completed())
    with pytest.raises(RuntimeError, match="unexpected ffprobe result"):
        _probe_video(Path("video.mp4"), VideoConfig(640, 360, 10, 3))


def test_encoder_failure_removes_partial_files(tmp_path: Path) -> None:
    output = tmp_path / "video.mp4"

    with pytest.raises(RuntimeError, match="FFmpeg"):
        encode_png_frames(
            output,
            [b"\x89PNG\r\n\x1a\ninvalid"],
            VideoConfig(640, 360, 10, 1),
            ffmpeg="/bin/false",
        )

    assert not output.exists()
    assert tuple(tmp_path.iterdir()) == ()
