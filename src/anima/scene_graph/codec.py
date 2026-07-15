"""Strict schema-version 1.0 codec for immutable scene graphs."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Final, NoReturn, TypedDict, cast

from anima.scene_graph._validation import has_unicode_surrogate
from anima.scene_graph.errors import SceneGraphDecodeError, SceneGraphValidationError
from anima.scene_graph.model import Layer, Project, Scene
from anima.scene_graph.nodes import (
    Circle,
    ClosePath,
    CubicTo,
    Ellipse,
    Group,
    LineTo,
    MoveTo,
    Node,
    Path,
    PathCommandPayload,
    Polygon,
    Rectangle,
    Shape,
    ShapeGeometry,
    Text,
)
from anima.scene_graph.values import (
    Resolution,
    StylePackRef,
    Transform,
    Vector2,
    VisibilityWindow,
)

SCHEMA_VERSION: Final = "1.0"


@dataclass(frozen=True, slots=True, kw_only=True)
class _ObjectPairs:
    pairs: tuple[tuple[str, object], ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class _InvalidConstant:
    token: str


class _CommonNode(TypedDict):
    id: str
    layer: str
    style_role: str | None
    transform: Transform
    visibility: VisibilityWindow
    z: int


def _vector_to_dict(vector: Vector2) -> dict[str, object]:
    return {"x": vector.x, "y": vector.y}


def _transform_to_dict(transform: Transform) -> dict[str, object]:
    return {
        "anchor": _vector_to_dict(transform.anchor),
        "position": _vector_to_dict(transform.position),
        "rotation": transform.rotation,
        "scale": _vector_to_dict(transform.scale),
    }


def _visibility_to_dict(visibility: VisibilityWindow) -> dict[str, object]:
    return {"end": visibility.end, "start": visibility.start}


def _geometry_to_dict(geometry: ShapeGeometry) -> dict[str, object]:
    if isinstance(geometry, Rectangle):
        return {"height": geometry.height, "type": "rectangle", "width": geometry.width}
    if isinstance(geometry, Circle):
        return {"radius": geometry.radius, "type": "circle"}
    if isinstance(geometry, Ellipse):
        return {
            "radius_x": geometry.radius_x,
            "radius_y": geometry.radius_y,
            "type": "ellipse",
        }
    return {
        "points": [_vector_to_dict(point) for point in geometry.points],
        "type": "polygon",
    }


def _command_to_dict(command: PathCommandPayload) -> dict[str, object]:
    if isinstance(command, MoveTo):
        return {"point": _vector_to_dict(command.point), "type": "move_to"}
    if isinstance(command, LineTo):
        return {"point": _vector_to_dict(command.point), "type": "line_to"}
    if isinstance(command, CubicTo):
        return {
            "control1": _vector_to_dict(command.control1),
            "control2": _vector_to_dict(command.control2),
            "point": _vector_to_dict(command.point),
            "type": "cubic_to",
        }
    return {"type": "close_path"}


def _node_common_to_dict(node: Node) -> dict[str, object]:
    return {
        "id": node.id,
        "layer": node.layer,
        "style_role": node.style_role,
        "transform": _transform_to_dict(node.transform),
        "type": node.node_type,
        "visibility": _visibility_to_dict(node.visibility),
        "z": node.z,
    }


def _node_to_dict(node: Node) -> dict[str, object]:
    payload = _node_common_to_dict(node)
    if isinstance(node, Shape):
        payload["geometry"] = _geometry_to_dict(node.geometry)
    elif isinstance(node, Path):
        payload["commands"] = [_command_to_dict(command) for command in node.commands]
    elif isinstance(node, Text):
        payload["content"] = node.content
        payload["font_role"] = node.font_role
        payload["size"] = node.size
    elif isinstance(node, Group):
        payload["children"] = [_node_to_dict(child) for child in node.children]
    else:
        raise TypeError(f"unsupported node class: {type(node).__name__}")
    return payload


def project_to_dict(project: Project) -> dict[str, object]:
    """Convert project into complete schema wrapper using JSON-compatible values."""
    if not isinstance(project, Project):
        raise TypeError("project must be Project")
    project_payload: dict[str, object] = {
        "engine_version": project.engine_version,
        "fps": project.fps,
        "resolution": {
            "height": project.resolution.height,
            "width": project.resolution.width,
        },
        "scenes": [
            {
                "id": scene.id,
                "layers": [
                    {
                        "id": layer.id,
                        "nodes": [_node_to_dict(node) for node in layer.nodes],
                    }
                    for layer in scene.layers
                ],
            }
            for scene in project.scenes
        ],
        "seed": project.seed,
        "style_pack": {"id": project.style_pack.id, "version": project.style_pack.version},
        "wpm": project.wpm,
    }
    return {"project": project_payload, "schema_version": SCHEMA_VERSION}


def dumps_project(project: Project) -> str:
    """Write deterministic UTF-8-compatible JSON text with one trailing newline."""
    return (
        json.dumps(
            project_to_dict(project),
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
        )
        + "\n"
    )


def _pairs_hook(pairs: list[tuple[str, object]]) -> _ObjectPairs:
    return _ObjectPairs(pairs=tuple(pairs))


def _constant_hook(token: str) -> _InvalidConstant:
    return _InvalidConstant(token=token)


def _child_path(path: str, key: str) -> str:
    return f"{path}.{key}"


def _normalize_json(value: object, *, path: str) -> object:
    if isinstance(value, _InvalidConstant):
        raise SceneGraphDecodeError(
            code="JSON.INVALID_CONSTANT",
            path=path,
            message=f"invalid JSON numeric constant {value.token!r}",
        )
    if isinstance(value, _ObjectPairs):
        result: dict[str, object] = {}
        for key, child in value.pairs:
            child_path = _child_path(path, key)
            if key in result:
                raise SceneGraphDecodeError(
                    code="JSON.DUPLICATE_KEY",
                    path=child_path,
                    message=f"duplicate object key {key!r}",
                )
            result[key] = _normalize_json(child, path=child_path)
        return result
    if isinstance(value, list):
        return [
            _normalize_json(child, path=f"{path}[{index}]")
            for index, child in enumerate(value)
        ]
    return value


def _decode_error(*, code: str, path: str, message: str) -> SceneGraphDecodeError:
    return SceneGraphDecodeError(code=code, path=path, message=message)


def _expect_object(value: object, *, path: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise _decode_error(code="JSON.WRONG_TYPE", path=path, message="expected object")
    for key in value:
        if not isinstance(key, str):
            raise _decode_error(
                code="JSON.WRONG_TYPE",
                path=path,
                message="object keys must be strings",
            )
    return cast(dict[str, object], value)


def _expect_exact_object(
    value: object,
    *,
    keys: frozenset[str],
    path: str,
) -> dict[str, object]:
    payload = _expect_object(value, path=path)
    missing = sorted(keys.difference(payload))
    if missing:
        key = missing[0]
        raise _decode_error(
            code="JSON.MISSING_KEY",
            path=_child_path(path, key),
            message=f"missing required key {key!r}",
        )
    extra = sorted(set(payload).difference(keys))
    if extra:
        key = extra[0]
        raise _decode_error(
            code="JSON.EXTRA_KEY",
            path=_child_path(path, key),
            message=f"unexpected key {key!r}",
        )
    return payload


def _expect_array(value: object, *, path: str) -> list[object]:
    if not isinstance(value, list):
        raise _decode_error(code="JSON.WRONG_TYPE", path=path, message="expected array")
    return cast(list[object], value)


def _expect_string(value: object, *, path: str) -> str:
    if not isinstance(value, str):
        raise _decode_error(code="JSON.WRONG_TYPE", path=path, message="expected string")
    if has_unicode_surrogate(value):
        raise _decode_error(
            code="VALUE.INVALID_UNICODE",
            path=path,
            message="string contains isolated UTF-16 surrogate code point",
        )
    return value


def _expect_identifier(value: object, *, path: str) -> str:
    result = _expect_string(value, path=path)
    if not result.strip():
        raise SceneGraphDecodeError(
            code="VALUE.EMPTY_IDENTIFIER",
            path=path,
            message="identifier must contain non-whitespace characters",
            offending_id=result,
        )
    return result


def _expect_integer(value: object, *, path: str) -> int:
    if type(value) is not int:
        raise _decode_error(
            code="JSON.WRONG_TYPE",
            path=path,
            message="expected integer; boolean is not accepted",
        )
    return value


def _expect_positive_integer(value: object, *, path: str) -> int:
    result = _expect_integer(value, path=path)
    if result <= 0:
        raise _decode_error(code="VALUE.NON_POSITIVE", path=path, message="expected > 0")
    return result


def _expect_number(value: object, *, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise _decode_error(
            code="JSON.WRONG_TYPE",
            path=path,
            message="expected number; boolean is not accepted",
        )
    try:
        result = float(value)
    except OverflowError as error:
        raise _decode_error(
            code="JSON.INVALID_NUMBER",
            path=path,
            message="number is outside finite floating-point range",
        ) from error
    if not math.isfinite(result):
        raise _decode_error(
            code="JSON.INVALID_NUMBER",
            path=path,
            message="expected finite number",
        )
    return result


def _expect_positive_number(value: object, *, path: str) -> float:
    result = _expect_number(value, path=path)
    if result <= 0.0:
        raise _decode_error(code="VALUE.NON_POSITIVE", path=path, message="expected > 0")
    return result


def _decode_vector(value: object, *, path: str) -> Vector2:
    payload = _expect_exact_object(value, keys=frozenset(("x", "y")), path=path)
    return Vector2(
        x=_expect_number(payload["x"], path=f"{path}.x"),
        y=_expect_number(payload["y"], path=f"{path}.y"),
    )


def _decode_transform(value: object, *, path: str) -> Transform:
    payload = _expect_exact_object(
        value,
        keys=frozenset(("anchor", "position", "rotation", "scale")),
        path=path,
    )
    return Transform(
        anchor=_decode_vector(payload["anchor"], path=f"{path}.anchor"),
        position=_decode_vector(payload["position"], path=f"{path}.position"),
        rotation=_expect_number(payload["rotation"], path=f"{path}.rotation"),
        scale=_decode_vector(payload["scale"], path=f"{path}.scale"),
    )


def _decode_optional_number(value: object, *, path: str) -> float | None:
    if value is None:
        return None
    return _expect_number(value, path=path)


def _decode_visibility(value: object, *, path: str) -> VisibilityWindow:
    payload = _expect_exact_object(value, keys=frozenset(("end", "start")), path=path)
    start = _decode_optional_number(payload["start"], path=f"{path}.start")
    end = _decode_optional_number(payload["end"], path=f"{path}.end")
    if start is not None and start < 0.0:
        raise _decode_error(
            code="VISIBILITY.NEGATIVE_BOUNDARY",
            path=f"{path}.start",
            message="visibility boundary cannot be negative",
        )
    if end is not None and end < 0.0:
        raise _decode_error(
            code="VISIBILITY.NEGATIVE_BOUNDARY",
            path=f"{path}.end",
            message="visibility boundary cannot be negative",
        )
    if start is not None and end is not None and start > end:
        raise _decode_error(
            code="VISIBILITY.REVERSED_INTERVAL",
            path=path,
            message="start cannot be greater than end",
        )
    return VisibilityWindow(start=start, end=end)


def _decode_geometry(value: object, *, path: str) -> ShapeGeometry:
    raw = _expect_object(value, path=path)
    if "type" not in raw:
        raise _decode_error(
            code="JSON.MISSING_KEY",
            path=f"{path}.type",
            message="missing geometry discriminator",
        )
    discriminator = _expect_string(raw["type"], path=f"{path}.type")
    if discriminator == "rectangle":
        payload = _expect_exact_object(
            raw,
            keys=frozenset(("height", "type", "width")),
            path=path,
        )
        return Rectangle(
            width=_expect_positive_number(payload["width"], path=f"{path}.width"),
            height=_expect_positive_number(payload["height"], path=f"{path}.height"),
        )
    if discriminator == "circle":
        payload = _expect_exact_object(raw, keys=frozenset(("radius", "type")), path=path)
        return Circle(radius=_expect_positive_number(payload["radius"], path=f"{path}.radius"))
    if discriminator == "ellipse":
        payload = _expect_exact_object(
            raw,
            keys=frozenset(("radius_x", "radius_y", "type")),
            path=path,
        )
        return Ellipse(
            radius_x=_expect_positive_number(payload["radius_x"], path=f"{path}.radius_x"),
            radius_y=_expect_positive_number(payload["radius_y"], path=f"{path}.radius_y"),
        )
    if discriminator == "polygon":
        payload = _expect_exact_object(raw, keys=frozenset(("points", "type")), path=path)
        points_payload = _expect_array(payload["points"], path=f"{path}.points")
        if len(points_payload) < 3:
            raise _decode_error(
                code="GEOMETRY.POLYGON_TOO_FEW_POINTS",
                path=f"{path}.points",
                message="polygon requires at least three points",
            )
        return Polygon(
            points=tuple(
                _decode_vector(point, path=f"{path}.points[{index}]")
                for index, point in enumerate(points_payload)
            )
        )
    raise _decode_error(
        code="JSON.UNKNOWN_DISCRIMINATOR",
        path=f"{path}.type",
        message=f"unknown geometry type {discriminator!r}",
    )


def _decode_command(value: object, *, path: str) -> PathCommandPayload:
    raw = _expect_object(value, path=path)
    if "type" not in raw:
        raise _decode_error(
            code="JSON.MISSING_KEY",
            path=f"{path}.type",
            message="missing path-command discriminator",
        )
    discriminator = _expect_string(raw["type"], path=f"{path}.type")
    if discriminator in ("move_to", "line_to"):
        payload = _expect_exact_object(raw, keys=frozenset(("point", "type")), path=path)
        point = _decode_vector(payload["point"], path=f"{path}.point")
        if discriminator == "move_to":
            return MoveTo(point=point)
        return LineTo(point=point)
    if discriminator == "cubic_to":
        payload = _expect_exact_object(
            raw,
            keys=frozenset(("control1", "control2", "point", "type")),
            path=path,
        )
        return CubicTo(
            control1=_decode_vector(payload["control1"], path=f"{path}.control1"),
            control2=_decode_vector(payload["control2"], path=f"{path}.control2"),
            point=_decode_vector(payload["point"], path=f"{path}.point"),
        )
    if discriminator == "close_path":
        _expect_exact_object(raw, keys=frozenset(("type",)), path=path)
        return ClosePath()
    raise _decode_error(
        code="JSON.UNKNOWN_DISCRIMINATOR",
        path=f"{path}.type",
        message=f"unknown path command type {discriminator!r}",
    )


def _decode_common_node(payload: dict[str, object], *, path: str) -> _CommonNode:
    style_role_value = payload["style_role"]
    style_role = (
        None
        if style_role_value is None
        else _expect_identifier(style_role_value, path=f"{path}.style_role")
    )
    return {
        "id": _expect_identifier(payload["id"], path=f"{path}.id"),
        "layer": _expect_identifier(payload["layer"], path=f"{path}.layer"),
        "style_role": style_role,
        "transform": _decode_transform(payload["transform"], path=f"{path}.transform"),
        "visibility": _decode_visibility(payload["visibility"], path=f"{path}.visibility"),
        "z": _expect_integer(payload["z"], path=f"{path}.z"),
    }


def _translate_path_validation(error: SceneGraphValidationError, *, path: str) -> NoReturn:
    translated_path = error.path
    if translated_path.startswith("$.path"):
        translated_path = path + translated_path[len("$.path") :]
    raise SceneGraphDecodeError(
        code=error.code,
        path=translated_path,
        message=error.message,
        offending_id=error.offending_id,
    ) from error


def _decode_node(value: object, *, path: str) -> Node:
    raw = _expect_object(value, path=path)
    if "type" not in raw:
        raise _decode_error(
            code="JSON.MISSING_KEY",
            path=f"{path}.type",
            message="missing node discriminator",
        )
    discriminator = _expect_string(raw["type"], path=f"{path}.type")
    common_keys = frozenset(
        ("id", "layer", "style_role", "transform", "type", "visibility", "z")
    )
    if discriminator == "shape":
        payload = _expect_exact_object(raw, keys=common_keys | {"geometry"}, path=path)
        common = _decode_common_node(payload, path=path)
        return Shape(
            geometry=_decode_geometry(payload["geometry"], path=f"{path}.geometry"),
            **common,
        )
    if discriminator == "path":
        payload = _expect_exact_object(raw, keys=common_keys | {"commands"}, path=path)
        common = _decode_common_node(payload, path=path)
        commands_payload = _expect_array(payload["commands"], path=f"{path}.commands")
        commands = tuple(
            _decode_command(command, path=f"{path}.commands[{index}]")
            for index, command in enumerate(commands_payload)
        )
        try:
            return Path(commands=commands, **common)
        except SceneGraphValidationError as error:
            _translate_path_validation(error, path=path)
    if discriminator == "text":
        payload = _expect_exact_object(
            raw,
            keys=common_keys | {"content", "font_role", "size"},
            path=path,
        )
        common = _decode_common_node(payload, path=path)
        return Text(
            content=_expect_string(payload["content"], path=f"{path}.content"),
            font_role=_expect_identifier(payload["font_role"], path=f"{path}.font_role"),
            size=_expect_positive_number(payload["size"], path=f"{path}.size"),
            **common,
        )
    if discriminator == "group":
        payload = _expect_exact_object(raw, keys=common_keys | {"children"}, path=path)
        common = _decode_common_node(payload, path=path)
        children_payload = _expect_array(payload["children"], path=f"{path}.children")
        return Group(
            children=tuple(
                _decode_node(child, path=f"{path}.children[{index}]")
                for index, child in enumerate(children_payload)
            ),
            **common,
        )
    raise _decode_error(
        code="JSON.UNKNOWN_DISCRIMINATOR",
        path=f"{path}.type",
        message=f"unknown node type {discriminator!r}",
    )


def _decode_layer(value: object, *, path: str) -> Layer:
    payload = _expect_exact_object(value, keys=frozenset(("id", "nodes")), path=path)
    nodes_payload = _expect_array(payload["nodes"], path=f"{path}.nodes")
    return Layer(
        id=_expect_identifier(payload["id"], path=f"{path}.id"),
        nodes=tuple(
            _decode_node(node, path=f"{path}.nodes[{index}]")
            for index, node in enumerate(nodes_payload)
        ),
    )


def _decode_scene(value: object, *, path: str) -> Scene:
    payload = _expect_exact_object(value, keys=frozenset(("id", "layers")), path=path)
    layers_payload = _expect_array(payload["layers"], path=f"{path}.layers")
    return Scene(
        id=_expect_identifier(payload["id"], path=f"{path}.id"),
        layers=tuple(
            _decode_layer(layer, path=f"{path}.layers[{index}]")
            for index, layer in enumerate(layers_payload)
        ),
    )


def _decode_resolution(value: object, *, path: str) -> Resolution:
    payload = _expect_exact_object(value, keys=frozenset(("height", "width")), path=path)
    return Resolution(
        width=_expect_positive_integer(payload["width"], path=f"{path}.width"),
        height=_expect_positive_integer(payload["height"], path=f"{path}.height"),
    )


def _decode_style_pack(value: object, *, path: str) -> StylePackRef:
    payload = _expect_exact_object(value, keys=frozenset(("id", "version")), path=path)
    return StylePackRef(
        id=_expect_identifier(payload["id"], path=f"{path}.id"),
        version=_expect_identifier(payload["version"], path=f"{path}.version"),
    )


def project_from_dict(value: object) -> Project:
    """Strictly decode complete schema wrapper from JSON-compatible Python values."""
    wrapper = _expect_object(value, path="$")
    if "schema_version" not in wrapper:
        raise _decode_error(
            code="SCHEMA.MISSING_VERSION",
            path="$.schema_version",
            message="schema_version is required",
        )
    version = _expect_string(wrapper["schema_version"], path="$.schema_version")
    if version != SCHEMA_VERSION:
        raise _decode_error(
            code="SCHEMA.UNSUPPORTED_VERSION",
            path="$.schema_version",
            message=f"unsupported schema version {version!r}; supported: {SCHEMA_VERSION!r}",
        )
    wrapper = _expect_exact_object(
        wrapper,
        keys=frozenset(("project", "schema_version")),
        path="$",
    )
    payload = _expect_exact_object(
        wrapper["project"],
        keys=frozenset(
            (
                "engine_version",
                "fps",
                "resolution",
                "scenes",
                "seed",
                "style_pack",
                "wpm",
            )
        ),
        path="$.project",
    )
    scenes_payload = _expect_array(payload["scenes"], path="$.project.scenes")
    return Project(
        engine_version=_expect_identifier(
            payload["engine_version"],
            path="$.project.engine_version",
        ),
        fps=_expect_positive_number(payload["fps"], path="$.project.fps"),
        resolution=_decode_resolution(payload["resolution"], path="$.project.resolution"),
        scenes=tuple(
            _decode_scene(scene, path=f"$.project.scenes[{index}]")
            for index, scene in enumerate(scenes_payload)
        ),
        seed=_expect_integer(payload["seed"], path="$.project.seed"),
        style_pack=_decode_style_pack(payload["style_pack"], path="$.project.style_pack"),
        wpm=_expect_positive_number(payload["wpm"], path="$.project.wpm"),
    )


def loads_project(data: str | bytes) -> Project:
    """Decode strict UTF-8 JSON without accepting duplicate keys or NaN constants."""
    if isinstance(data, bytes):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as error:
            raise SceneGraphDecodeError(
                code="JSON.INVALID_UTF8",
                path="$",
                message="input is not valid UTF-8",
            ) from error
    elif isinstance(data, str):
        text = data
    else:
        raise TypeError("data must be str or bytes")

    try:
        parsed = cast(
            object,
            json.loads(
                text,
                object_pairs_hook=_pairs_hook,
                parse_constant=_constant_hook,
            ),
        )
    except json.JSONDecodeError as error:
        raise SceneGraphDecodeError(
            code="JSON.INVALID",
            path="$",
            message=f"invalid JSON at line {error.lineno}, column {error.colno}",
        ) from error

    normalized = _normalize_json(parsed, path="$")
    return project_from_dict(normalized)
