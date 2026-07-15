"""Immutable territory geometry records."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from shapely.geometry.base import BaseGeometry

from .base import ValidityInterval


def normalize_identifier(value: str, *, kind: str) -> str:
    """Normalize case and reject identifiers unsafe for scoped references."""

    normalized = value.strip().casefold()
    if not normalized:
        raise ValueError(f"{kind} must not be empty")
    if ":" in normalized:
        raise ValueError(f"{kind} must not contain ':': {value!r}")
    return normalized


@dataclass(frozen=True, slots=True)
class TerritoryVersion:
    """One valid-time version of canonical territory geometry."""

    territory_id: str
    geometry: BaseGeometry
    validity: ValidityInterval = field(default_factory=ValidityInterval)
    aliases: tuple[str, ...] = ()
    properties: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        territory_id = normalize_identifier(self.territory_id, kind="territory id")
        if not isinstance(self.geometry, BaseGeometry):
            raise TypeError("territory geometry must be a Shapely geometry")
        if self.geometry.is_empty:
            raise ValueError(f"territory geometry must not be empty: {territory_id}")
        if not self.geometry.is_valid:
            raise ValueError(f"territory geometry must be valid: {territory_id}")

        normalized_aliases = {
            normalize_identifier(alias, kind="territory alias") for alias in self.aliases
        }
        aliases = tuple(sorted(normalized_aliases - {territory_id}))
        object.__setattr__(self, "territory_id", territory_id)
        object.__setattr__(self, "aliases", aliases)
        object.__setattr__(self, "properties", MappingProxyType(dict(self.properties)))


@dataclass(frozen=True, slots=True)
class ResolvedTerritory:
    """Dataset-scoped result returned by every geometry query path."""

    dataset_id: str
    version: TerritoryVersion

    @property
    def scoped_id(self) -> str:
        return f"{self.dataset_id}:{self.version.territory_id}"

    @property
    def territory_id(self) -> str:
        return self.version.territory_id

    @property
    def geometry(self) -> BaseGeometry:
        return self.version.geometry

    @property
    def validity(self) -> ValidityInterval:
        return self.version.validity

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        min_x, min_y, max_x, max_y = self.geometry.bounds
        return float(min_x), float(min_y), float(max_x), float(max_y)
