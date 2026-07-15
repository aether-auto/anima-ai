from __future__ import annotations

from types import MappingProxyType

import pytest
from anima.scene_graph import (
    Circle,
    Group,
    Layer,
    Project,
    Scene,
    Shape,
    StylePackRef,
)


def _shape(node_id: str, layer: str, z: int) -> Shape:
    return Shape(id=node_id, layer=layer, z=z, geometry=Circle(radius=1.0))


def test_layer_render_order_sorts_by_z_with_stable_declared_ties() -> None:
    declared = (
        _shape("middle-first", "art", 0),
        _shape("back", "art", -1),
        _shape("middle-second", "art", 0),
        _shape("front", "art", 2),
    )
    layer = Layer(id="art", nodes=declared)

    assert layer.nodes == declared
    assert tuple(node.id for node in layer.render_order) == (
        "back",
        "middle-first",
        "middle-second",
        "front",
    )


def test_group_is_parent_order_item_and_sorts_children_recursively() -> None:
    group = Group(
        id="group",
        layer="art",
        z=0,
        children=(
            _shape("group-front", "art", 10),
            _shape("group-back-first", "art", -2),
            _shape("group-back-second", "art", -2),
        ),
    )
    sibling = _shape("sibling", "art", 1)
    layer = Layer(id="art", nodes=(sibling, group))

    assert tuple(node.id for node in layer.render_order) == ("group", "sibling")
    assert tuple(node.id for node in group.render_order) == (
        "group-back-first",
        "group-back-second",
        "group-front",
    )


def test_project_preorder_is_declared_order_across_scenes_layers_and_groups() -> None:
    nested = _shape("nested", "labels", 0)
    group = Group(id="group", layer="labels", children=(nested,))
    first = _shape("first", "art", 20)
    second = _shape("second", "art", -20)
    project = Project(
        style_pack=StylePackRef(id="flat", version="1.0.0"),
        scenes=(
            Scene(
                id="intro",
                layers=(
                    Layer(id="art", nodes=(first, second)),
                    Layer(id="labels", nodes=(group,)),
                ),
            ),
            Scene(id="outro", layers=(Layer(id="empty"),)),
        ),
    )

    expected = ("first", "second", "group", "nested")
    assert tuple(node.id for node in project.preorder) == expected
    assert tuple(node.id for node in project.iter_nodes()) == expected
    assert tuple(node.id for node in project.walk_nodes()) == expected


def test_node_lookup_is_read_only_and_reuses_preorder_instances() -> None:
    node = _shape("only", "art", 0)
    project = Project(
        style_pack=StylePackRef(id="flat", version="1.0.0"),
        scenes=(Scene(id="scene", layers=(Layer(id="art", nodes=(node,)),)),),
    )

    assert isinstance(project.node_lookup, MappingProxyType)
    assert project.node_lookup["only"] is node
    assert project.nodes_by_id is project.node_lookup
    assert project.get_node("only") is node
    assert project.get_node("missing") is None

    with pytest.raises(TypeError):
        project.node_lookup["new"] = node  # type: ignore[index]
