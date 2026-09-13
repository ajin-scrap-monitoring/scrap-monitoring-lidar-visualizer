from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
import pyvista as pv

from scrap_monitoring_visualizer.contracts import (
    ContractParser,
    Header,
    Observation,
)
from scrap_monitoring_visualizer.geometry import build_scene_geometry
from scrap_monitoring_visualizer.rendering import RenderConfig, describe_scene
from scrap_monitoring_visualizer.rendering.renderer import (
    HEIGHT_SCALAR_NAME,
    _apply_camera,
    _height_label_font_size,
    _height_poly_data,
    _height_scale,
    _height_tick_levels,
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


def test_height_mesh_uses_absolute_vertex_z_values(
    records: tuple[Header, Observation],
) -> None:
    geometry = build_scene_geometry(*records)

    data = _height_poly_data(geometry.surface)

    assert data.point_data[HEIGHT_SCALAR_NAME].tolist() == [
        vertex[2] for vertex in geometry.surface.vertices
    ]


def test_height_ticks_use_two_meter_intervals_and_include_bounds() -> None:
    assert _height_tick_levels(0.0, 10.0) == (0.0, 2.0, 4.0, 6.0, 8.0, 10.0)
    assert _height_tick_levels(-0.5, 3.5) == (-0.5, 0.0, 2.0, 3.5)


@pytest.mark.parametrize(
    ("frame_height", "font_size"),
    [(360, 16), (720, 18), (1080, 27), (2160, 28)],
)
def test_height_label_font_size_scales_with_frame(
    frame_height: int, font_size: int
) -> None:
    assert _height_label_font_size(frame_height) == font_size


def test_height_scale_uses_screen_right_boundary_edge(
    records: tuple[Header, Observation],
) -> None:
    header, observation = records
    camera_position = describe_scene(
        header,
        observation,
        config=RenderConfig(),
        connected=True,
    ).camera_position
    scale = _height_scale(header, camera_position)

    assert scale.line_points[0][:2] == scale.line_points[1][:2]
    assert scale.line_points[0][2] == header.scene.floor_z_m
    assert scale.line_points[1][2] == header.scene.top_z_m
    assert scale.labels == ("0 m", "1 m")


def test_scene_description_contains_required_overlay(
    records: tuple[Header, Observation],
) -> None:
    header, observation = records
    description = describe_scene(
        header,
        observation,
        config=RenderConfig(),
        connected=True,
    )

    assert description.active_inlet_index == 0
    assert "sequence: 1" in description.overlay
    assert "connection: connected" in description.overlay
    assert "run:" not in description.overlay
    assert "missing_sequences:" not in description.overlay


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
    )

    assert description.active_inlet_index is None
