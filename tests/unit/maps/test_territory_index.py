from __future__ import annotations

from datetime import date

import pytest
from shapely import Polygon

from anima.data.territory_index import TerritoryIndex
from anima.maps import DatasetRegistry, MapDataset, TerritoryVersion, ValidityInterval


def _square(x: float) -> Polygon:
    return Polygon(((x, 0), (x + 1, 0), (x + 1, 1), (x, 1), (x, 0)))


def test_validity_intervals_are_half_open() -> None:
    older = ValidityInterval(date(1900, 1, 1), date(1918, 1, 1))
    newer = ValidityInterval(date(1918, 1, 1), None)

    assert older.contains(date(1917, 12, 31))
    assert not older.contains(date(1918, 1, 1))
    assert newer.contains(date(1918, 1, 1))


def test_dataset_rejects_overlapping_versions_for_same_territory() -> None:
    versions = (
        TerritoryVersion("state", _square(0), ValidityInterval(1900, 1920)),
        TerritoryVersion("state", _square(1), ValidityInterval(1919, 1930)),
    )

    with pytest.raises(ValueError, match="overlapping validity intervals.*state"):
        MapDataset("history", versions)


def test_dataset_rejects_alias_collision_between_canonical_ids() -> None:
    versions = (
        TerritoryVersion("alpha", _square(0), aliases=("shared",)),
        TerritoryVersion("beta", _square(1), aliases=("shared",)),
    )

    with pytest.raises(ValueError, match="alias 'shared'.*alpha.*beta"):
        MapDataset("modern", versions)


def test_direct_lookup_accepts_scoped_ids_aliases_and_years() -> None:
    dataset = MapDataset(
        "history",
        (
            TerritoryVersion(
                "germany",
                _square(0),
                ValidityInterval(1871, 1919),
                aliases=("deu", "german-empire"),
            ),
            TerritoryVersion(
                "germany",
                _square(1),
                ValidityInterval(1919, None),
                aliases=("deu",),
            ),
        ),
    )

    assert dataset.resolve("history:german-empire", at=1918).geometry.equals(_square(0))
    assert dataset.resolve("deu", at="1919-01-01").geometry.equals(_square(1))
    assert dataset.canonical_id("history:deu", at=1918) == "history:germany"


def test_dataset_enumeration_is_canonical_and_sorted() -> None:
    dataset = MapDataset(
        "modern",
        (
            TerritoryVersion("zeta", _square(2), aliases=("z",)),
            TerritoryVersion("alpha", _square(0), aliases=("a",)),
        ),
    )

    assert [record.scoped_id for record in dataset.enumerate()] == [
        "modern:alpha",
        "modern:zeta",
    ]


def test_serialization_is_stable_yaml_and_round_trips_geometry() -> None:
    dataset = MapDataset(
        "history",
        (
            TerritoryVersion(
                "alpha",
                _square(0),
                ValidityInterval("1900-01-01", "1950-01-01"),
                aliases=("a",),
                properties={"name": "Alpha", "rank": 2},
            ),
        ),
        source_version="fixture-1",
        metadata={"license": "CC0-1.0"},
    )

    first = dataset.to_yaml()
    second = MapDataset.from_yaml(first).to_yaml()

    assert first == second
    assert first.endswith("\n")
    assert '"dataset_id": "history"' in first
    assert MapDataset.from_yaml(first).resolve("alpha", at=1910).geometry.equals(_square(0))


def test_registry_and_index_query_point_and_bbox_through_same_resolver() -> None:
    dataset = MapDataset(
        "modern",
        (
            TerritoryVersion("west", _square(0)),
            TerritoryVersion("east", _square(1)),
        ),
    )
    registry = DatasetRegistry((dataset,))
    index = TerritoryIndex(registry)

    point_matches = index.query_point(0.5, 0.5, at=2024)
    bbox_matches = index.query_bbox((0.25, 0.25, 1.75, 0.75), at=2024)

    assert [match.scoped_id for match in point_matches] == ["modern:west"]
    assert [match.scoped_id for match in bbox_matches] == ["modern:east", "modern:west"]
    assert index.resolve("modern", "west", at=2024) == point_matches[0]


def test_registry_rejects_duplicate_dataset_ids() -> None:
    first = MapDataset("modern", (TerritoryVersion("alpha", _square(0)),))
    second = MapDataset("modern", (TerritoryVersion("beta", _square(1)),))

    with pytest.raises(ValueError, match="duplicate dataset id: modern"):
        DatasetRegistry((first, second))

