from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .test_wheel_policy import _build_wheel


def test_wheel_installs_and_loads_all_data_without_network(tmp_path: Path) -> None:
    wheel_dir = tmp_path / "wheel"
    wheel_dir.mkdir()
    wheel = _build_wheel(wheel_dir)
    venv = tmp_path / "venv"
    subprocess.run(
        [sys.executable, "-m", "venv", "--system-site-packages", str(venv)],
        check=True,
    )
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            str(wheel),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    script = """
import json
from anima.data.vendored import available_datasets, load_geojson, verify_vendored_data
assert verify_vendored_data() == ()
counts = {dataset_id: len(load_geojson(dataset_id)["features"]) for dataset_id in available_datasets()}
print(json.dumps(counts, sort_keys=True))
"""
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment["PROJ_NETWORK"] = "OFF"
    completed = subprocess.run(
        [str(python), "-I", "-c", script],
        cwd=tmp_path,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert '"historical-basemaps"' in completed.stdout
    assert '"natural-earth-110m"' in completed.stdout
    assert '"natural-earth-50m"' in completed.stdout
