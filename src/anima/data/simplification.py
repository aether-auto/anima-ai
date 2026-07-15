"""Topology-aware country collection simplification."""

from __future__ import annotations

import copy
import json
import math
from dataclasses import dataclass
from typing import Any, cast

from shapely import make_valid, unary_union
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry
from topojson import Topology


@dataclass(frozen=True, slots=True)
class TopologyParameters:
    """Explicit deterministic topology construction parameters."""

    quantization: int = 1_000_001
    tolerance: float = 0.0
    prevent_oversimplify: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.quantization, int) or isinstance(self.quantization, bool):
            raise ValueError("quantization must be an integer of at least 2")
        if self.quantization < 2:
            raise ValueError("quantization must be an integer of at least 2")
        if isinstance(self.tolerance, bool):
            raise ValueError("tolerance must be finite and non-negative")
        tolerance = float(self.tolerance)
        if not math.isfinite(tolerance) or tolerance < 0:
            raise ValueError("tolerance must be finite and non-negative")
        if not isinstance(self.prevent_oversimplify, bool):
            raise ValueError("prevent_oversimplify must be boolean")
        object.__setattr__(self, "tolerance", tolerance)

    def to_dict(self) -> dict[str, object]:
        return {
            "prevent_oversimplify": self.prevent_oversimplify,
            "quantization": self.quantization,
            "tolerance": self.tolerance,
        }


@dataclass(frozen=True, slots=True)
class SimplifiedTopology:
    """Canonical GeoJSON plus inspectable quantized shared-arc topology."""

    topology: dict[str, Any]
    feature_collection: dict[str, Any]
    parameters: TopologyParameters

    def _geometry(self, feature_id: str) -> dict[str, Any]:
        geometries = self.topology["objects"]["territories"]["geometries"]
        for geometry in geometries:
            if str(geometry.get("id")) == feature_id:
                return cast(dict[str, Any], geometry)
        raise KeyError(f"unknown topology feature id: {feature_id}")

    def arc_references(self, feature_id: str) -> tuple[int, ...]:
        """Return signed arc references used by one feature."""

        references: list[int] = []

        def collect(value: object) -> None:
            if isinstance(value, int):
                references.append(value)
            elif isinstance(value, list):
                for child in value:
                    collect(child)

        collect(self._geometry(feature_id)["arcs"])
        return tuple(references)

    def shared_arc_indices(self, first_id: str, second_id: str) -> tuple[int, ...]:
        """Return unsigned raw arc indexes shared by two features."""

        first = {
            reference if reference >= 0 else ~reference
            for reference in self.arc_references(first_id)
        }
        second = {
            reference if reference >= 0 else ~reference
            for reference in self.arc_references(second_id)
        }
        return tuple(sorted(first & second))

    def to_topology_json(self) -> str:
        payload = dict(self.topology)
        payload["parameters"] = self.parameters.to_dict()
        return json.dumps(
            payload, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
        ) + "\n"

    def to_geojson(self) -> str:
        return json.dumps(
            self.feature_collection,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n"


def _polygonal(geometry: BaseGeometry) -> BaseGeometry:
    """Return only the valid Polygon/MultiPolygon content of a geometry."""

    if geometry.geom_type in {"Polygon", "MultiPolygon"} and geometry.is_valid:
        return geometry
    if geometry.geom_type == "GeometryCollection":
        parts = [part for part in geometry.geoms if part.geom_type in {"Polygon", "MultiPolygon"}]
        if parts:
            return unary_union(parts)
    return geometry.buffer(0)


def _repair_polygonal(geometry: BaseGeometry) -> BaseGeometry:
    """Deterministically repair invalid rings, dropping collapsed parts."""

    return _polygonal(make_valid(geometry, method="structure", keep_collapsed=False))


def _canonical_features(collection: dict[str, Any]) -> list[dict[str, Any]]:
    if collection.get("type") != "FeatureCollection":
        raise ValueError("topology input must be a GeoJSON FeatureCollection")
    raw_features = collection.get("features")
    if not isinstance(raw_features, list) or not raw_features:
        raise ValueError("topology input must contain at least one feature")

    seen: set[str] = set()
    features: list[dict[str, Any]] = []
    for raw_feature in raw_features:
        if not isinstance(raw_feature, dict) or raw_feature.get("type") != "Feature":
            raise ValueError("topology input contains non-Feature value")
        feature = copy.deepcopy(raw_feature)
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            raise ValueError("topology feature properties must contain a mapping")
        raw_id = feature.get("id", properties.get("id"))
        if not isinstance(raw_id, str) or not raw_id.strip():
            raise ValueError("topology feature requires non-empty string id")
        feature_id = raw_id.strip().casefold()
        if feature_id in seen:
            raise ValueError(f"duplicate feature id: {feature_id}")
        seen.add(feature_id)
        feature["id"] = feature_id
        properties["id"] = feature_id

        geometry = feature.get("geometry")
        if not isinstance(geometry, dict) or geometry.get("type") not in {
            "Polygon",
            "MultiPolygon",
        }:
            raise ValueError("country topology features must use Polygon or MultiPolygon")
        shaped = shape(geometry)
        if shaped.is_empty or not shaped.is_valid:
            raise ValueError(f"feature geometry must be non-empty and valid: {feature_id}")
        features.append(feature)
    return sorted(features, key=lambda item: str(item["id"]))


def simplify_feature_collection(
    collection: dict[str, Any],
    *,
    parameters: TopologyParameters | None = None,
) -> SimplifiedTopology:
    """Build shared arcs, quantize, simplify once per arc, and return GeoJSON."""

    selected = parameters or TopologyParameters()
    canonical_collection: dict[str, Any] = {
        "type": "FeatureCollection",
        "features": _canonical_features(collection),
    }
    topology = Topology(
        canonical_collection,
        topology=True,
        prequantize=selected.quantization,
        topoquantize=False,
        presimplify=False,
        toposimplify=selected.tolerance if selected.tolerance > 0 else False,
        shared_coords=False,
        prevent_oversimplify=selected.prevent_oversimplify,
        simplify_with="shapely",
        simplify_algorithm="dp",
        winding_order="CW_CCW",
        object_name="territories",
        ignore_index=False,
    )

    raw_topology = copy.deepcopy(topology.output)
    raw_topology.pop("options", None)
    raw_topology.pop("coordinates", None)
    canonical_topology: dict[str, Any] = json.loads(
        json.dumps(raw_topology, ensure_ascii=False, allow_nan=False, sort_keys=True)
    )

    exported: dict[str, Any] = json.loads(
        topology.to_geojson(
            object_name="territories",
            validate=False,
            winding_order="CCW_CW",
            decimals=12,
        )
    )
    exported["features"] = sorted(exported["features"], key=lambda item: str(item["id"]))
    for feature in exported["features"]:
        shaped = shape(feature["geometry"])
        if not shaped.is_valid:
            # Quantization can pinch rings into bowtie self-intersections; repair
            # deterministically and keep only the polygonal components.
            shaped = _repair_polygonal(shaped)
            feature["geometry"] = json.loads(
                json.dumps(mapping(shaped), ensure_ascii=False, allow_nan=False)
            )
        if shaped.is_empty or not shaped.is_valid:
            raise ValueError(f"simplification produced invalid geometry: {feature['id']}")

    return SimplifiedTopology(canonical_topology, exported, selected)


__all__ = [
    "SimplifiedTopology",
    "TopologyParameters",
    "simplify_feature_collection",
]
