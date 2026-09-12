"""Render validated observations as deterministic engineering scenes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pyvista as pv

from scrap_monitoring_lidar_visualizer.contracts.models import Header, Observation
from scrap_monitoring_lidar_visualizer.geometry import Mesh, SceneGeometry
from scrap_monitoring_lidar_visualizer.limits import (
    DEFAULT_FRAME_HEIGHT,
    DEFAULT_FRAME_WIDTH,
    MAX_FRAME_HEIGHT,
    MAX_FRAME_WIDTH,
)

EXPECTED_RENDER_WINDOW = "vtkOSOpenGLRenderWindow"


@dataclass(frozen=True, slots=True)
class RenderConfig:
    width: int = DEFAULT_FRAME_WIDTH
    height: int = DEFAULT_FRAME_HEIGHT
    camera: Literal["isometric", "top"] = "isometric"

    def validate(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("frame dimensions must be positive")
        if self.width > MAX_FRAME_WIDTH or self.height > MAX_FRAME_HEIGHT:
            raise ValueError("frame dimensions exceed the configured limit")


@dataclass(frozen=True, slots=True)
class RenderResult:
    path: Path
    width: int
    height: int
    render_window: str
    surface_vertices: int
    surface_faces: int


@dataclass(frozen=True, slots=True)
class SceneDescription:
    camera_position: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ]
    overlay: str
    active_inlet_index: int | None


def _poly_data(mesh: Mesh) -> pv.PolyData:
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(
        [value for face in mesh.faces for value in (3, *face)], dtype=np.int64
    )
    return pv.PolyData(vertices, faces)


def _camera_position(
    header: Header, camera: Literal["isometric", "top"]
) -> tuple[
    tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]
]:
    x_values = tuple(point[0] for point in header.scene.boundary_xy_m)
    y_values = tuple(point[1] for point in header.scene.boundary_xy_m)
    center_x = (min(x_values) + max(x_values)) / 2
    center_y = (min(y_values) + max(y_values)) / 2
    center_z = (header.scene.floor_z_m + header.scene.top_z_m) / 2
    span = max(
        max(x_values) - min(x_values),
        max(y_values) - min(y_values),
        header.scene.top_z_m - header.scene.floor_z_m,
        1.0,
    )
    focal = (center_x, center_y, center_z)
    if camera == "top":
        return ((center_x, center_y, center_z + 3 * span), focal, (0.0, 1.0, 0.0))
    return (
        (center_x + 1.7 * span, center_y - 1.7 * span, center_z + 1.3 * span),
        focal,
        (0.0, 0.0, 1.0),
    )


def _overlay(
    observation: Observation,
    *,
    connected: bool,
    missing_sequences: int,
    connection_label: str | None,
) -> str:
    scenario = observation.scenario
    connection = connection_label or ("connected" if connected else "disconnected")
    return "\n".join(
        (
            f"run: {observation.run_id}",
            f"sequence: {observation.sequence}",
            f"elapsed_s: {scenario.elapsed_s:.3f}",
            f"surface_fill_ratio: {scenario.surface_fill_ratio:.4f}",
            f"phase: {scenario.phase}",
            f"cycle_index: {scenario.cycle_index}",
            f"connection: {connection}",
            f"missing_sequences: {missing_sequences}",
        )
    )


def describe_scene(
    header: Header,
    observation: Observation,
    *,
    config: RenderConfig,
    connected: bool,
    missing_sequences: int,
    connection_label: str | None = None,
) -> SceneDescription:
    config.validate()
    active_inlet = (
        observation.scenario.current_inlet_index
        if observation.scenario.phase == "filling"
        else None
    )
    return SceneDescription(
        camera_position=_camera_position(header, config.camera),
        overlay=_overlay(
            observation,
            connected=connected,
            missing_sequences=missing_sequences,
            connection_label=connection_label,
        ),
        active_inlet_index=active_inlet,
    )


def render_scene(
    output_path: Path,
    header: Header,
    observation: Observation,
    geometry: SceneGeometry,
    *,
    config: RenderConfig | None = None,
    connected: bool,
    missing_sequences: int,
    connection_label: str | None = None,
) -> RenderResult:
    config = config or RenderConfig()
    config.validate()
    description = describe_scene(
        header,
        observation,
        config=config,
        connected=connected,
        missing_sequences=missing_sequences,
        connection_label=connection_label,
    )
    if output_path.exists():
        raise FileExistsError(output_path)
    if not output_path.parent.is_dir():
        raise ValueError("frame parent directory does not exist")
    plotter = pv.Plotter(off_screen=True, window_size=[config.width, config.height])
    plotter.set_background("#101820")  # type: ignore[arg-type]
    try:
        plotter.add_mesh(_poly_data(geometry.floor), color="#313A46")
        plotter.add_mesh(
            _poly_data(geometry.walls), color="#536273", opacity=0.35, show_edges=True
        )
        plotter.add_mesh(
            _poly_data(geometry.surface),
            color="#D6A85F",
            smooth_shading=False,
            show_edges=True,
        )
        x_values = tuple(point[0] for point in header.scene.boundary_xy_m)
        y_values = tuple(point[1] for point in header.scene.boundary_xy_m)
        marker_scale = max(
            max(x_values) - min(x_values), max(y_values) - min(y_values), 1.0
        )
        for sensor in header.scene.sensors:
            plotter.add_mesh(
                pv.Sphere(radius=0.025 * marker_scale, center=sensor.p0_m),
                color="#61AFEF",
            )
            plotter.add_mesh(
                pv.Arrow(
                    start=sensor.p0_m,
                    direction=sensor.u0,
                    scale=0.2 * marker_scale,
                ),
                color="#61AFEF",
            )
        for index, inlet in enumerate(header.scene.inlet_positions_xy_m):
            color = "#E06C75" if index == description.active_inlet_index else "#98C379"
            plotter.add_mesh(
                pv.Sphere(
                    radius=0.03 * marker_scale,
                    center=(inlet[0], inlet[1], header.scene.top_z_m),
                ),
                color=color,
            )
        plotter.add_text(
            description.overlay,
            position="upper_left",
            font_size=10,
            color="#F1F5F9",
        )
        plotter.reset_camera()  # type: ignore[call-arg]
        plotter.camera_position = description.camera_position
        plotter.render()
        render_window = type(plotter.render_window).__name__
        if render_window != EXPECTED_RENDER_WINDOW:
            raise RuntimeError(f"unexpected render window: {render_window}")
        image = plotter.screenshot(str(output_path), return_img=True)
        if image is None or image.shape[:2] != (config.height, config.width):
            raise RuntimeError("renderer returned an unexpected frame shape")
    finally:
        plotter.close()
    return RenderResult(
        path=output_path,
        width=config.width,
        height=config.height,
        render_window=render_window,
        surface_vertices=len(geometry.surface.vertices),
        surface_faces=len(geometry.surface.faces),
    )
