"""Deterministic map dataset and process-wide registry types."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from shapely.geometry import mapping, shape

from .base import DateLike, ValidityInterval, coerce_date
from .territory import ResolvedTerritory, TerritoryVersion, normalize_identifier


@dataclass(frozen=True, slots=True, init=False)
class MapDataset:
    """Immutable registry of canonical IDs and valid-time Shapely geometries."""

    dataset_id: str
    versions: tuple[TerritoryVersion, ...]
    source_version: str
    metadata: Mapping[str, object]
    _versions_by_id: Mapping[str, tuple[TerritoryVersion, ...]]
    _aliases: Mapping[str, str]

    def __init__(
        self,
        dataset_id: str,
        versions: Iterable[TerritoryVersion],
        *,
        source_version: str = "",
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        normalized_dataset_id = normalize_identifier(dataset_id, kind="dataset id")
        ordered = tuple(
            sorted(
                versions,
                key=lambda item: (
                    item.territory_id,
                    item.validity.start.isoformat() if item.validity.start else "",
                    item.validity.end.isoformat() if item.validity.end else "9999-12-31",
                ),
            )
        )
        if not ordered:
            raise ValueError(
                f"dataset must contain at least one territory: {normalized_dataset_id}"
            )

        grouped: dict[str, list[TerritoryVersion]] = defaultdict(list)
        aliases: dict[str, str] = {}
        canonical_ids = {version.territory_id for version in ordered}
        for version in ordered:
            grouped[version.territory_id].append(version)
            for alias in version.aliases:
                if alias in canonical_ids:
                    raise ValueError(
                        f"alias {alias!r} for {version.territory_id!r} shadows canonical territory"
                    )
                owner = aliases.get(alias)
                if owner is not None and owner != version.territory_id:
                    raise ValueError(
                        f"alias {alias!r} maps to both {owner!r} and {version.territory_id!r}"
                    )
                aliases[alias] = version.territory_id

        frozen_groups: dict[str, tuple[TerritoryVersion, ...]] = {}
        for territory_id, candidates in grouped.items():
            for position, left in enumerate(candidates):
                for right in candidates[position + 1 :]:
                    if left.validity.overlaps(right.validity):
                        raise ValueError(
                            "overlapping validity intervals for territory "
                            f"{territory_id!r}: {left.validity} and {right.validity}"
                        )
            frozen_groups[territory_id] = tuple(candidates)

        object.__setattr__(self, "dataset_id", normalized_dataset_id)
        object.__setattr__(self, "versions", ordered)
        object.__setattr__(self, "source_version", source_version)
        object.__setattr__(self, "metadata", MappingProxyType(dict(metadata or {})))
        object.__setattr__(self, "_versions_by_id", MappingProxyType(frozen_groups))
        object.__setattr__(self, "_aliases", MappingProxyType(aliases))

    def _unscoped(self, reference: str) -> str:
        normalized = reference.strip().casefold()
        if ":" not in normalized:
            return normalize_identifier(normalized, kind="territory reference")
        dataset_id, territory_id = normalized.split(":", maxsplit=1)
        if dataset_id != self.dataset_id:
            raise KeyError(
                f"territory reference targets dataset {dataset_id!r}, not {self.dataset_id!r}"
            )
        return normalize_identifier(territory_id, kind="territory reference")

    def resolve(self, reference: str, *, at: DateLike | None = None) -> ResolvedTerritory:
        """Resolve canonical/scoped/alias reference at date."""

        requested_id = self._unscoped(reference)
        territory_id = self._aliases.get(requested_id, requested_id)
        candidates = self._versions_by_id.get(territory_id)
        if candidates is None:
            raise KeyError(f"unknown territory {reference!r} in dataset {self.dataset_id!r}")

        if at is None:
            if len(candidates) == 1:
                return ResolvedTerritory(self.dataset_id, candidates[0])
            current = tuple(item for item in candidates if item.validity.end is None)
            if len(current) == 1:
                return ResolvedTerritory(self.dataset_id, current[0])
            raise ValueError(
                f"date required to resolve versioned territory {self.dataset_id}:{territory_id}"
            )

        instant = coerce_date(at)
        matches = tuple(item for item in candidates if item.validity.contains(instant))
        if not matches:
            ranges = ", ".join(
                f"[{item.validity.start or '-infinity'}, {item.validity.end or 'infinity'})"
                for item in candidates
            )
            raise KeyError(
                f"territory {self.dataset_id}:{territory_id} has no geometry at "
                f"{instant.isoformat()}; available intervals: {ranges}"
            )
        return ResolvedTerritory(self.dataset_id, matches[0])

    def canonical_id(self, reference: str, *, at: DateLike | None = None) -> str:
        """Return canonical dataset-scoped ID after date validation."""

        return self.resolve(reference, at=at).scoped_id

    def enumerate(self, *, at: DateLike | None = None) -> tuple[ResolvedTerritory, ...]:
        """Enumerate canonical records deterministically."""

        records: list[ResolvedTerritory] = []
        for territory_id in sorted(self._versions_by_id):
            try:
                records.append(self.resolve(territory_id, at=at))
            except KeyError:
                if at is None:
                    raise
        return tuple(records)

    def to_dict(self) -> dict[str, object]:
        """Return stable, serialization-safe mapping."""

        return {
            "dataset_id": self.dataset_id,
            "metadata": dict(self.metadata),
            "source_version": self.source_version,
            "territories": [
                {
                    "aliases": list(version.aliases),
                    "geometry": mapping(version.geometry),
                    "properties": dict(version.properties),
                    "territory_id": version.territory_id,
                    "validity": version.validity.to_dict(),
                }
                for version in self.versions
            ],
        }

    def to_yaml(self) -> str:
        """Serialize canonical YAML 1.2 using its deterministic JSON subset."""

        return json.dumps(
            self.to_dict(), ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True
        ) + "\n"

    @classmethod
    def from_yaml(cls, serialized: str) -> MapDataset:
        """Load canonical JSON-subset YAML produced by :meth:`to_yaml`."""

        raw = json.loads(serialized)
        if not isinstance(raw, dict):
            raise ValueError("dataset serialization must contain a mapping")
        territory_values = raw.get("territories")
        if not isinstance(territory_values, list):
            raise ValueError("dataset serialization requires territories list")
        versions = []
        for raw_version in territory_values:
            if not isinstance(raw_version, dict):
                raise ValueError("territory serialization must contain a mapping")
            validity = raw_version.get("validity", {})
            if not isinstance(validity, dict):
                raise ValueError("territory validity must contain a mapping")
            versions.append(
                TerritoryVersion(
                    str(raw_version["territory_id"]),
                    shape(raw_version["geometry"]),
                    ValidityInterval(validity.get("start"), validity.get("end")),
                    tuple(str(alias) for alias in raw_version.get("aliases", [])),
                    raw_version.get("properties", {}),
                )
            )
        metadata = raw.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError("dataset metadata must contain a mapping")
        return cls(
            str(raw["dataset_id"]),
            versions,
            source_version=str(raw.get("source_version", "")),
            metadata=metadata,
        )


@dataclass(frozen=True, slots=True, init=False)
class DatasetRegistry:
    """Immutable deterministic collection of datasets."""

    _datasets: Mapping[str, MapDataset] = field(repr=False)

    def __init__(self, datasets: Iterable[MapDataset] = ()) -> None:
        indexed: dict[str, MapDataset] = {}
        for dataset in datasets:
            if dataset.dataset_id in indexed:
                raise ValueError(f"duplicate dataset id: {dataset.dataset_id}")
            indexed[dataset.dataset_id] = dataset
        object.__setattr__(self, "_datasets", MappingProxyType(indexed))

    def get(self, dataset_id: str) -> MapDataset:
        normalized = normalize_identifier(dataset_id, kind="dataset id")
        try:
            return self._datasets[normalized]
        except KeyError as error:
            available = ", ".join(sorted(self._datasets)) or "<none>"
            raise KeyError(f"unknown dataset {normalized!r}; available: {available}") from error

    def enumerate(self) -> tuple[MapDataset, ...]:
        return tuple(self._datasets[key] for key in sorted(self._datasets))
