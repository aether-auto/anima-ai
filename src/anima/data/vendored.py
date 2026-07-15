"""Immutable offline resource catalog and deterministic GeoJSON loading."""

from __future__ import annotations

import copy
import json
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
from importlib.resources import files
from pathlib import PurePosixPath
from typing import Any

from shapely.geometry import shape

from anima.maps import MapDataset, TerritoryVersion, ValidityInterval, coerce_date

_SHA256 = re.compile(r"[0-9a-f]{64}")


def _relative_path(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} requires non-empty relative resource path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or str(path) != value:
        raise ValueError(f"{field} requires normalized relative resource path: {value!r}")
    return value


@dataclass(frozen=True, slots=True)
class ResourceSpec:
    """One immutable package resource."""

    path: str
    sha256: str
    size: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", _relative_path(self.path, field="resource path"))
        if not _SHA256.fullmatch(self.sha256):
            raise ValueError(f"resource checksum must be lowercase SHA-256: {self.sha256!r}")
        if not isinstance(self.size, int) or isinstance(self.size, bool) or self.size <= 0:
            raise ValueError("resource size must be a positive integer")


@dataclass(frozen=True, slots=True)
class DatasetSpec:
    """Version-pinned data source and its shipped resources."""

    dataset_id: str
    source_name: str
    source_version: str
    package: str
    license_path: str
    attribution_path: str
    resources: tuple[ResourceSpec, ...]

    def __post_init__(self) -> None:
        dataset_id = self.dataset_id.strip().casefold()
        if not dataset_id or ":" in dataset_id:
            raise ValueError(f"invalid dataset id: {self.dataset_id!r}")
        if not self.source_name.strip() or not self.source_version.strip():
            raise ValueError(f"dataset source name/version must be pinned: {dataset_id}")
        if not (
            self.package.startswith("anima.data.")
            or self.package.startswith("anima_ai_data.")
        ):
            raise ValueError(
                "dataset package must live under anima.data or anima_ai_data: "
                f"{self.package!r}"
            )
        if not self.resources:
            raise ValueError(f"dataset must declare resources: {dataset_id}")
        object.__setattr__(self, "dataset_id", dataset_id)
        object.__setattr__(self, "license_path", _relative_path(self.license_path, field="license"))
        object.__setattr__(
            self,
            "attribution_path",
            _relative_path(self.attribution_path, field="attribution"),
        )


def parse_catalog(raw: object) -> tuple[DatasetSpec, ...]:
    """Validate catalog mapping and return deterministic immutable specs."""

    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("vendored data catalog requires schema_version 1")
    raw_datasets = raw.get("datasets")
    if not isinstance(raw_datasets, list):
        raise ValueError("vendored data catalog requires datasets list")

    seen: set[str] = set()
    datasets: list[DatasetSpec] = []
    for value in raw_datasets:
        if not isinstance(value, dict):
            raise ValueError("vendored dataset entry must contain a mapping")
        raw_resources = value.get("resources")
        if not isinstance(raw_resources, list):
            raise ValueError("vendored dataset resources must contain a list")
        resources = tuple(
            ResourceSpec(
                path=str(resource["path"]),
                sha256=str(resource["sha256"]),
                size=resource["size"],
            )
            for resource in raw_resources
            if isinstance(resource, dict)
        )
        if len(resources) != len(raw_resources):
            raise ValueError("vendored resource entry must contain a mapping")
        dataset = DatasetSpec(
            dataset_id=str(value["dataset_id"]),
            source_name=str(value["source_name"]),
            source_version=str(value["source_version"]),
            package=str(value["package"]),
            license_path=str(value["license_path"]),
            attribution_path=str(value["attribution_path"]),
            resources=resources,
        )
        if dataset.dataset_id in seen:
            raise ValueError(f"duplicate vendored dataset id: {dataset.dataset_id}")
        seen.add(dataset.dataset_id)
        datasets.append(dataset)
    return tuple(sorted(datasets, key=lambda item: item.dataset_id))


@lru_cache(maxsize=1)
def _catalog() -> tuple[DatasetSpec, ...]:
    payload = files("anima.data").joinpath("catalog.json").read_bytes()
    return parse_catalog(json.loads(payload))


def available_datasets() -> tuple[str, ...]:
    return tuple(spec.dataset_id for spec in _catalog())


def dataset_spec(dataset_id: str) -> DatasetSpec:
    normalized = dataset_id.strip().casefold()
    for spec in _catalog():
        if spec.dataset_id == normalized:
            return spec
    available = ", ".join(available_datasets()) or "<none>"
    raise KeyError(f"unknown vendored dataset {normalized!r}; available: {available}")


def read_resource(package: str, path: str) -> bytes:
    """Read package resource without materializing or accessing network."""

    normalized = _relative_path(path, field="resource")
    resource = files(package)
    for part in PurePosixPath(normalized).parts:
        resource = resource.joinpath(part)
    return resource.read_bytes()


def canonical_geojson_bytes(collection: Mapping[str, object]) -> bytes:
    """Encode deterministic UTF-8 GeoJSON with one trailing newline."""

    return (
        json.dumps(
            collection,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def normalize_feature_collection(
    collection: dict[str, Any],
    *,
    quantization: int = 1_000_001,
) -> dict[str, Any]:
    """Normalize IDs and coordinates through shared-arc topojson quantization."""

    from .simplification import TopologyParameters, simplify_feature_collection

    working = copy.deepcopy(collection)
    features = working.get("features")
    if not isinstance(features, list):
        raise ValueError("normalization input requires features list")
    for feature in features:
        if not isinstance(feature, dict):
            raise ValueError("normalization feature must contain a mapping")
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            raise ValueError("normalization feature properties must contain a mapping")
        raw_id = feature.get("id", properties.get("territory_id", properties.get("id")))
        if not isinstance(raw_id, str) or not raw_id.strip():
            raise ValueError("normalization feature requires canonical id")
        canonical_id = raw_id.strip().casefold()
        feature["id"] = canonical_id
        properties["id"] = canonical_id
        properties["territory_id"] = canonical_id

    result = simplify_feature_collection(
        working,
        parameters=TopologyParameters(quantization=quantization),
    ).feature_collection
    result["features"] = sorted(
        result["features"],
        key=lambda feature: (
            str(feature["id"]),
            str(feature.get("properties", {}).get("valid_from") or ""),
        ),
    )
    return result


def _territory_slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    slug: list[str] = []
    for character in normalized:
        if character.isalnum():
            slug.append(character)
        elif slug and slug[-1] != "-":
            slug.append("-")
    identifier = "".join(slug).strip("-")
    if not identifier:
        raise ValueError(f"territory name has no identifier characters: {value!r}")
    return identifier


def normalize_natural_earth(
    collection: dict[str, Any],
    *,
    quantization: int = 1_000_001,
) -> dict[str, Any]:
    """Normalize Natural Earth Admin 0 features to stable canonical IDs."""

    working = copy.deepcopy(collection)
    features = working.get("features")
    if not isinstance(features, list):
        raise ValueError("Natural Earth input requires features list")
    for feature in features:
        if not isinstance(feature, dict):
            raise ValueError("Natural Earth feature must contain a mapping")
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            raise ValueError("Natural Earth feature properties must contain a mapping")
        canonical_codes = tuple(
            str(properties[key]).strip().casefold()
            for key in ("ADM0_A3", "ISO_A3", "SOV_A3")
            if properties.get(key) not in (None, "", -99, "-99")
        )
        three_letter = next((code for code in canonical_codes if len(code) == 3), None)
        if three_letter is None:
            natural_earth_id = properties.get("NE_ID")
            if natural_earth_id in (None, ""):
                raise ValueError("Natural Earth feature lacks stable ADM0_A3/ISO_A3/NE_ID")
            three_letter = f"ne-{natural_earth_id}"
        feature["id"] = three_letter
        properties["id"] = three_letter
        properties["territory_id"] = three_letter
        aliases = {
            str(properties[key]).strip().casefold()
            for key in ("ISO_A3", "ISO_A2")
            if properties.get(key) not in (None, "", -99, "-99")
        }
        properties["aliases"] = sorted(aliases - {three_letter})
        properties["valid_from"] = None
        properties["valid_to"] = None
    return normalize_feature_collection(working, quantization=quantization)


def normalize_historical_snapshots(
    snapshots: Mapping[int, dict[str, Any]],
    *,
    quantization: int = 1_000_001,
) -> dict[str, Any]:
    """Normalize dated historical-basemaps snapshots into valid-time features."""

    if not snapshots:
        raise ValueError("historical normalization requires at least one snapshot")
    years = sorted(snapshots)
    starts = {year: coerce_date(year) for year in years}
    combined: list[dict[str, Any]] = []
    for position, year in enumerate(years):
        working = copy.deepcopy(snapshots[year])
        features = working.get("features")
        if not isinstance(features, list):
            raise ValueError(f"historical snapshot {year} requires features list")
        next_start = starts[years[position + 1]] if position + 1 < len(years) else None
        for feature in features:
            if not isinstance(feature, dict):
                raise ValueError(f"historical snapshot {year} feature must contain a mapping")
            properties = feature.get("properties")
            if not isinstance(properties, dict):
                raise ValueError(
                    f"historical snapshot {year} feature properties must contain a mapping"
                )
            name = properties.get("NAME")
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f"historical snapshot {year} feature requires NAME")
            territory_id = _territory_slug(name)
            feature["id"] = territory_id
            properties["id"] = territory_id
            properties["territory_id"] = territory_id
            properties["name"] = name.strip()
            properties["aliases"] = []
            properties["valid_from"] = starts[year].isoformat()
            properties["valid_to"] = None if next_start is None else next_start.isoformat()
            properties["source_year"] = year
        normalized = normalize_feature_collection(working, quantization=quantization)
        combined.extend(normalized["features"])
    combined.sort(
        key=lambda feature: (
            str(feature["id"]),
            str(feature.get("properties", {}).get("valid_from") or ""),
        )
    )
    return {"features": combined, "type": "FeatureCollection"}


def _check_package_version(spec: DatasetSpec) -> None:
    if not spec.package.startswith("anima_ai_data."):
        return
    from anima_ai_data import __version__ as companion_version

    from anima import __version__ as main_version

    if companion_version != main_version:
        raise ValueError(
            "companion package version mismatch: "
            f"anima-ai-data {companion_version}; anima-ai {main_version}"
        )


def _checked_payload(spec: DatasetSpec, resource: ResourceSpec) -> bytes:
    _check_package_version(spec)
    payload = read_resource(spec.package, resource.path)
    if len(payload) != resource.size:
        raise ValueError(
            f"vendored resource size mismatch for {spec.dataset_id}/{resource.path}: "
            f"expected {resource.size}, got {len(payload)}"
        )
    actual = sha256(payload).hexdigest()
    if actual != resource.sha256:
        raise ValueError(
            f"vendored resource SHA-256 mismatch for {spec.dataset_id}/{resource.path}: "
            f"expected {resource.sha256}, got {actual}"
        )
    return payload


def load_geojson(dataset_id: str) -> dict[str, Any]:
    """Load and checksum a normalized vendored FeatureCollection."""

    spec = dataset_spec(dataset_id)
    features: list[dict[str, Any]] = []
    for resource in spec.resources:
        payload = _checked_payload(spec, resource)
        collection: Any = json.loads(payload)
        if not isinstance(collection, dict) or collection.get("type") != "FeatureCollection":
            raise ValueError(f"vendored resource is not FeatureCollection: {resource.path}")
        if canonical_geojson_bytes(collection) != payload:
            raise ValueError(f"vendored resource is not canonical GeoJSON: {resource.path}")
        raw_features = collection.get("features")
        if not isinstance(raw_features, list):
            raise ValueError(f"vendored resource lacks features list: {resource.path}")
        features.extend(raw_features)
    features.sort(
        key=lambda feature: (
            str(feature["id"]),
            str(feature.get("properties", {}).get("valid_from") or ""),
        )
    )
    return {"features": features, "type": "FeatureCollection"}


def load_map_dataset(dataset_id: str) -> MapDataset:
    """Build deterministic valid-time Shapely registry from vendored GeoJSON."""

    spec = dataset_spec(dataset_id)
    versions: list[TerritoryVersion] = []
    for feature in load_geojson(dataset_id)["features"]:
        properties = feature.get("properties", {})
        territory_id = str(properties.get("territory_id", feature["id"]))
        raw_aliases = properties.get("aliases", [])
        if not isinstance(raw_aliases, list):
            raise ValueError(f"territory aliases must be a list: {feature['id']}")
        versions.append(
            TerritoryVersion(
                territory_id,
                shape(feature["geometry"]),
                ValidityInterval(properties.get("valid_from"), properties.get("valid_to")),
                tuple(str(alias) for alias in raw_aliases),
                properties,
            )
        )
    return MapDataset(
        spec.dataset_id,
        versions,
        source_version=spec.source_version,
        metadata={"source_name": spec.source_name},
    )


def verify_vendored_data() -> tuple[str, ...]:
    """Return deterministic resource verification errors; empty tuple means valid."""

    errors: list[str] = []
    for spec in _catalog():
        try:
            _check_package_version(spec)
        except (ModuleNotFoundError, ValueError) as error:
            errors.append(str(error))
            continue
        for path in (spec.license_path, spec.attribution_path):
            try:
                if not read_resource(spec.package, path).strip():
                    errors.append(f"empty required resource: {spec.package}/{path}")
            except (FileNotFoundError, ModuleNotFoundError) as error:
                errors.append(f"missing required resource: {spec.package}/{path}: {error}")
        for resource in spec.resources:
            try:
                _checked_payload(spec, resource)
            except (FileNotFoundError, ModuleNotFoundError, ValueError) as error:
                errors.append(str(error))
    return tuple(sorted(errors))


__all__ = [
    "DatasetSpec",
    "ResourceSpec",
    "available_datasets",
    "canonical_geojson_bytes",
    "dataset_spec",
    "load_geojson",
    "load_map_dataset",
    "normalize_historical_snapshots",
    "normalize_natural_earth",
    "normalize_feature_collection",
    "parse_catalog",
    "read_resource",
    "verify_vendored_data",
]
