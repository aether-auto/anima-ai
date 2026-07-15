from __future__ import annotations

from shapely import box

from anima.data.territory_index import TerritoryIndex
from anima.maps import DatasetRegistry, MapDataset, TerritoryVersion, ValidityInterval


def test_historical_resolution_changes_geometry_at_exact_transition() -> None:
    historical = MapDataset(
        "historical",
        (
            TerritoryVersion("poland", box(0, 0, 1, 1), ValidityInterval(1918, 1939)),
            TerritoryVersion("poland", box(1, 0, 2, 1), ValidityInterval(1939, 1945)),
            TerritoryVersion("poland", box(2, 0, 3, 1), ValidityInterval(1945, None)),
        ),
    )
    index = TerritoryIndex(DatasetRegistry((historical,)))

    assert index.resolve("historical", "poland", at="1938-12-31").bbox == (0.0, 0.0, 1.0, 1.0)
    assert index.resolve("historical", "poland", at="1939-01-01").bbox == (1.0, 0.0, 2.0, 1.0)
    assert index.resolve("historical", "poland", at="1945-01-01").bbox == (2.0, 0.0, 3.0, 1.0)


def test_historical_queries_filter_nonmatching_periods() -> None:
    historical = MapDataset(
        "historical",
        (
            TerritoryVersion("former", box(0, 0, 1, 1), ValidityInterval(1900, 1910)),
            TerritoryVersion("present", box(0, 0, 1, 1), ValidityInterval(1910, None)),
        ),
    )
    index = TerritoryIndex(DatasetRegistry((historical,)))

    assert [item.scoped_id for item in index.query_point(0.5, 0.5, at=1909)] == [
        "historical:former"
    ]
    assert [item.scoped_id for item in index.query_point(0.5, 0.5, at=1910)] == [
        "historical:present"
    ]
