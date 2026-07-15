"""Territory index facade backed by shared geometry resolver."""

from __future__ import annotations

from anima.geometry import GeometryResolver


class TerritoryIndex(GeometryResolver):
    """Semantic map-data name for :class:`~anima.geometry.GeometryResolver`."""


__all__ = ["TerritoryIndex"]
