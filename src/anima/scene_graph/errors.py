"""Structured public errors for scene-graph construction and decoding."""

from __future__ import annotations


class SceneGraphError(ValueError):
    """Base error carrying stable machine-readable context."""

    __slots__ = ("code", "message", "offending_id", "path")

    def __init__(
        self,
        *,
        code: str,
        path: str,
        message: str,
        offending_id: str | None = None,
    ) -> None:
        self.code = code
        self.path = path
        self.message = message
        self.offending_id = offending_id
        super().__init__(str(self))

    def __str__(self) -> str:
        identifier = "" if self.offending_id is None else f" id={self.offending_id!r}"
        return f"{self.code} at {self.path}{identifier}: {self.message}"


class SceneGraphValidationError(SceneGraphError):
    """Raised when immutable model construction violates scene-graph invariants."""


class SceneGraphDecodeError(SceneGraphError):
    """Raised when serialized input violates schema or JSON contract."""
