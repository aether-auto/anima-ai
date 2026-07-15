from __future__ import annotations

import json

import pytest
from shapely import box
from shapely.geometry import shape
from shapely.ops import unary_union

from anima.data.simplification import (
    TopologyParameters,
    simplify_feature_collection,
)


def _adjacent_collection(reverse: bool = False) -> dict[str, object]:
    shared_south_to_north = [
        [0.0, -2.0],
        [0.1, -1.5],
        [-0.1, -1.0],
        [0.1, -0.5],
        [-0.1, 0.0],
        [0.1, 0.5],
        [-0.1, 1.0],
        [0.1, 1.5],
        [0.0, 2.0],
    ]
    west = {
        "type": "Feature",
        "id": "west",
        "properties": {"id": "west"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[-2.0, -2.0], *shared_south_to_north, [-2.0, 2.0], [-2.0, -2.0]]
            ],
        },
    }
    east = {
        "type": "Feature",
        "id": "east",
        "properties": {"id": "east"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [0.0, -2.0],
                    [2.0, -2.0],
                    [2.0, 2.0],
                    *reversed(shared_south_to_north),
                ]
            ],
        },
    }
    features = [west, east]
    if reverse:
        features.reverse()
    return {"type": "FeatureCollection", "features": features}


def _features(result: object) -> dict[str, object]:
    return {
        str(feature["id"]): shape(feature["geometry"])
        for feature in result.feature_collection["features"]
    }


def test_parameters_are_explicit_and_validated() -> None:
    assert TopologyParameters() == TopologyParameters(
        quantization=1_000_001,
        tolerance=0.0,
        prevent_oversimplify=True,
    )

    with pytest.raises(ValueError, match="quantization"):
        TopologyParameters(quantization=1)
    with pytest.raises(ValueError, match="tolerance"):
        TopologyParameters(tolerance=-0.01)


@pytest.mark.parametrize("tolerance", (0.0, 0.05, 0.2))
def test_adjacent_polygons_share_same_quantized_arc_without_gap_or_overlap(
    tolerance: float,
) -> None:
    result = simplify_feature_collection(
        _adjacent_collection(),
        parameters=TopologyParameters(tolerance=tolerance),
    )
    features = _features(result)
    west = features["west"]
    east = features["east"]

    shared = result.shared_arc_indices("west", "east")
    west_refs = result.arc_references("west")
    east_refs = result.arc_references("east")
    union = unary_union((west, east))

    assert shared
    assert all(
        (index in west_refs and ~index in east_refs)
        or (~index in west_refs and index in east_refs)
        for index in shared
    )
    assert west.intersection(east).area == 0.0
    assert box(-2, -2, 2, 2).difference(union).area == pytest.approx(0.0, abs=1e-12)
    assert union.difference(box(-2, -2, 2, 2)).area == pytest.approx(0.0, abs=1e-12)
    assert all(
        isinstance(coordinate, int)
        for arc in result.topology["arcs"]
        for point in arc
        for coordinate in point
    )


def test_simplification_is_deterministic_across_input_order() -> None:
    parameters = TopologyParameters(quantization=100_001, tolerance=0.1)

    first = simplify_feature_collection(_adjacent_collection(), parameters=parameters)
    second = simplify_feature_collection(_adjacent_collection(reverse=True), parameters=parameters)

    assert first.to_topology_json() == second.to_topology_json()
    assert first.to_geojson() == second.to_geojson()
    assert json.loads(first.to_topology_json())["parameters"] == {
        "prevent_oversimplify": True,
        "quantization": 100_001,
        "tolerance": 0.1,
    }


def test_collection_rejects_duplicate_or_nonpolygon_features() -> None:
    duplicate = _adjacent_collection()
    duplicate["features"][1]["id"] = "west"
    duplicate["features"][1]["properties"]["id"] = "west"

    with pytest.raises(ValueError, match="duplicate feature id: west"):
        simplify_feature_collection(duplicate)

    point_collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "point",
                "properties": {},
                "geometry": {"type": "Point", "coordinates": [0, 0]},
            }
        ],
    }
    with pytest.raises(ValueError, match="Polygon or MultiPolygon"):
        simplify_feature_collection(point_collection)
