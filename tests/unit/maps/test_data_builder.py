from __future__ import annotations

import json
import zipfile
from pathlib import Path

from anima.data.builder import BuildPaths, build_vendored_data


def _write_zip(path: Path, members: dict[str, object]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in sorted(members.items()):
            archive.writestr(name, json.dumps(value, sort_keys=True))


def _countries() -> dict[str, object]:
    features = []
    for territory_id, alpha2, x in (("FRA", "FR", 0), ("DEU", "DE", 1)):
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "ADM0_A3": territory_id,
                    "ISO_A3": territory_id,
                    "ISO_A2": alpha2,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[x, 0], [x + 1, 0], [x + 1, 1], [x, 1], [x, 0]]
                    ],
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}


def _historical(name: str, x: float) -> dict[str, object]:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"NAME": name},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[x, 0], [x + 1, 0], [x + 1, 1], [x, 1], [x, 0]]
                    ],
                },
            }
        ],
    }


def test_builder_normalizes_archives_and_writes_reproducible_catalog_and_manifests(
    tmp_path: Path,
) -> None:
    natural_earth = tmp_path / "natural-earth.zip"
    historical = tmp_path / "historical.zip"
    countries = _countries()
    _write_zip(
        natural_earth,
        {
            "natural-earth/geojson/ne_110m_admin_0_countries.geojson": countries,
            "natural-earth/geojson/ne_50m_admin_0_countries.geojson": countries,
        },
    )
    _write_zip(
        historical,
        {
            "historical-basemaps/geojson/world_bc44.geojson": _historical(
                "Roman Republic", 0
            ),
            "historical-basemaps/geojson/world_1.geojson": _historical("Roman Empire", 1),
        },
    )
    paths = BuildPaths(
        main_data=tmp_path / "main/anima/data",
        companion_data=tmp_path / "companion/anima_ai_data/historical_basemaps",
        manifests=tmp_path / "docs/manifests",
    )

    first = build_vendored_data(
        natural_earth,
        historical,
        paths=paths,
        historical_source_version="5956740",
        quantization=100_001,
    )
    first_bytes = {path: path.read_bytes() for path in first.generated_files}
    second = build_vendored_data(
        natural_earth,
        historical,
        paths=paths,
        historical_source_version="5956740",
        quantization=100_001,
    )

    assert first == second
    assert first_bytes == {path: path.read_bytes() for path in second.generated_files}
    catalog = json.loads((paths.main_data / "catalog.json").read_bytes())
    assert [dataset["dataset_id"] for dataset in catalog["datasets"]] == [
        "historical-basemaps",
        "natural-earth-110m",
        "natural-earth-50m",
    ]
    historical_payload = json.loads(
        (paths.companion_data / "historical.geojson").read_bytes()
    )
    assert any(
        feature["properties"]["valid_from"].startswith("-")
        for feature in historical_payload["features"]
    )
    assert (paths.manifests / "natural_earth_checksums.json").is_file()
    assert (paths.manifests / "historical_basemaps_checksums.json").is_file()
