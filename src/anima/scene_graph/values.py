"""Immutable shared value objects for scene-graph authoring."""

from __future__ import annotations

from dataclasses import dataclass, field

from anima.scene_graph._validation import (
    require_finite_number,
    require_identifier,
    require_instance,
    require_positive_integer,
)
from anima.scene_graph.errors import SceneGraphValidationError


@dataclass(frozen=True, slots=True, kw_only=True)
class Resolution:
    """Output size in whole pixels."""

    width: int = 1920
    height: int = 1080

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "width",
            require_positive_integer(self.width, path="$.resolution.width"),
        )
        object.__setattr__(
            self,
            "height",
            require_positive_integer(self.height, path="$.resolution.height"),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class StylePackRef:
    """Pinned style-pack identity; resolution belongs to later subsystem."""

    id: str
    version: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "id",
            require_identifier(self.id, path="$.style_pack.id"),
        )
        object.__setattr__(
            self,
            "version",
            require_identifier(self.version, path="$.style_pack.version"),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class Vector2:
    """Finite two-dimensional vector in scene pixels."""

    x: float = 0.0
    y: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", require_finite_number(self.x, path="$.vector.x"))
        object.__setattr__(self, "y", require_finite_number(self.y, path="$.vector.y"))


@dataclass(frozen=True, slots=True, kw_only=True)
class Transform:
    """Local node transform; rotation uses degrees."""

    position: Vector2 = field(default_factory=Vector2)
    rotation: float = 0.0
    scale: Vector2 = field(default_factory=lambda: Vector2(x=1.0, y=1.0))
    anchor: Vector2 = field(default_factory=Vector2)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "position",
            require_instance(self.position, Vector2, path="$.transform.position"),
        )
        object.__setattr__(
            self,
            "rotation",
            require_finite_number(self.rotation, path="$.transform.rotation"),
        )
        object.__setattr__(
            self,
            "scale",
            require_instance(self.scale, Vector2, path="$.transform.scale"),
        )
        object.__setattr__(
            self,
            "anchor",
            require_instance(self.anchor, Vector2, path="$.transform.anchor"),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class VisibilityWindow:
    """Optional half-open visibility boundaries in seconds."""

    start: float | None = None
    end: float | None = None

    def __post_init__(self) -> None:
        start = (
            None
            if self.start is None
            else require_finite_number(self.start, path="$.visibility.start")
        )
        end = (
            None
            if self.end is None
            else require_finite_number(self.end, path="$.visibility.end")
        )
        if start is not None and start < 0.0:
            raise SceneGraphValidationError(
                code="VISIBILITY.NEGATIVE_BOUNDARY",
                path="$.visibility.start",
                message="visibility boundary cannot be negative",
            )
        if end is not None and end < 0.0:
            raise SceneGraphValidationError(
                code="VISIBILITY.NEGATIVE_BOUNDARY",
                path="$.visibility.end",
                message="visibility boundary cannot be negative",
            )
        if start is not None and end is not None and start > end:
            raise SceneGraphValidationError(
                code="VISIBILITY.REVERSED_INTERVAL",
                path="$.visibility",
                message="start cannot be greater than end",
            )
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
