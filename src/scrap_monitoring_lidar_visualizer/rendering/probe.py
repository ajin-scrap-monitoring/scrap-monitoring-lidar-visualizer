"""Render the fixed public contract fixture inside the target container."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

from scrap_monitoring_lidar_visualizer.contracts import (
    ContractParser,
    Header,
    Observation,
)
from scrap_monitoring_lidar_visualizer.geometry import build_scene_geometry
from scrap_monitoring_lidar_visualizer.rendering import RenderConfig, render_scene


def run_probe(output_dir: Path, contract_root: Path) -> dict[str, object]:
    if "DISPLAY" in os.environ or os.geteuid() == 0:
        raise RuntimeError("scene probe requires headless non-root execution")
    output_dir.mkdir(parents=True, exist_ok=False)
    parser = ContractParser(contract_root)
    lines = (
        (contract_root / "fixtures/observation.v1.jsonl")
        .read_bytes()
        .splitlines(keepends=True)
    )
    records = tuple(parser.parse_line(line).value for line in lines)
    if (
        len(records) != 2
        or not isinstance(records[0], Header)
        or not isinstance(records[1], Observation)
    ):
        raise RuntimeError(
            "contract fixture must contain one header and one observation"
        )
    geometry = build_scene_geometry(records[0], records[1])
    result = render_scene(
        output_dir / "scene.png",
        records[0],
        records[1],
        geometry,
        config=RenderConfig(),
        connected=True,
        missing_sequences=0,
    )
    top_result = render_scene(
        output_dir / "scene-top.png",
        records[0],
        records[1],
        geometry,
        config=RenderConfig(camera="top"),
        connected=False,
        missing_sequences=2,
    )
    payload = {
        **asdict(result),
        "path": result.path.name,
        "euid": os.geteuid(),
        "display_present": "DISPLAY" in os.environ,
        "floor_faces": len(geometry.floor.faces),
        "wall_faces": len(geometry.walls.faces),
        "top_path": top_result.path.name,
    }
    (output_dir / "scene.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("/output/scene"))
    parser.add_argument(
        "--contracts", type=Path, default=Path("/app/contracts/observation/v1")
    )
    args = parser.parse_args()
    print(json.dumps(run_probe(args.output, args.contracts), sort_keys=True))


if __name__ == "__main__":
    main()
