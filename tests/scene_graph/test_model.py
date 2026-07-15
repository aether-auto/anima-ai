from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import anima
from anima.scene_graph import (
    Layer,
    Project,
    Resolution,
    Scene,
    StylePackRef,
    Transform,
    Vector2,
    VisibilityWindow,
)


def test_value_object_defaults_are_complete_and_immutable() -> None:
    resolution = Resolution()
    transform = Transform()
    visibility = VisibilityWindow()

    assert resolution == Resolution(width=1920, height=1080)
    assert transform == Transform(
        position=Vector2(x=0.0, y=0.0),
        rotation=0.0,
        scale=Vector2(x=1.0, y=1.0),
        anchor=Vector2(x=0.0, y=0.0),
    )
    assert visibility == VisibilityWindow(start=None, end=None)

    with pytest.raises(FrozenInstanceError):
        resolution.width = 1280  # type: ignore[misc]


def test_project_defaults_use_single_engine_version_constant() -> None:
    project = Project(style_pack=StylePackRef(id="crude", version="1.0.0"))

    assert project.resolution == Resolution(width=1920, height=1080)
    assert project.fps == 30.0
    assert project.seed == 0
    assert project.wpm == 150.0
    assert project.engine_version == anima.__version__
    assert project.scenes == ()


def test_every_ordered_collection_is_normalized_without_retained_list_aliases() -> None:
    layers: list[Layer] = [Layer(id="background")]
    scenes: list[Scene] = [Scene(id="intro", layers=layers)]
    project = Project(
        style_pack=StylePackRef(id="flat", version="2.1.0"),
        scenes=scenes,
    )

    layers.append(Layer(id="foreground"))
    scenes.clear()

    assert isinstance(project.scenes, tuple)
    assert isinstance(project.scenes[0].layers, tuple)
    assert tuple(layer.id for layer in project.scenes[0].layers) == ("background",)


def test_kw_only_construction_is_enforced() -> None:
    with pytest.raises(TypeError):
        Resolution(1280, 720)  # type: ignore[misc]

    with pytest.raises(TypeError):
        StylePackRef("crude", "1.0.0")  # type: ignore[misc]


def test_package_ships_typed_marker_and_reads_version_from_version_module() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")

    assert Path("src/anima/py.typed").is_file()
    assert 'dynamic = ["version"]' in pyproject
    assert 'version = {attr = "anima._version.__version__"}' in pyproject


def test_public_contract_documentation_covers_authoring_and_downstream_boundaries() -> None:
    contract = Path("docs/scene-graph-contract.md").read_text(encoding="utf-8")

    for required in (
        "project: Project",
        "## Units and defaults",
        "## Immutability and rebuild lifecycle",
        "## Node payloads",
        "## Ordering and traversal",
        "## Structured errors",
        "## JSON compatibility policy",
        "## Downstream boundaries",
        "no implicit migration",
    ):
        assert required in contract
