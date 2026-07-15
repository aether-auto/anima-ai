from __future__ import annotations

import json
import os
from pathlib import Path

import pyproj
import pytest
from shapely import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)

from anima.data.projections import (
    Projection,
    ProjectionDefinition,
    regional_equal_area,
    world_equal_earth,
)


def _geometry_cases() -> tuple[object, ...]:
    polygon = Polygon(((-2, 48), (2, 48), (2, 51), (-2, 51), (-2, 48)))
    return (
        Point(0, 50),
        Point(0, 50, 100),
        LineString(((-4, 49), (0, 50), (4, 51))),
        Polygon(((-4, 49), (4, 49), (4, 52), (-4, 52), (-4, 49))),
        MultiPoint(((-2, 49), (2, 51))),
        MultiLineString((((-3, 49), (0, 50)), ((0, 50), (3, 51)))),
        MultiPolygon((polygon, Polygon(((3, 48), (4, 48), (4, 49), (3, 49), (3, 48))))),
        GeometryCollection((Point(0, 50), LineString(((-1, 49), (1, 51))))),
    )


def test_pyproj_is_pinned_and_network_is_disabled() -> None:
    assert pyproj.__version__ == "3.7.1"
    assert '"pyproj==3.7.1"' in Path("pyproject.toml").read_text()
    assert os.environ["PROJ_NETWORK"] == "OFF"
    assert not pyproj.network.is_network_enabled()


def test_world_definition_is_canonical_equal_earth() -> None:
    definition = world_equal_earth()

    assert definition == ProjectionDefinition(
        method="equal-earth",
        target_crs="EPSG:8857",
        origin=None,
    )
    assert definition.always_xy is True
    assert definition.to_json() == (
        '{"always_xy":true,"method":"equal-earth","origin":null,'
        '"source_crs":"EPSG:4326","target_crs":"EPSG:8857"}\n'
    )
    assert ProjectionDefinition.from_json(definition.to_json()) == definition


def test_regional_definition_is_caller_centered_wgs84_laea() -> None:
    definition = regional_equal_area(longitude=12.5, latitude=47.25)

    assert definition.method == "lambert-azimuthal-equal-area"
    assert definition.origin == (12.5, 47.25)
    assert "+proj=laea" in definition.target_crs
    assert "+lon_0=12.5" in definition.target_crs
    assert "+lat_0=47.25" in definition.target_crs
    assert "+datum=WGS84" in definition.target_crs
    assert ProjectionDefinition.from_json(definition.to_json()) == definition


@pytest.mark.parametrize(
    ("longitude", "latitude", "message"),
    ((181, 0, "longitude"), (0, 91, "latitude"), (float("nan"), 0, "finite")),
)
def test_regional_origin_validation(longitude: float, latitude: float, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        regional_equal_area(longitude=longitude, latitude=latitude)


@pytest.mark.parametrize("definition", (world_equal_earth(), regional_equal_area(0, 50)))
@pytest.mark.parametrize("geometry", _geometry_cases())
def test_projection_round_trip_preserves_geometry_type_and_coordinates(
    definition: ProjectionDefinition, geometry: object
) -> None:
    projection = Projection(definition)

    projected = projection.forward(geometry)
    restored = projection.inverse(projected)

    assert projected.geom_type == geometry.geom_type
    assert restored.geom_type == geometry.geom_type
    assert restored.has_z == geometry.has_z
    assert restored.equals_exact(geometry, tolerance=1e-8)


@pytest.mark.parametrize("definition", (world_equal_earth(), regional_equal_area(-96, 40)))
def test_point_round_trip_is_deterministic_for_coordinate_grid(
    definition: ProjectionDefinition,
) -> None:
    projection = Projection(definition)
    coordinates = ((-120.25, 35.5), (-96.0, 40.0), (-75.25, 45.75))

    first = [projection.inverse_point(*projection.forward_point(*point)) for point in coordinates]
    second = [projection.inverse_point(*projection.forward_point(*point)) for point in coordinates]

    assert first == second
    for actual, expected in zip(first, coordinates, strict=True):
        assert actual == pytest.approx(expected, abs=1e-9)


def test_projection_definition_rejects_noncanonical_payload() -> None:
    payload = json.dumps(
        {
            "always_xy": False,
            "method": "equal-earth",
            "origin": None,
            "source_crs": "EPSG:4326",
            "target_crs": "EPSG:8857",
        }
    )

    with pytest.raises(ValueError, match="always_xy must be true"):
        ProjectionDefinition.from_json(payload)
