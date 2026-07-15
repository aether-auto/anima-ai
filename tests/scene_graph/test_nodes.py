from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Literal

import pytest
from anima.scene_graph import (
    Circle,
    ClosePath,
    CubicTo,
    Ellipse,
    Group,
    Layer,
    LineTo,
    MoveTo,
    Node,
    Path,
    Polygon,
    Project,
    Rectangle,
    Scene,
    SceneGraphValidationError,
    Shape,
    StylePackRef,
    Text,
    Transform,
    Vector2,
)


def _project(*layers: Layer) -> Project:
    return Project(
        style_pack=StylePackRef(id="crude", version="1.0.0"),
        scenes=(Scene(id="scene", layers=layers),),
    )


def test_node_is_abstract_and_phase_one_subtypes_are_immutable() -> None:
    with pytest.raises(TypeError):
        Node(id="base", layer="art")  # type: ignore[abstract]

    shape = Shape(
        id="box",
        layer="art",
        geometry=Rectangle(width=10.0, height=20.0),
    )
    with pytest.raises(FrozenInstanceError):
        shape.z = 2  # type: ignore[misc]


def test_shape_supports_every_geometry_variant() -> None:
    geometries = (
        Rectangle(width=10.0, height=20.0),
        Circle(radius=5.0),
        Ellipse(radius_x=6.0, radius_y=3.0),
        Polygon(
            points=[
                Vector2(x=0.0, y=0.0),
                Vector2(x=2.0, y=0.0),
                Vector2(x=1.0, y=2.0),
            ]
        ),
    )

    nodes = tuple(
        Shape(id=f"shape-{index}", layer="art", geometry=geometry)
        for index, geometry in enumerate(geometries)
    )
    project = _project(Layer(id="art", nodes=nodes))

    assert tuple(node.geometry for node in project.scenes[0].layers[0].nodes) == geometries
    assert isinstance(geometries[-1].points, tuple)  # type: ignore[union-attr]


def test_polygon_requires_at_least_three_points() -> None:
    with pytest.raises(SceneGraphValidationError) as caught:
        Polygon(points=(Vector2(), Vector2(x=1.0)))

    assert caught.value.code == "GEOMETRY.POLYGON_TOO_FEW_POINTS"
    assert caught.value.path == "$.polygon.points"


def test_path_supports_every_command_and_normalizes_commands() -> None:
    commands = [
        MoveTo(point=Vector2(x=0.0, y=0.0)),
        LineTo(point=Vector2(x=10.0, y=0.0)),
        CubicTo(
            control1=Vector2(x=12.0, y=0.0),
            control2=Vector2(x=12.0, y=10.0),
            point=Vector2(x=10.0, y=10.0),
        ),
        ClosePath(),
    ]
    path = Path(id="outline", layer="art", commands=commands)
    commands.clear()

    assert isinstance(path.commands, tuple)
    assert tuple(type(command) for command in path.commands) == (
        MoveTo,
        LineTo,
        CubicTo,
        ClosePath,
    )


@pytest.mark.parametrize(
    ("commands", "code"),
    [
        ((), "PATH.EMPTY"),
        ((LineTo(point=Vector2()),), "PATH.INITIAL_MOVE_REQUIRED"),
        ((MoveTo(point=Vector2()), ClosePath()), "PATH.INVALID_CLOSE"),
        (
            (
                MoveTo(point=Vector2()),
                LineTo(point=Vector2(x=1.0)),
                ClosePath(),
                LineTo(point=Vector2(x=2.0)),
            ),
            "PATH.MOVE_REQUIRED_AFTER_CLOSE",
        ),
    ],
)
def test_path_rejects_structurally_invalid_command_sequences(
    commands: tuple[object, ...],
    code: str,
) -> None:
    with pytest.raises(SceneGraphValidationError) as caught:
        Path(id="bad", layer="art", commands=commands)  # type: ignore[arg-type]

    assert caught.value.code == code
    assert caught.value.offending_id == "bad"


def test_path_allows_move_to_to_start_or_replace_empty_subpaths() -> None:
    path = Path(
        id="moves",
        layer="art",
        commands=(
            MoveTo(point=Vector2()),
            MoveTo(point=Vector2(x=1.0)),
            LineTo(point=Vector2(x=2.0)),
        ),
    )

    assert tuple(command.command_type for command in path.commands) == (
        "move_to",
        "move_to",
        "line_to",
    )


def test_closed_phase_one_unions_reject_runtime_subclasses() -> None:
    class UnsupportedNode(Node):
        @property
        def node_type(self) -> Literal["shape"]:
            return "shape"

    class RectangleExtension(Rectangle):
        pass

    class LineExtension(LineTo):
        pass

    unsupported_node = UnsupportedNode(id="sprite", layer="art")
    with pytest.raises(SceneGraphValidationError) as node_error:
        Layer(id="art", nodes=(unsupported_node,))
    assert node_error.value.code == "NODE.UNSUPPORTED_TYPE"
    assert node_error.value.offending_id == "sprite"

    with pytest.raises(SceneGraphValidationError) as geometry_error:
        Shape(
            id="extended-shape",
            layer="art",
            geometry=RectangleExtension(width=1.0, height=1.0),
        )
    assert geometry_error.value.code == "NODE.INVALID_GEOMETRY"
    assert geometry_error.value.offending_id == "extended-shape"

    with pytest.raises(SceneGraphValidationError) as command_error:
        Path(
            id="extended-path",
            layer="art",
            commands=(
                MoveTo(point=Vector2()),
                LineExtension(point=Vector2(x=1.0)),
            ),
        )
    assert command_error.value.code == "VALUE.INVALID_MODEL"
    assert command_error.value.offending_id == "extended-path"


def test_text_preserves_unicode_content_and_group_owns_local_children() -> None:
    children = [
        Text(
            id="title",
            layer="labels",
            content="Zażółć gęślą jaźń — 你好 👋",
            font_role="heading",
            size=48.0,
            transform=Transform(position=Vector2(x=12.0, y=24.0)),
        )
    ]
    group = Group(id="card", layer="labels", children=children)
    children.clear()

    assert isinstance(group.children, tuple)
    assert group.children[0].transform.position == Vector2(x=12.0, y=24.0)
    assert "你好" in group.children[0].content  # type: ignore[union-attr]


def test_project_rejects_duplicate_scene_and_scene_local_layer_ids() -> None:
    style_pack = StylePackRef(id="crude", version="1.0.0")
    with pytest.raises(SceneGraphValidationError) as scenes:
        Project(
            style_pack=style_pack,
            scenes=(Scene(id="same"), Scene(id="same")),
        )
    assert scenes.value.code == "GRAPH.DUPLICATE_SCENE_ID"
    assert scenes.value.offending_id == "same"

    with pytest.raises(SceneGraphValidationError) as layers:
        Project(
            style_pack=style_pack,
            scenes=(Scene(id="scene", layers=(Layer(id="same"), Layer(id="same"))),),
        )
    assert layers.value.code == "GRAPH.DUPLICATE_LAYER_ID"
    assert layers.value.offending_id == "same"


def test_project_rejects_project_wide_nested_node_id_collisions_without_renaming() -> None:
    first = Shape(id="shared", layer="art", geometry=Circle(radius=2.0))
    nested = Text(
        id="shared",
        layer="labels",
        content="collision",
        font_role="body",
        size=20.0,
    )
    group = Group(id="group", layer="labels", children=(nested,))

    with pytest.raises(SceneGraphValidationError) as caught:
        Project(
            style_pack=StylePackRef(id="crude", version="1.0.0"),
            scenes=(
                Scene(id="one", layers=(Layer(id="art", nodes=(first,)),)),
                Scene(id="two", layers=(Layer(id="labels", nodes=(group,)),)),
            ),
        )

    assert caught.value.code == "GRAPH.DUPLICATE_NODE_ID"
    assert caught.value.offending_id == "shared"
    assert nested.id == "shared"


def test_project_rejects_layer_mismatch_for_nested_nodes() -> None:
    child = Shape(id="child", layer="wrong", geometry=Circle(radius=1.0))
    group = Group(id="group", layer="art", children=(child,))

    with pytest.raises(SceneGraphValidationError) as caught:
        _project(Layer(id="art", nodes=(group,)))

    assert caught.value.code == "GRAPH.LAYER_MISMATCH"
    assert caught.value.offending_id == "child"
    assert caught.value.path.endswith(".children[0].layer")


def test_project_rejects_same_node_instance_under_multiple_parents() -> None:
    shared = Shape(id="shared", layer="art", geometry=Circle(radius=1.0))
    left = Group(id="left", layer="art", children=(shared,))
    right = Group(id="right", layer="art", children=(shared,))

    with pytest.raises(SceneGraphValidationError) as caught:
        _project(Layer(id="art", nodes=(left, right)))

    assert caught.value.code == "GRAPH.MULTIPLE_PARENTS"
    assert caught.value.offending_id == "shared"
