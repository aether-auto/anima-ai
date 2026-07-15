from __future__ import annotations

import json

import pytest

from anima.data.vendored import (
    DatasetSpec,
    ResourceSpec,
    canonical_geojson_bytes,
    normalize_feature_collection,
    parse_catalog,
)


def _collection(reverse: bool = False) -> dict[str, object]:
    west = {
        "type": "Feature",
        "id": "WEST",
        "properties": {"name": "West", "territory_id": "WEST"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
        },
    }
    east = {
        "type": "Feature",
        "id": "EAST",
        "properties": {"name": "East", "territory_id": "EAST"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[1, 0], [2, 0], [2, 1], [1, 1], [1, 0]]],
        },
    }
    features = [west, east]
    if reverse:
        features.reverse()
    return {"type": "FeatureCollection", "features": features}


def test_normalization_is_topology_quantized_and_input_order_independent() -> None:
    first = normalize_feature_collection(_collection(), quantization=100_001)
    second = normalize_feature_collection(_collection(reverse=True), quantization=100_001)

    assert first == second
    assert [feature["id"] for feature in first["features"]] == ["east", "west"]
    assert all(
        feature["properties"]["territory_id"] == feature["id"]
        for feature in first["features"]
    )
    assert canonical_geojson_bytes(first).endswith(b"\n")
    assert canonical_geojson_bytes(first) == canonical_geojson_bytes(
        json.loads(canonical_geojson_bytes(first))
    )


def test_catalog_parser_requires_immutable_checksums_and_unique_ids() -> None:
    digest = "a" * 64
    raw = {
        "schema_version": 1,
        "datasets": [
            {
                "dataset_id": "natural-earth-110m",
                "source_name": "Natural Earth",
                "source_version": "5.1.2",
                "package": "anima.data.natural_earth",
                "license_path": "LICENSE.txt",
                "attribution_path": "ATTRIBUTION.txt",
                "resources": [
                    {"path": "ne_110m/countries.geojson", "sha256": digest, "size": 12}
                ],
            }
        ],
    }

    parsed = parse_catalog(raw)

    assert parsed == (
        DatasetSpec(
            dataset_id="natural-earth-110m",
            source_name="Natural Earth",
            source_version="5.1.2",
            package="anima.data.natural_earth",
            license_path="LICENSE.txt",
            attribution_path="ATTRIBUTION.txt",
            resources=(
                ResourceSpec(
                    path="ne_110m/countries.geojson",
                    sha256=digest,
                    size=12,
                ),
            ),
        ),
    )

    raw["datasets"][0]["resources"][0]["sha256"] = "mutable"
    with pytest.raises(ValueError, match="SHA-256"):
        parse_catalog(raw)


def test_catalog_parser_rejects_path_traversal() -> None:
    raw = {
        "schema_version": 1,
        "datasets": [
            {
                "dataset_id": "unsafe",
                "source_name": "source",
                "source_version": "1",
                "package": "anima.data",
                "license_path": "LICENSE.txt",
                "attribution_path": "ATTRIBUTION.txt",
                "resources": [{"path": "../secret", "sha256": "a" * 64, "size": 1}],
            }
        ],
    }

    with pytest.raises(ValueError, match="relative resource path"):
        parse_catalog(raw)
