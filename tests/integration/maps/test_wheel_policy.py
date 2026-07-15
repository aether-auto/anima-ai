from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path


def _build_wheel(destination: Path) -> Path:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            ".",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(destination),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    wheels = tuple(destination.glob("anima_ai-*.whl"))
    assert len(wheels) == 1
    return wheels[0]


def test_main_wheel_stays_at_or_below_60_mib_and_contains_offline_data(tmp_path: Path) -> None:
    wheel = _build_wheel(tmp_path)

    assert wheel.stat().st_size <= 60 * 1024 * 1024
    with zipfile.ZipFile(wheel) as archive:
        members = set(archive.namelist())

    assert "anima/data/catalog.json" in members
    assert "anima/data/natural_earth/LICENSE.txt" in members
    assert "anima/data/natural_earth/ATTRIBUTION.txt" in members
    assert "anima/data/historical_basemaps/LICENSE.txt" in members
    assert "anima/data/historical_basemaps/ATTRIBUTION.txt" in members
    assert any(name.endswith("ne_110m/countries.geojson") for name in members)
    assert any(name.endswith("ne_50m/countries.geojson") for name in members)
    assert any("historical_basemaps" in name and name.endswith(".geojson") for name in members)
