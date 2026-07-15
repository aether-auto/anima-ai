from __future__ import annotations

import pytest
from shapely.geometry import shape

from anima.data.simplification import TopologyParameters, simplify_feature_collection
from anima.data.vendored import load_geojson


def _country_pair() -> dict[str, object]:
    collection = load_geojson("natural-earth-50m")
    features = [
        feature
        for feature in collection["features"]
        if feature["id"] in {"fra", "deu"}
    ]
    assert {feature["id"] for feature in features} == {"fra", "deu"}
    return {"type": "FeatureCollection", "features": features}


@pytest.mark.parametrize("tolerance", (0.0, 0.01, 0.05))
def test_france_germany_border_remains_coincident_across_tolerances(
    tolerance: float,
) -> None:
    result = simplify_feature_collection(
        _country_pair(),
        parameters=TopologyParameters(tolerance=tolerance),
    )
    geometries = {
        feature["id"]: shape(feature["geometry"])
        for feature in result.feature_collection["features"]
    }

    assert result.shared_arc_indices("fra", "deu")
    assert geometries["fra"].intersection(geometries["deu"]).area == 0.0
    assert geometries["fra"].boundary.intersection(geometries["deu"].boundary).length > 0
