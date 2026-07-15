"""Pinned, serializable map projections with offline PROJ behavior."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from typing import Any

from pyproj import Transformer, network
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform

os.environ["PROJ_NETWORK"] = "OFF"
network.set_network_enabled(active=False)


def _finite_origin(longitude: float, latitude: float) -> tuple[float, float]:
    lon = float(longitude)
    lat = float(latitude)
    if not math.isfinite(lon) or not math.isfinite(lat):
        raise ValueError("projection origin coordinates must be finite")
    if lon < -180 or lon > 180:
        raise ValueError(f"projection origin longitude outside -180..180: {lon}")
    if lat < -90 or lat > 90:
        raise ValueError(f"projection origin latitude outside -90..90: {lat}")
    return (0.0 if lon == 0 else lon, 0.0 if lat == 0 else lat)


def _number(value: float) -> str:
    return format(value, ".15g")


def _laea_crs(origin: tuple[float, float]) -> str:
    longitude, latitude = origin
    return (
        f"+proj=laea +lat_0={_number(latitude)} +lon_0={_number(longitude)} "
        "+datum=WGS84 +units=m +no_defs +type=crs"
    )


@dataclass(frozen=True, slots=True)
class ProjectionDefinition:
    """Canonical serializable projection contract."""

    method: str
    target_crs: str
    origin: tuple[float, float] | None
    source_crs: str = "EPSG:4326"
    always_xy: bool = True

    def __post_init__(self) -> None:
        if self.source_crs != "EPSG:4326":
            raise ValueError("source_crs must be EPSG:4326")
        if not self.always_xy:
            raise ValueError("always_xy must be true")
        if self.method == "equal-earth":
            if self.target_crs != "EPSG:8857" or self.origin is not None:
                raise ValueError("equal-earth requires target EPSG:8857 and null origin")
            return
        if self.method == "lambert-azimuthal-equal-area":
            if self.origin is None:
                raise ValueError("regional projection requires caller-specified origin")
            normalized_origin = _finite_origin(*self.origin)
            if self.target_crs != _laea_crs(normalized_origin):
                raise ValueError("regional target_crs does not match canonical origin")
            object.__setattr__(self, "origin", normalized_origin)
            return
        raise ValueError(f"unsupported projection method: {self.method!r}")

    def to_dict(self) -> dict[str, object]:
        return {
            "always_xy": self.always_xy,
            "method": self.method,
            "origin": self.origin,
            "source_crs": self.source_crs,
            "target_crs": self.target_crs,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(), ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")
        ) + "\n"

    @classmethod
    def from_json(cls, serialized: str) -> ProjectionDefinition:
        raw: Any = json.loads(serialized)
        if not isinstance(raw, dict):
            raise ValueError("projection definition must contain a mapping")
        expected = {"always_xy", "method", "origin", "source_crs", "target_crs"}
        if set(raw) != expected:
            raise ValueError(
                f"projection definition fields must be {sorted(expected)!r}; got {sorted(raw)!r}"
            )
        raw_origin = raw["origin"]
        origin: tuple[float, float] | None
        if raw_origin is None:
            origin = None
        elif isinstance(raw_origin, list) and len(raw_origin) == 2:
            origin = (float(raw_origin[0]), float(raw_origin[1]))
        else:
            raise ValueError("projection origin must be null or [longitude, latitude]")
        return cls(
            method=str(raw["method"]),
            target_crs=str(raw["target_crs"]),
            origin=origin,
            source_crs=str(raw["source_crs"]),
            always_xy=bool(raw["always_xy"]),
        )


def world_equal_earth() -> ProjectionDefinition:
    """Return EPSG:8857 Equal Earth world default."""

    return ProjectionDefinition(method="equal-earth", target_crs="EPSG:8857", origin=None)


def regional_equal_area(longitude: float, latitude: float) -> ProjectionDefinition:
    """Return caller-centered WGS84 Lambert azimuthal equal-area default."""

    origin = _finite_origin(longitude, latitude)
    return ProjectionDefinition(
        method="lambert-azimuthal-equal-area",
        target_crs=_laea_crs(origin),
        origin=origin,
    )


class Projection:
    """Forward/inverse coordinate and Shapely-geometry transformer."""

    __slots__ = ("definition", "_forward", "_inverse")

    def __init__(self, definition: ProjectionDefinition) -> None:
        self.definition = definition
        self._forward = Transformer.from_crs(
            definition.source_crs,
            definition.target_crs,
            always_xy=definition.always_xy,
        )
        self._inverse = Transformer.from_crs(
            definition.target_crs,
            definition.source_crs,
            always_xy=definition.always_xy,
        )

    @classmethod
    def world(cls) -> Projection:
        return cls(world_equal_earth())

    @classmethod
    def regional(cls, longitude: float, latitude: float) -> Projection:
        return cls(regional_equal_area(longitude, latitude))

    def forward_point(self, x: float, y: float) -> tuple[float, float]:
        projected_x, projected_y = self._forward.transform(float(x), float(y))
        return float(projected_x), float(projected_y)

    def inverse_point(self, x: float, y: float) -> tuple[float, float]:
        longitude, latitude = self._inverse.transform(float(x), float(y))
        return float(longitude), float(latitude)

    def forward(self, geometry: BaseGeometry) -> BaseGeometry:
        if not isinstance(geometry, BaseGeometry):
            raise TypeError("forward projection requires Shapely geometry")
        return transform(self._forward.transform, geometry)

    def inverse(self, geometry: BaseGeometry) -> BaseGeometry:
        if not isinstance(geometry, BaseGeometry):
            raise TypeError("inverse projection requires Shapely geometry")
        return transform(self._inverse.transform, geometry)


__all__ = [
    "Projection",
    "ProjectionDefinition",
    "regional_equal_area",
    "world_equal_earth",
]
