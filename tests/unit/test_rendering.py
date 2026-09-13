from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
import pyvista as pv

from scrap_monitoring_lidar_visualizer.contracts import (
    ContractParser,
    Header,
    Observation,
)
from scrap_monitoring_lidar_visualizer.rendering import RenderConfig, describe_scene
from scrap_monitoring_lidar_visualizer.rendering.renderer import (
    _apply_camera,
    _sensor_rotation_axis,
)

CONTRACT_ROOT = Path("contracts/observation/v1")


@pytest.fixture(scope="module")
def records() -> tuple[Header, Observation]:
    parser = ContractParser(CONTRACT_ROOT)
    lines = (
        (CONTRACT_ROOT / "fixtures/observation.v1.jsonl")
        .read_bytes()
        .splitlines(keepends=True)
    )
    values = tuple(parser.parse_line(line).value for line in lines)
    assert isinstance(values[0], Header)
    assert isinstance(values[1], Observation)
    return values[0], values[1]


@pytest.mark.parametrize(
    "config",
    [
        RenderConfig(width=0),
        RenderConfig(height=0),
        RenderConfig(width=3841),
        RenderConfig(height=2161),
    ],
)
def test_render_config_rejects_invalid_dimensions(config: RenderConfig) -> None:
    with pytest.raises(ValueError):
        config.validate()


def test_render_config_accepts_both_cameras() -> None:
    RenderConfig(camera="isometric").validate()
    RenderConfig(camera="top").validate()


def test_camera_uses_parallel_projection() -> None:
    class PlotterStub:
        def __init__(self) -> None:
            self.camera_position: object = None
            self.reset = False
            self.parallel_projection = False

        def reset_camera(self) -> None:
            self.reset = True

        def enable_parallel_projection(self) -> None:
            self.parallel_projection = True

    camera_position = (
        (1.0, -1.0, 1.0),
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 1.0),
    )
    plotter = PlotterStub()

    _apply_camera(cast(pv.Plotter, plotter), camera_position)

    assert plotter.reset
    assert plotter.camera_position == camera_position
    assert plotter.parallel_projection


def test_sensor_marker_uses_right_handed_rotation_axis(
    records: tuple[Header, Observation],
) -> None:
    header, _ = records

    assert _sensor_rotation_axis(header.scene.sensors[0]) == (0.0, -1.0, 0.0)


def test_scene_description_contains_required_overlay_and_camera(
    records: tuple[Header, Observation],
) -> None:
    header, observation = records
    isometric = describe_scene(
        header,
        observation,
        config=RenderConfig(camera="isometric"),
        connected=True,
        missing_sequences=3,
    )
    top = describe_scene(
        header,
        observation,
        config=RenderConfig(camera="top"),
        connected=False,
        missing_sequences=3,
        connection_label="replay",
    )

    assert isometric.camera_position != top.camera_position
    assert isometric.active_inlet_index == 0
    assert "sequence: 1" in isometric.overlay
    assert "connection: connected" in isometric.overlay
    assert "missing_sequences: 3" in top.overlay
    assert "connection: replay" in top.overlay


def test_collecting_scene_has_no_active_inlet(
    records: tuple[Header, Observation],
) -> None:
    header, observation = records
    collecting = replace(
        observation,
        scenario=replace(
            observation.scenario, phase="collecting", current_inlet_index=None
        ),
    )
    description = describe_scene(
        header,
        collecting,
        config=RenderConfig(),
        connected=True,
        missing_sequences=0,
    )

    assert description.active_inlet_index is None
