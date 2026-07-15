from __future__ import annotations

import json

import pytest

from anima.scene_graph import (
    Project,
    SceneGraphDecodeError,
    SceneGraphValidationError,
    StylePackRef,
    dumps_project,
    loads_project,
    project_from_dict,
    project_to_dict,
)


def test_semantic_round_trip_and_decode_encode_byte_stability(
    representative_project: Project,
) -> None:
    encoded = dumps_project(representative_project)
    decoded = loads_project(encoded)

    assert decoded == representative_project
    assert dumps_project(decoded) == encoded


def test_repeated_serialization_is_identical_and_canonical(
    representative_project: Project,
) -> None:
    first = dumps_project(representative_project)
    second = dumps_project(representative_project)

    assert first == second
    assert first.endswith("\n")
    assert not first.endswith("\n\n")
    assert "世界 🌍" in first
    assert "\\u4e16" not in first
    assert first.startswith('{\n  "project":')
    assert first.rstrip().endswith('"schema_version": "1.0"\n}')


def test_project_to_dict_wraps_schema_and_emits_every_default() -> None:
    payload = project_to_dict(Project(style_pack=StylePackRef(id="flat", version="1.0.0")))

    assert payload == {
        "schema_version": "1.0",
        "project": {
            "engine_version": "0.0.0.dev0",
            "fps": 30.0,
            "resolution": {"height": 1080, "width": 1920},
            "scenes": [],
            "seed": 0,
            "style_pack": {"id": "flat", "version": "1.0.0"},
            "wpm": 150.0,
        },
    }
    assert project_from_dict(payload) == Project(
        style_pack=StylePackRef(id="flat", version="1.0.0")
    )


def test_declared_collection_order_survives_round_trip(representative_project: Project) -> None:
    decoded = loads_project(dumps_project(representative_project))

    assert tuple(scene.id for scene in decoded.scenes) == ("intro", "outro")
    assert tuple(layer.id for layer in decoded.scenes[0].layers) == ("art", "labels")
    assert tuple(node.id for node in decoded.scenes[0].layers[0].nodes) == (
        "background",
        "sun",
        "cloud",
        "mountain",
        "route",
    )


@pytest.mark.parametrize(
    ("payload", "code", "path"),
    [
        ('{"schema_version":"1.0","project":{},"project":{}}', "JSON.DUPLICATE_KEY", "$.project"),
        (
            '{"schema_version":"1.0","project":{"fps":NaN}}',
            "JSON.INVALID_CONSTANT",
            "$.project.fps",
        ),
        ('{"schema_version":"1.0","project":', "JSON.INVALID", "$"),
        ('{"project":{}}', "SCHEMA.MISSING_VERSION", "$.schema_version"),
        (
            '{"schema_version":"2.0","project":{}}',
            "SCHEMA.UNSUPPORTED_VERSION",
            "$.schema_version",
        ),
        (
            '{"schema_version":"1.0","project":{},"extra":true}',
            "JSON.EXTRA_KEY",
            "$.extra",
        ),
        ('{"schema_version":"1.0"}', "JSON.MISSING_KEY", "$.project"),
        ('{"schema_version":1.0,"project":{}}', "JSON.WRONG_TYPE", "$.schema_version"),
    ],
)
def test_strict_json_wrapper_rejects_malformed_payloads(
    payload: str,
    code: str,
    path: str,
) -> None:
    with pytest.raises(SceneGraphDecodeError) as caught:
        loads_project(payload)

    assert caught.value.code == code
    assert caught.value.path == path


def test_decoder_rejects_missing_default_field(representative_project: Project) -> None:
    payload = project_to_dict(representative_project)
    project_payload = payload["project"]
    assert isinstance(project_payload, dict)
    del project_payload["wpm"]

    with pytest.raises(SceneGraphDecodeError) as caught:
        project_from_dict(payload)

    assert caught.value.code == "JSON.MISSING_KEY"
    assert caught.value.path == "$.project.wpm"


def test_decoder_rejects_unknown_node_geometry_and_command_discriminators(
    representative_project: Project,
) -> None:
    wrapper = project_to_dict(representative_project)
    project_payload = wrapper["project"]
    assert isinstance(project_payload, dict)
    scenes = project_payload["scenes"]
    assert isinstance(scenes, list)
    first_scene = scenes[0]
    assert isinstance(first_scene, dict)
    layers = first_scene["layers"]
    assert isinstance(layers, list)
    first_layer = layers[0]
    assert isinstance(first_layer, dict)
    nodes = first_layer["nodes"]
    assert isinstance(nodes, list)

    node = nodes[0]
    assert isinstance(node, dict)
    node["type"] = "sprite"
    with pytest.raises(SceneGraphDecodeError) as unknown_node:
        project_from_dict(wrapper)
    assert unknown_node.value.code == "JSON.UNKNOWN_DISCRIMINATOR"
    assert unknown_node.value.path.endswith(".type")

    wrapper = project_to_dict(representative_project)
    project_payload = wrapper["project"]
    assert isinstance(project_payload, dict)
    scenes = project_payload["scenes"]
    assert isinstance(scenes, list)
    first_scene = scenes[0]
    assert isinstance(first_scene, dict)
    layers = first_scene["layers"]
    assert isinstance(layers, list)
    first_layer = layers[0]
    assert isinstance(first_layer, dict)
    nodes = first_layer["nodes"]
    assert isinstance(nodes, list)
    shape = nodes[0]
    assert isinstance(shape, dict)
    geometry = shape["geometry"]
    assert isinstance(geometry, dict)
    geometry["type"] = "triangle"
    with pytest.raises(SceneGraphDecodeError) as unknown_geometry:
        project_from_dict(wrapper)
    assert unknown_geometry.value.code == "JSON.UNKNOWN_DISCRIMINATOR"
    assert unknown_geometry.value.path.endswith(".geometry.type")

    wrapper = project_to_dict(representative_project)
    project_payload = wrapper["project"]
    assert isinstance(project_payload, dict)
    scenes = project_payload["scenes"]
    assert isinstance(scenes, list)
    first_scene = scenes[0]
    assert isinstance(first_scene, dict)
    layers = first_scene["layers"]
    assert isinstance(layers, list)
    first_layer = layers[0]
    assert isinstance(first_layer, dict)
    nodes = first_layer["nodes"]
    assert isinstance(nodes, list)
    path_node = nodes[4]
    assert isinstance(path_node, dict)
    commands = path_node["commands"]
    assert isinstance(commands, list)
    command = commands[0]
    assert isinstance(command, dict)
    command["type"] = "quadratic_to"
    with pytest.raises(SceneGraphDecodeError) as unknown_command:
        project_from_dict(wrapper)
    assert unknown_command.value.code == "JSON.UNKNOWN_DISCRIMINATOR"
    assert unknown_command.value.path.endswith(".commands[0].type")


def test_decoder_rejects_wrong_primitives_and_non_finite_python_values(
    representative_project: Project,
) -> None:
    wrapper = project_to_dict(representative_project)
    project_payload = wrapper["project"]
    assert isinstance(project_payload, dict)
    project_payload["fps"] = True
    with pytest.raises(SceneGraphDecodeError) as boolean_number:
        project_from_dict(wrapper)
    assert boolean_number.value.code == "JSON.WRONG_TYPE"
    assert boolean_number.value.path == "$.project.fps"

    wrapper = project_to_dict(representative_project)
    project_payload = wrapper["project"]
    assert isinstance(project_payload, dict)
    project_payload["fps"] = float("inf")
    with pytest.raises(SceneGraphDecodeError) as infinity:
        project_from_dict(wrapper)
    assert infinity.value.code == "JSON.INVALID_NUMBER"
    assert infinity.value.path == "$.project.fps"


def test_decoder_converts_huge_integer_overflow_into_structured_error(
    representative_project: Project,
) -> None:
    wrapper = project_to_dict(representative_project)
    project_payload = wrapper["project"]
    assert isinstance(project_payload, dict)
    project_payload["fps"] = 10**10_000

    with pytest.raises(SceneGraphDecodeError) as caught:
        project_from_dict(wrapper)

    assert caught.value.code == "JSON.INVALID_NUMBER"
    assert caught.value.path == "$.project.fps"


def test_decoder_rejects_escaped_isolated_unicode_surrogate(
    representative_project: Project,
) -> None:
    encoded = dumps_project(representative_project).replace("Anima — 世界 🌍", "\\ud800")

    with pytest.raises(SceneGraphDecodeError) as caught:
        loads_project(encoded)

    assert caught.value.code == "VALUE.INVALID_UNICODE"
    assert caught.value.path.endswith(".content")


def test_decoder_runs_same_graph_invariant_validator(representative_project: Project) -> None:
    wrapper = project_to_dict(representative_project)
    project_payload = wrapper["project"]
    assert isinstance(project_payload, dict)
    scenes = project_payload["scenes"]
    assert isinstance(scenes, list)
    second_scene = scenes[1]
    assert isinstance(second_scene, dict)
    layers = second_scene["layers"]
    assert isinstance(layers, list)
    layer = layers[0]
    assert isinstance(layer, dict)
    nodes = layer["nodes"]
    assert isinstance(nodes, list)
    node = nodes[0]
    assert isinstance(node, dict)
    node["id"] = "sun"

    with pytest.raises(SceneGraphValidationError) as caught:
        project_from_dict(wrapper)

    assert caught.value.code == "GRAPH.DUPLICATE_NODE_ID"
    assert caught.value.path.startswith("$.project.scenes[1]")


def test_loads_project_accepts_utf8_bytes(representative_project: Project) -> None:
    encoded = dumps_project(representative_project).encode("utf-8")
    assert loads_project(encoded) == representative_project


def test_loads_project_rejects_invalid_utf8() -> None:
    with pytest.raises(SceneGraphDecodeError) as caught:
        loads_project(b"\xff")
    assert caught.value.code == "JSON.INVALID_UTF8"
    assert caught.value.path == "$"


def test_raw_json_parser_rejects_duplicate_nested_keys() -> None:
    minimal = dumps_project(Project(style_pack=StylePackRef(id="flat", version="1.0.0")))
    parsed = json.loads(minimal)
    assert parsed["schema_version"] == "1.0"
    duplicate = minimal.replace('"width": 1920', '"width": 1920,\n        "width": 1920')

    with pytest.raises(SceneGraphDecodeError) as caught:
        loads_project(duplicate)
    assert caught.value.code == "JSON.DUPLICATE_KEY"
    assert caught.value.path == "$.project.resolution.width"
