from __future__ import annotations

import json
from pathlib import Path

from anima.scene_graph import Project, dumps_project, loads_project, project_to_dict

FIXTURE_PATH = Path("tests/scene_graph/fixtures/project-v1.0.json")


def test_representative_project_matches_exact_checked_in_canonical_bytes(
    representative_project: Project,
) -> None:
    expected = FIXTURE_PATH.read_bytes()
    actual = dumps_project(representative_project).encode("utf-8")

    assert actual == expected


def test_contract_fixture_is_canonical_and_semantically_stable() -> None:
    raw = FIXTURE_PATH.read_bytes()
    decoded = loads_project(raw)

    assert dumps_project(decoded).encode("utf-8") == raw
    assert project_to_dict(decoded) == json.loads(raw)


def test_contract_fixture_covers_all_phase_one_discriminators() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    node_types: set[str] = set()
    geometry_types: set[str] = set()
    command_types: set[str] = set()

    def visit_node(node: dict[str, object]) -> None:
        node_type = node["type"]
        assert isinstance(node_type, str)
        node_types.add(node_type)
        geometry = node.get("geometry")
        if isinstance(geometry, dict):
            discriminator = geometry["type"]
            assert isinstance(discriminator, str)
            geometry_types.add(discriminator)
        commands = node.get("commands")
        if isinstance(commands, list):
            for command in commands:
                assert isinstance(command, dict)
                discriminator = command["type"]
                assert isinstance(discriminator, str)
                command_types.add(discriminator)
        children = node.get("children")
        if isinstance(children, list):
            for child in children:
                assert isinstance(child, dict)
                visit_node(child)

    project = payload["project"]
    assert isinstance(project, dict)
    scenes = project["scenes"]
    assert isinstance(scenes, list)
    for scene in scenes:
        assert isinstance(scene, dict)
        layers = scene["layers"]
        assert isinstance(layers, list)
        for layer in layers:
            assert isinstance(layer, dict)
            nodes = layer["nodes"]
            assert isinstance(nodes, list)
            for node in nodes:
                assert isinstance(node, dict)
                visit_node(node)

    assert node_types == {"shape", "path", "text", "group"}
    assert geometry_types == {"rectangle", "circle", "ellipse", "polygon"}
    assert command_types == {"move_to", "line_to", "cubic_to", "close_path"}


def test_contract_fixture_has_schema_wrapper_and_only_snake_case_keys() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert set(payload) == {"schema_version", "project"}

    def assert_keys(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                assert isinstance(key, str)
                assert key == key.lower()
                assert "-" not in key
                assert_keys(child)
        elif isinstance(value, list):
            for child in value:
                assert_keys(child)

    assert_keys(payload)
