from __future__ import annotations

from pathlib import Path

import yaml


def test_ci_workflow_covers_all_supported_operating_systems() -> None:
    workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text())

    jobs = workflow["jobs"]
    operating_systems = jobs["test"]["strategy"]["matrix"]["include"]
    assert operating_systems == [
        {"os": "ubuntu-latest", "lockfile": "requirements/lock-linux.txt"},
        {"os": "macos-latest", "lockfile": "requirements/lock-macos.txt"},
        {"os": "windows-latest", "lockfile": "requirements/lock-windows.txt"},
    ]


def test_ci_workflow_runs_locked_install_imports_and_quality_checks() -> None:
    workflow_text = Path(".github/workflows/ci.yml").read_text()

    for command in (
        "--require-hashes",
        "import skia, av, shapely, pyproj, topojson, numpy",
        "ruff check .",
        "mypy --strict src/anima",
        "pytest -q",
    ):
        assert command in workflow_text
