from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path


def _build_wheel(project: Path, destination: Path, pattern: str) -> Path:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            str(project),
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(destination),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    wheels = tuple(destination.glob(pattern))
    assert len(wheels) == 1
    return wheels[0]


def build_map_wheels(destination: Path) -> tuple[Path, Path]:
    main = _build_wheel(Path("."), destination, "anima_ai-*.whl")
    data = _build_wheel(
        Path("packages/anima-ai-data"), destination, "anima_ai_data-*.whl"
    )
    return main, data


def test_main_and_data_wheels_enforce_size_license_and_version_policy(tmp_path: Path) -> None:
    main_wheel, data_wheel = build_map_wheels(tmp_path)

    assert main_wheel.stat().st_size <= 60 * 1024 * 1024
    assert main_wheel.name.split("-", maxsplit=2)[1] == data_wheel.name.split("-", maxsplit=2)[1]
    with zipfile.ZipFile(main_wheel) as archive:
        main_members = set(archive.namelist())
    with zipfile.ZipFile(data_wheel) as archive:
        data_members = set(archive.namelist())

    assert "anima/data/catalog.json" in main_members
    assert "anima/data/natural_earth/LICENSE.txt" in main_members
    assert "anima/data/natural_earth/ATTRIBUTION.txt" in main_members
    assert any(name.endswith("ne_110m/countries.geojson") for name in main_members)
    assert any(name.endswith("ne_50m/countries.geojson") for name in main_members)
    assert not any("historical_basemaps" in name for name in main_members)

    assert "anima_ai_data/historical_basemaps/LICENSE.txt" in data_members
    assert "anima_ai_data/historical_basemaps/ATTRIBUTION.txt" in data_members
    assert any(
        "historical_basemaps" in name and name.endswith(".geojson")
        for name in data_members
    )
