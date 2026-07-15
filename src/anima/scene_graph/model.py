"""Project hierarchy, graph invariants, traversal, and render-order views."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from anima._version import ENGINE_VERSION
from anima.scene_graph._validation import (
    normalize_models,
    require_identifier,
    require_instance,
    require_integer,
    require_positive_number,
)
from anima.scene_graph.errors import SceneGraphValidationError
from anima.scene_graph.nodes import Group, Node, _normalize_nodes, _render_order
from anima.scene_graph.values import Resolution, StylePackRef


@dataclass(frozen=True, slots=True, kw_only=True)
class Layer:
    """Declared layer and its root nodes."""

    id: str
    nodes: tuple[Node, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", require_identifier(self.id, path="$.layer.id"))
        object.__setattr__(
            self,
            "nodes",
            _normalize_nodes(self.nodes, path="$.layer.nodes"),
        )

    @property
    def render_order(self) -> tuple[Node, ...]:
        """Root nodes sorted by z with stable equal-z ties."""
        return _render_order(self.nodes)


@dataclass(frozen=True, slots=True, kw_only=True)
class Scene:
    """Ordered collection of independently named layers."""

    id: str
    layers: tuple[Layer, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", require_identifier(self.id, path="$.scene.id"))
        object.__setattr__(
            self,
            "layers",
            normalize_models(self.layers, Layer, path="$.scene.layers"),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class Project:
    """Validated immutable scene graph and pinned authoring settings."""

    style_pack: StylePackRef
    resolution: Resolution = field(default_factory=Resolution)
    fps: float = 30.0
    seed: int = 0
    wpm: float = 150.0
    engine_version: str = ENGINE_VERSION
    scenes: tuple[Scene, ...] = ()
    _preorder: tuple[Node, ...] = field(init=False, repr=False, compare=False)
    _node_lookup: Mapping[str, Node] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "style_pack",
            require_instance(self.style_pack, StylePackRef, path="$.project.style_pack"),
        )
        object.__setattr__(
            self,
            "resolution",
            require_instance(self.resolution, Resolution, path="$.project.resolution"),
        )
        object.__setattr__(
            self,
            "fps",
            require_positive_number(self.fps, path="$.project.fps"),
        )
        object.__setattr__(self, "seed", require_integer(self.seed, path="$.project.seed"))
        object.__setattr__(
            self,
            "wpm",
            require_positive_number(self.wpm, path="$.project.wpm"),
        )
        object.__setattr__(
            self,
            "engine_version",
            require_identifier(self.engine_version, path="$.project.engine_version"),
        )
        scenes = normalize_models(self.scenes, Scene, path="$.project.scenes")
        object.__setattr__(self, "scenes", scenes)

        preorder, lookup = self._validate_hierarchy(scenes)
        object.__setattr__(self, "_preorder", preorder)
        object.__setattr__(self, "_node_lookup", MappingProxyType(lookup))

    @staticmethod
    def _validate_hierarchy(scenes: tuple[Scene, ...]) -> tuple[tuple[Node, ...], dict[str, Node]]:
        scene_ids: set[str] = set()
        node_paths_by_instance: dict[int, str] = {}
        node_paths_by_id: dict[str, str] = {}
        preorder: list[Node] = []
        lookup: dict[str, Node] = {}

        def visit(node: Node, *, layer_id: str, path: str) -> None:
            instance_key = id(node)
            if instance_key in node_paths_by_instance:
                raise SceneGraphValidationError(
                    code="GRAPH.MULTIPLE_PARENTS",
                    path=path,
                    message=(
                        "node instance already owned at "
                        f"{node_paths_by_instance[instance_key]}"
                    ),
                    offending_id=node.id,
                )
            node_paths_by_instance[instance_key] = path

            if node.layer != layer_id:
                raise SceneGraphValidationError(
                    code="GRAPH.LAYER_MISMATCH",
                    path=f"{path}.layer",
                    message=f"declared layer {node.layer!r} does not match {layer_id!r}",
                    offending_id=node.id,
                )
            if node.id in node_paths_by_id:
                raise SceneGraphValidationError(
                    code="GRAPH.DUPLICATE_NODE_ID",
                    path=f"{path}.id",
                    message=f"node ID already declared at {node_paths_by_id[node.id]}",
                    offending_id=node.id,
                )
            node_paths_by_id[node.id] = path
            preorder.append(node)
            lookup[node.id] = node

            if isinstance(node, Group):
                for child_index, child in enumerate(node.children):
                    visit(
                        child,
                        layer_id=layer_id,
                        path=f"{path}.children[{child_index}]",
                    )

        for scene_index, scene in enumerate(scenes):
            scene_path = f"$.project.scenes[{scene_index}]"
            if scene.id in scene_ids:
                raise SceneGraphValidationError(
                    code="GRAPH.DUPLICATE_SCENE_ID",
                    path=f"{scene_path}.id",
                    message="scene ID must be project-unique",
                    offending_id=scene.id,
                )
            scene_ids.add(scene.id)

            layer_ids: set[str] = set()
            for layer_index, layer in enumerate(scene.layers):
                layer_path = f"{scene_path}.layers[{layer_index}]"
                if layer.id in layer_ids:
                    raise SceneGraphValidationError(
                        code="GRAPH.DUPLICATE_LAYER_ID",
                        path=f"{layer_path}.id",
                        message="layer ID must be scene-local unique",
                        offending_id=layer.id,
                    )
                layer_ids.add(layer.id)
                for node_index, node in enumerate(layer.nodes):
                    visit(
                        node,
                        layer_id=layer.id,
                        path=f"{layer_path}.nodes[{node_index}]",
                    )

        return tuple(preorder), lookup

    @property
    def preorder(self) -> tuple[Node, ...]:
        """Declared scene/layer/root/child preorder."""
        return self._preorder

    @property
    def node_lookup(self) -> Mapping[str, Node]:
        """Read-only project-wide stable-ID lookup."""
        return self._node_lookup

    @property
    def nodes_by_id(self) -> Mapping[str, Node]:
        """Alias documenting lookup key semantics."""
        return self._node_lookup

    def get_node(self, node_id: str) -> Node | None:
        return self._node_lookup.get(node_id)

    def iter_nodes(self) -> Iterator[Node]:
        return iter(self._preorder)

    def walk_nodes(self) -> Iterator[Node]:
        return iter(self._preorder)
