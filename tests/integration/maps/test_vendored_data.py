from __future__ import annotations

from hashlib import sha256

from anima.data.vendored import (
    available_datasets,
    canonical_geojson_bytes,
    dataset_spec,
    load_geojson,
    load_map_dataset,
    read_resource,
    verify_vendored_data,
)


def test_all_vendored_datasets_load_and_match_manifests_offline() -> None:
    assert available_datasets() == (
        "historical-basemaps",
        "natural-earth-110m",
        "natural-earth-50m",
    )
    assert verify_vendored_data() == ()

    for dataset_id in available_datasets():
        spec = dataset_spec(dataset_id)
        assert spec.source_version
        assert read_resource(spec.package, spec.license_path).strip()
        assert read_resource(spec.package, spec.attribution_path).strip()
        for resource in spec.resources:
            payload = read_resource(spec.package, resource.path)
            assert len(payload) == resource.size
            assert sha256(payload).hexdigest() == resource.sha256


def test_natural_earth_scales_are_real_normalized_country_collections() -> None:
    expected_minimum = {"natural-earth-110m": 170, "natural-earth-50m": 240}

    for dataset_id, minimum in expected_minimum.items():
        collection = load_geojson(dataset_id)
        ids = {feature["id"] for feature in collection["features"]}

        assert len(collection["features"]) >= minimum
        assert {"fra", "deu", "usa", "chn"} <= ids
        assert canonical_geojson_bytes(collection) == read_resource(
            dataset_spec(dataset_id).package,
            dataset_spec(dataset_id).resources[0].path,
        )

        # Every scale must load into the resolver: shipped aliases must never
        # shadow canonical IDs or collide across features.
        dataset = load_map_dataset(dataset_id)
        assert dataset.resolve("fr").territory_id == "fra"
        assert dataset.resolve("us").territory_id == "usa"


def test_historical_basemaps_cover_multiple_eras_and_resolve_dates() -> None:
    collection = load_geojson("historical-basemaps")
    starts = {
        feature["properties"]["valid_from"]
        for feature in collection["features"]
        if feature["properties"]["valid_from"] is not None
    }
    dataset = load_map_dataset("historical-basemaps")

    assert min(starts) < "1900-01-01"
    assert max(starts) >= "2000-01-01"
    assert len(dataset.versions) >= 500
    assert dataset.enumerate(at=1914)
    assert dataset.enumerate(at=1945)
    assert dataset.enumerate(at=2010)
