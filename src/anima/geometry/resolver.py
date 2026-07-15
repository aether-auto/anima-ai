"""Shared geometry resolver used by map verification and rendering."""

from __future__ import annotations

from dataclasses import dataclass

from shapely import Point, box

from anima.maps import DatasetRegistry, DateLike, ResolvedTerritory


@dataclass(frozen=True, slots=True)
class GeometryResolver:
    """Resolve direct, point, and bounding-box map geometry through one index.

    Render and verify code should share one instance. Coordinates use dataset CRS;
    caller supplies matching projection before query when projected coordinates are
    needed.
    """

    registry: DatasetRegistry

    def resolve(
        self, dataset_id: str, territory_id: str, *, at: DateLike | None = None
    ) -> ResolvedTerritory:
        return self.registry.get(dataset_id).resolve(territory_id, at=at)

    def query_point(
        self,
        x: float,
        y: float,
        *,
        at: DateLike,
        dataset_id: str | None = None,
    ) -> tuple[ResolvedTerritory, ...]:
        probe = Point(float(x), float(y))
        return self._query(probe, at=at, dataset_id=dataset_id, predicate="covers")

    def query_bbox(
        self,
        bounds: tuple[float, float, float, float],
        *,
        at: DateLike,
        dataset_id: str | None = None,
    ) -> tuple[ResolvedTerritory, ...]:
        min_x, min_y, max_x, max_y = (float(value) for value in bounds)
        if min_x > max_x or min_y > max_y:
            raise ValueError(f"invalid bbox ordering: {bounds!r}")
        probe = box(min_x, min_y, max_x, max_y)
        return self._query(probe, at=at, dataset_id=dataset_id, predicate="intersects")

    def _query(
        self,
        probe: Point | object,
        *,
        at: DateLike,
        dataset_id: str | None,
        predicate: str,
    ) -> tuple[ResolvedTerritory, ...]:
        datasets = (
            (self.registry.get(dataset_id),)
            if dataset_id is not None
            else self.registry.enumerate()
        )
        matches: list[ResolvedTerritory] = []
        for dataset in datasets:
            for record in dataset.enumerate(at=at):
                if predicate == "covers":
                    matched = record.geometry.covers(probe)
                else:
                    matched = record.geometry.intersects(probe)
                if matched:
                    matches.append(record)
        return tuple(sorted(matches, key=lambda item: item.scoped_id))

