"""Typed immutable Phase 1 node and payload definitions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import ClassVar, Literal, NoReturn, TypeAlias, final

from anima.scene_graph._validation import (
    normalize_models,
    require_identifier,
    require_instance,
    require_integer,
    require_positive_number,
    require_string,
)
from anima.scene_graph.errors import SceneGraphValidationError
from anima.scene_graph.values import Transform, Vector2, VisibilityWindow

GeometryType: TypeAlias = Literal["rectangle", "circle", "ellipse", "polygon"]
NodeType: TypeAlias = Literal["shape", "path", "text", "group"]
PathCommandType: TypeAlias = Literal["move_to", "line_to", "cubic_to", "close_path"]


@dataclass(frozen=True, slots=True, kw_only=True)
class Geometry(ABC):
    """Closed Phase 1 geometry payload base."""

    @property
    @abstractmethod
    def geometry_type(self) -> GeometryType:
        """Return stable codec discriminator."""


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class Rectangle(Geometry):
    width: float
    height: float

    @property
    def geometry_type(self) -> Literal["rectangle"]:
        return "rectangle"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "width",
            require_positive_number(self.width, path="$.rectangle.width"),
        )
        object.__setattr__(
            self,
            "height",
            require_positive_number(self.height, path="$.rectangle.height"),
        )


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class Circle(Geometry):
    radius: float

    @property
    def geometry_type(self) -> Literal["circle"]:
        return "circle"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "radius",
            require_positive_number(self.radius, path="$.circle.radius"),
        )


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class Ellipse(Geometry):
    radius_x: float
    radius_y: float

    @property
    def geometry_type(self) -> Literal["ellipse"]:
        return "ellipse"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "radius_x",
            require_positive_number(self.radius_x, path="$.ellipse.radius_x"),
        )
        object.__setattr__(
            self,
            "radius_y",
            require_positive_number(self.radius_y, path="$.ellipse.radius_y"),
        )


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class Polygon(Geometry):
    points: tuple[Vector2, ...]

    @property
    def geometry_type(self) -> Literal["polygon"]:
        return "polygon"

    def __post_init__(self) -> None:
        points = normalize_models(self.points, Vector2, path="$.polygon.points")
        if len(points) < 3:
            raise SceneGraphValidationError(
                code="GEOMETRY.POLYGON_TOO_FEW_POINTS",
                path="$.polygon.points",
                message="polygon requires at least three points",
            )
        object.__setattr__(self, "points", points)


ShapeGeometry: TypeAlias = Rectangle | Circle | Ellipse | Polygon


@dataclass(frozen=True, slots=True, kw_only=True)
class PathCommand(ABC):
    """Closed Phase 1 path command base."""

    @property
    @abstractmethod
    def command_type(self) -> PathCommandType:
        """Return stable codec discriminator."""


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class MoveTo(PathCommand):
    point: Vector2

    @property
    def command_type(self) -> Literal["move_to"]:
        return "move_to"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "point",
            require_instance(self.point, Vector2, path="$.move_to.point"),
        )


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class LineTo(PathCommand):
    point: Vector2

    @property
    def command_type(self) -> Literal["line_to"]:
        return "line_to"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "point",
            require_instance(self.point, Vector2, path="$.line_to.point"),
        )


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class CubicTo(PathCommand):
    control1: Vector2
    control2: Vector2
    point: Vector2

    @property
    def command_type(self) -> Literal["cubic_to"]:
        return "cubic_to"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "control1",
            require_instance(self.control1, Vector2, path="$.cubic_to.control1"),
        )
        object.__setattr__(
            self,
            "control2",
            require_instance(self.control2, Vector2, path="$.cubic_to.control2"),
        )
        object.__setattr__(
            self,
            "point",
            require_instance(self.point, Vector2, path="$.cubic_to.point"),
        )


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class ClosePath(PathCommand):
    @property
    def command_type(self) -> Literal["close_path"]:
        return "close_path"


PathCommandPayload: TypeAlias = MoveTo | LineTo | CubicTo | ClosePath


@dataclass(frozen=True, slots=True, kw_only=True)
class Node(ABC):
    """Stable identity and shared placement carried by every render node."""

    id: str
    layer: str
    transform: Transform = field(default_factory=Transform)
    style_role: str | None = None
    z: int = 0
    visibility: VisibilityWindow = field(default_factory=VisibilityWindow)

    NODE_TYPE: ClassVar[NodeType]

    @property
    @abstractmethod
    def node_type(self) -> NodeType:
        """Return stable codec discriminator."""

    def __post_init__(self) -> None:
        node_id = require_identifier(self.id, path="$.node.id")
        object.__setattr__(self, "id", node_id)
        try:
            object.__setattr__(
                self,
                "layer",
                require_identifier(self.layer, path="$.node.layer"),
            )
            object.__setattr__(
                self,
                "transform",
                require_instance(self.transform, Transform, path="$.node.transform"),
            )
            if self.style_role is not None:
                object.__setattr__(
                    self,
                    "style_role",
                    require_identifier(self.style_role, path="$.node.style_role"),
                )
            object.__setattr__(self, "z", require_integer(self.z, path="$.node.z"))
            object.__setattr__(
                self,
                "visibility",
                require_instance(self.visibility, VisibilityWindow, path="$.node.visibility"),
            )
        except SceneGraphValidationError as error:
            _raise_with_node_id(error, node_id=node_id)


def _raise_with_node_id(error: SceneGraphValidationError, *, node_id: str) -> NoReturn:
    raise SceneGraphValidationError(
        code=error.code,
        path=error.path,
        message=error.message,
        offending_id=node_id,
    ) from error


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class Shape(Node):
    geometry: ShapeGeometry

    NODE_TYPE: ClassVar[Literal["shape"]] = "shape"

    @property
    def node_type(self) -> Literal["shape"]:
        return self.NODE_TYPE

    def __post_init__(self) -> None:
        Node.__post_init__(self)
        if type(self.geometry) not in (Rectangle, Circle, Ellipse, Polygon):
            raise SceneGraphValidationError(
                code="NODE.INVALID_GEOMETRY",
                path="$.shape.geometry",
                message="expected Phase 1 geometry payload",
                offending_id=self.id,
            )


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class Path(Node):
    commands: tuple[PathCommandPayload, ...]

    NODE_TYPE: ClassVar[Literal["path"]] = "path"

    @property
    def node_type(self) -> Literal["path"]:
        return self.NODE_TYPE

    def __post_init__(self) -> None:
        Node.__post_init__(self)
        try:
            raw_commands = tuple(self.commands)
        except TypeError as error:
            raise SceneGraphValidationError(
                code="VALUE.INVALID_COLLECTION",
                path="$.path.commands",
                message="expected ordered collection",
                offending_id=self.id,
            ) from error
        normalized_commands: list[PathCommandPayload] = []
        for index, command in enumerate(raw_commands):
            if (
                not isinstance(command, MoveTo | LineTo | CubicTo | ClosePath)
                or type(command) not in (MoveTo, LineTo, CubicTo, ClosePath)
            ):
                raise SceneGraphValidationError(
                    code="VALUE.INVALID_MODEL",
                    path=f"$.path.commands[{index}]",
                    message="expected PathCommand",
                    offending_id=self.id,
                )
            normalized_commands.append(command)
        commands = tuple(normalized_commands)
        if not commands:
            raise SceneGraphValidationError(
                code="PATH.EMPTY",
                path="$.path.commands",
                message="path requires at least one command",
                offending_id=self.id,
            )
        if not isinstance(commands[0], MoveTo):
            raise SceneGraphValidationError(
                code="PATH.INITIAL_MOVE_REQUIRED",
                path="$.path.commands[0]",
                message="first path command must be move_to",
                offending_id=self.id,
            )

        segment_count = 0
        closed = False
        for index, command in enumerate(commands[1:], start=1):
            if isinstance(command, MoveTo):
                segment_count = 0
                closed = False
            elif isinstance(command, ClosePath):
                if closed or segment_count == 0:
                    raise SceneGraphValidationError(
                        code="PATH.INVALID_CLOSE",
                        path=f"$.path.commands[{index}]",
                        message="close_path requires open subpath containing a segment",
                        offending_id=self.id,
                    )
                closed = True
            else:
                if closed:
                    raise SceneGraphValidationError(
                        code="PATH.MOVE_REQUIRED_AFTER_CLOSE",
                        path=f"$.path.commands[{index}]",
                        message="move_to required after close_path",
                        offending_id=self.id,
                    )
                segment_count += 1

        object.__setattr__(self, "commands", commands)


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class Text(Node):
    content: str
    font_role: str
    size: float

    NODE_TYPE: ClassVar[Literal["text"]] = "text"

    @property
    def node_type(self) -> Literal["text"]:
        return self.NODE_TYPE

    def __post_init__(self) -> None:
        Node.__post_init__(self)
        try:
            object.__setattr__(
                self,
                "content",
                require_string(self.content, path="$.text.content"),
            )
            object.__setattr__(
                self,
                "font_role",
                require_identifier(self.font_role, path="$.text.font_role"),
            )
            object.__setattr__(
                self,
                "size",
                require_positive_number(self.size, path="$.text.size"),
            )
        except SceneGraphValidationError as error:
            _raise_with_node_id(error, node_id=self.id)


def _render_order(nodes: tuple[Node, ...]) -> tuple[Node, ...]:
    return tuple(
        node
        for _index, node in sorted(
            enumerate(nodes),
            key=lambda indexed: (indexed[1].z, indexed[0]),
        )
    )


@final
@dataclass(frozen=True, slots=True, kw_only=True)
class Group(Node):
    children: tuple[Node, ...] = ()

    NODE_TYPE: ClassVar[Literal["group"]] = "group"

    @property
    def node_type(self) -> Literal["group"]:
        return self.NODE_TYPE

    def __post_init__(self) -> None:
        Node.__post_init__(self)
        object.__setattr__(
            self,
            "children",
            _normalize_nodes(self.children, path="$.group.children"),
        )

    @property
    def render_order(self) -> tuple[Node, ...]:
        """Children sorted by local z and stable declared sequence."""
        return _render_order(self.children)


def _normalize_nodes(values: Iterable[object], *, path: str) -> tuple[Node, ...]:
    if isinstance(values, str | bytes | bytearray):
        raise SceneGraphValidationError(
            code="VALUE.INVALID_COLLECTION",
            path=path,
            message="expected ordered collection",
        )
    try:
        copied = tuple(values)
    except TypeError as error:
        raise SceneGraphValidationError(
            code="VALUE.INVALID_COLLECTION",
            path=path,
            message="expected ordered collection",
        ) from error
    normalized: list[Node] = []
    for index, node in enumerate(copied):
        if not isinstance(node, Node):
            raise SceneGraphValidationError(
                code="VALUE.INVALID_MODEL",
                path=f"{path}[{index}]",
                message="expected Node",
            )
        if type(node) not in (Shape, Path, Text, Group):
            raise SceneGraphValidationError(
                code="NODE.UNSUPPORTED_TYPE",
                path=f"{path}[{index}]",
                message=f"unsupported Phase 1 node class {type(node).__name__}",
                offending_id=node.id,
            )
        normalized.append(node)
    return tuple(normalized)
