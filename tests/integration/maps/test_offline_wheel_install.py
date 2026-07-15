from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .test_wheel_policy import build_map_wheels


def test_wheel_installs_and_loads_all_data_without_network(tmp_path: Path) -> None:
    wheel_dir = tmp_path / "wheel"
    wheel_dir.mkdir()
    wheels = build_map_wheels(wheel_dir)
    install_target = tmp_path / "installed"
    install_environment = dict(os.environ)
    install_environment["PIP_CONFIG_FILE"] = os.devnull
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-index",
            "--no-deps",
            "--no-user",
            "--ignore-installed",
            "--target",
            str(install_target),
            *(str(wheel) for wheel in wheels),
        ],
        env=install_environment,
        check=True,
        capture_output=True,
        text=True,
    )
    script = """
import json
import os
import sys
sys.path.insert(0, os.environ["ANIMA_WHEEL_TARGET"])
from anima.data.vendored import available_datasets, load_geojson, verify_vendored_data
assert verify_vendored_data() == ()
counts = {
    dataset_id: len(load_geojson(dataset_id)["features"])
    for dataset_id in available_datasets()
}
print(json.dumps(counts, sort_keys=True))
"""
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment["ANIMA_WHEEL_TARGET"] = str(install_target)
    environment["PROJ_NETWORK"] = "OFF"
    completed = subprocess.run(
        [sys.executable, "-I", "-c", script],
        cwd=tmp_path,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert '"historical-basemaps"' in completed.stdout
    assert '"natural-earth-110m"' in completed.stdout
    assert '"natural-earth-50m"' in completed.stdout
