from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path


def test_wheel_contains_fixed_contract_schemas(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path)],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(tmp_path.glob("*.whl"))
    package = "scrap_monitoring_visualizer/contracts/schema/v1"

    with zipfile.ZipFile(wheel) as archive:
        for name in ("header.schema.json", "observation.schema.json"):
            packaged = archive.read(f"{package}/{name}")
            fixed = (root / "contracts/observation/v1" / name).read_bytes()
            assert packaged == fixed
