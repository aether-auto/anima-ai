"""Deterministic source-archive builder for offline map package resources."""

from __future__ import annotations

import json
import re
import tarfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any

from anima.maps import coerce_date

from .vendored import (
    canonical_geojson_bytes,
    normalize_historical_snapshots,
    normalize_natural_earth,
)

_HISTORICAL_SNAPSHOT = re.compile(r"world_(?P<bce>bc)?(?P<year>[1-9]\d*)\.geojson")


@dataclass(frozen=True, slots=True)
class BuildPaths:
    """Destination roots for main wheel, companion wheel, and audit manifests."""

    main_data: Path
    companion_data: Path
    manifests: Path


@dataclass(frozen=True, slots=True)
class BuildResult:
    """Stable generated-file inventory."""

    generated_files: tuple[Path, ...]


def _archive_members(path: Path) -> dict[str, bytes]:
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            return {
                name: archive.read(name)
                for name in sorted(archive.namelist())
                if not name.endswith("/")
            }
    if tarfile.is_tarfile(path):
        members: dict[str, bytes] = {}
        with tarfile.open(path) as archive:
            for member in sorted(archive.getmembers(), key=lambda item: item.name):
                if not member.isfile():
                    continue
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise ValueError(f"cannot read archive member: {member.name}")
                members[member.name] = extracted.read()
        return members
    raise ValueError(f"unsupported source archive format: {path}")


def _one_member(
    members: dict[str, bytes],
    predicate: Callable[[str], bool],
    *,
    description: str,
) -> tuple[str, bytes]:
    matches = tuple((name, payload) for name, payload in members.items() if predicate(name))
    if len(matches) != 1:
        names = ", ".join(name for name, _ in matches) or "<none>"
        raise ValueError(f"source archive requires exactly one {description}; found: {names}")
    return matches[0]


def _has_suffix(suffix: str) -> Callable[[str], bool]:
    return lambda name: name.endswith(suffix)


def _collection(payload: bytes, *, source: str) -> dict[str, Any]:
    value: Any = json.loads(payload)
    if not isinstance(value, dict) or value.get("type") != "FeatureCollection":
        raise ValueError(f"source member is not GeoJSON FeatureCollection: {source}")
    return value


def _write(path: Path, payload: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def _resource(path: str, payload: bytes) -> dict[str, object]:
    return {"path": path, "sha256": sha256(payload).hexdigest(), "size": len(payload)}


def _source_record(path: str, payload: bytes) -> dict[str, object]:
    return {"path": path, "sha256": sha256(payload).hexdigest(), "size": len(payload)}


def build_vendored_data(
    natural_earth_archive: Path,
    historical_archive: Path,
    *,
    paths: BuildPaths,
    historical_source_version: str,
    natural_earth_source_version: str = "5.1.2",
    quantization: int = 1_000_001,
) -> BuildResult:
    """Build normalized package data and immutable manifests from pinned archives."""

    if not historical_source_version.strip() or not natural_earth_source_version.strip():
        raise ValueError("source versions must be non-empty immutable refs")
    natural_members = _archive_members(natural_earth_archive)
    historical_members = _archive_members(historical_archive)

    natural_outputs: list[tuple[str, bytes, str, bytes]] = []
    for scale in ("110m", "50m"):
        source_suffix = f"geojson/ne_{scale}_admin_0_countries.geojson"
        source_name, source_payload = _one_member(
            natural_members,
            _has_suffix(source_suffix),
            description=f"Natural Earth {scale} Admin 0 Countries GeoJSON",
        )
        normalized = normalize_natural_earth(
            _collection(source_payload, source=source_name),
            quantization=quantization,
        )
        output_payload = canonical_geojson_bytes(normalized)
        natural_outputs.append(
            (f"ne_{scale}/countries.geojson", output_payload, source_name, source_payload)
        )

    snapshots: dict[int, dict[str, Any]] = {}
    snapshot_sources: dict[int, tuple[str, bytes]] = {}
    for name, payload in historical_members.items():
        matched = _HISTORICAL_SNAPSHOT.fullmatch(PurePosixPath(name).name)
        if matched is None:
            continue
        year = int(matched.group("year"))
        if matched.group("bce") is not None:
            year = -year
        if year in snapshots:
            raise ValueError(f"duplicate historical snapshot year in archive: {year}")
        snapshots[year] = _collection(payload, source=name)
        snapshot_sources[year] = (name, payload)
    historical_normalized = normalize_historical_snapshots(
        snapshots,
        quantization=quantization,
    )
    historical_payload = canonical_geojson_bytes(historical_normalized)

    generated: list[Path] = []
    for output_path, output_payload, _, _ in natural_outputs:
        generated.append(
            _write(paths.main_data / "natural_earth" / output_path, output_payload)
        )
    generated.append(_write(paths.companion_data / "historical.geojson", historical_payload))

    catalog = {
        "datasets": [
            {
                "attribution_path": "ATTRIBUTION.txt",
                "dataset_id": "historical-basemaps",
                "license_path": "LICENSE.txt",
                "package": "anima_ai_data.historical_basemaps",
                "resources": [_resource("historical.geojson", historical_payload)],
                "source_name": "historical-basemaps",
                "source_version": historical_source_version,
            },
            *(
                {
                    "attribution_path": "ATTRIBUTION.txt",
                    "dataset_id": f"natural-earth-{scale}",
                    "license_path": "LICENSE.txt",
                    "package": "anima.data.natural_earth",
                    "resources": [_resource(output_path, output_payload)],
                    "source_name": "Natural Earth",
                    "source_version": natural_earth_source_version,
                }
                for scale, (output_path, output_payload, _, _) in zip(
                    ("110m", "50m"), natural_outputs, strict=True
                )
            ),
        ],
        "schema_version": 1,
    }
    generated.append(_write(paths.main_data / "catalog.json", canonical_geojson_bytes(catalog)))

    natural_manifest = {
        "quantization": quantization,
        "resources": [
            {
                "dataset_id": f"natural-earth-{scale}",
                "normalized": _resource(output_path, output_payload),
                "source": _source_record(source_name, source_payload),
            }
            for scale, (output_path, output_payload, source_name, source_payload) in zip(
                ("110m", "50m"), natural_outputs, strict=True
            )
        ],
        "schema_version": 1,
        "source": {
            "archive_sha256": sha256(natural_earth_archive.read_bytes()).hexdigest(),
            "name": "Natural Earth",
            "version": natural_earth_source_version,
        },
    }
    historical_years = sorted(snapshot_sources)
    historical_manifest = {
        "normalized": _resource("historical.geojson", historical_payload),
        "quantization": quantization,
        "schema_version": 1,
        "snapshots": [
            {
                "source": _source_record(*snapshot_sources[year]),
                "valid_from": coerce_date(year).isoformat(),
                "valid_to": (
                    None
                    if position + 1 == len(historical_years)
                    else coerce_date(historical_years[position + 1]).isoformat()
                ),
                "year": year,
            }
            for position, year in enumerate(historical_years)
        ],
        "source": {
            "archive_sha256": sha256(historical_archive.read_bytes()).hexdigest(),
            "name": "historical-basemaps",
            "version": historical_source_version,
        },
    }
    generated.append(
        _write(
            paths.manifests / "natural_earth_checksums.json",
            canonical_geojson_bytes(natural_manifest),
        )
    )
    generated.append(
        _write(
            paths.manifests / "historical_basemaps_checksums.json",
            canonical_geojson_bytes(historical_manifest),
        )
    )
    return BuildResult(tuple(sorted(generated, key=lambda path: path.as_posix())))


__all__ = ["BuildPaths", "BuildResult", "build_vendored_data"]
