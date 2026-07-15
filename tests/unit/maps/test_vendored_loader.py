from __future__ import annotations

import json
from hashlib import sha256

import anima_ai_data
import pytest

from anima.data import vendored
from anima.data.vendored import (
    DatasetSpec,
    ResourceSpec,
    canonical_geojson_bytes,
    normalize_feature_collection,
    normalize_historical_snapshots,
    normalize_natural_earth,
    parse_catalog,
    read_resource,
    verify_vendored_data,
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


def _historical_collection(name: str, x: float) -> dict[str, object]:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"NAME": name, "BORDERPRECISION": 2},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[x, 0], [x + 1, 0], [x + 1, 1], [x, 1], [x, 0]]
                    ],
                },
            }
        ],
    }


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


def test_natural_earth_normalization_uses_canonical_iso_ids_and_aliases() -> None:
    collection = _collection()
    collection["features"][0]["properties"].update(
        {"ADM0_A3": "FRA", "ISO_A3": "FRA", "ISO_A2": "FR"}
    )
    collection["features"][1]["properties"].update(
        {"ADM0_A3": "DEU", "ISO_A3": "DEU", "ISO_A2": "DE"}
    )

    normalized = normalize_natural_earth(collection, quantization=100_001)

    assert [feature["id"] for feature in normalized["features"]] == ["deu", "fra"]
    assert normalized["features"][0]["properties"]["aliases"] == ["de"]
    assert normalized["features"][1]["properties"]["aliases"] == ["fr"]


def test_natural_earth_sovereignty_code_does_not_create_colliding_aliases() -> None:
    collection = _collection()
    collection["features"][0]["properties"].update(
        {"ADM0_A3": "FRA", "ISO_A3": "FRA", "ISO_A2": "FR", "SOV_A3": "FRA"}
    )
    collection["features"][1]["properties"].update(
        {"ADM0_A3": "NCL", "ISO_A3": "NCL", "ISO_A2": "NC", "SOV_A3": "FRA"}
    )

    normalized = normalize_natural_earth(collection, quantization=100_001)
    aliases = {
        feature["id"]: feature["properties"]["aliases"]
        for feature in normalized["features"]
    }

    assert aliases == {"fra": ["fr"], "ncl": ["nc"]}


def test_historical_snapshot_normalization_assigns_bce_half_open_validity() -> None:
    normalized = normalize_historical_snapshots(
        {
            -44: _historical_collection("Roman Republic", 0),
            1: _historical_collection("Roman Empire", 1),
        },
        quantization=100_001,
    )
    by_id = {feature["id"]: feature for feature in normalized["features"]}

    assert by_id["roman-republic"]["properties"]["valid_from"] == "-0044-01-01"
    assert by_id["roman-republic"]["properties"]["valid_to"] == "0001-01-01"
    assert by_id["roman-empire"]["properties"]["valid_from"] == "0001-01-01"
    assert by_id["roman-empire"]["properties"]["valid_to"] is None


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

    raw["datasets"][0]["resources"][0]["sha256"] = digest
    raw["datasets"][0]["resources"][0]["size"] = "12"
    with pytest.raises(ValueError, match="positive integer"):
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


def test_catalog_accepts_version_matched_companion_resource_package() -> None:
    raw = {
        "schema_version": 1,
        "datasets": [
            {
                "dataset_id": "historical-basemaps",
                "source_name": "historical-basemaps",
                "source_version": "5956740",
                "package": "anima_ai_data.historical_basemaps",
                "license_path": "LICENSE.txt",
                "attribution_path": "ATTRIBUTION.txt",
                "resources": [
                    {"path": "world_1914.geojson", "sha256": "a" * 64, "size": 1}
                ],
            }
        ],
    }

    assert parse_catalog(raw)[0].package == "anima_ai_data.historical_basemaps"


def test_missing_companion_package_hides_dataset_with_actionable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        vendored,
        "_package_installed",
        lambda package: not package.startswith("anima_ai_data"),
    )

    assert vendored.available_datasets() == ("natural-earth-110m", "natural-earth-50m")
    assert vendored.verify_vendored_data() == ()
    with pytest.raises(KeyError, match="maps-data"):
        vendored.dataset_spec("historical-basemaps")


def test_companion_package_version_must_match_main_package(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = read_resource(
        "anima_ai_data.historical_basemaps",
        "ATTRIBUTION.txt",
    )
    spec = DatasetSpec(
        dataset_id="historical-basemaps",
        source_name="historical-basemaps",
        source_version="5956740",
        package="anima_ai_data.historical_basemaps",
        license_path="LICENSE.txt",
        attribution_path="ATTRIBUTION.txt",
        resources=(
            ResourceSpec(
                path="ATTRIBUTION.txt",
                sha256=sha256(payload).hexdigest(),
                size=len(payload),
            ),
        ),
    )
    monkeypatch.setattr(vendored, "_catalog", lambda: (spec,))
    monkeypatch.setattr(anima_ai_data, "__version__", "9.9.9")

    assert verify_vendored_data() == (
        "companion package version mismatch: anima-ai-data 9.9.9; anima-ai 0.0.0.dev0",
    )
