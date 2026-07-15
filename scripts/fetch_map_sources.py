#!/usr/bin/env python3
"""Fetch pinned map source files and pack deterministic source archives.

Every downloaded file is verified against ``scripts/map_sources.lock.json``
(SHA-256 + size, pinned upstream refs). Verified members are packed into two
uncompressed, fixed-timestamp zip archives so the archives themselves are
byte-reproducible inputs for ``scripts/build_map_data.py``.

Network access happens only here, never in the anima package itself.
"""

from __future__ import annotations

import argparse
import json
import zipfile
from hashlib import sha256
from pathlib import Path
from typing import Any
from urllib.request import urlopen

_ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


def _lock() -> dict[str, Any]:
    payload = json.loads((Path(__file__).parent / "map_sources.lock.json").read_text())
    if not isinstance(payload, dict):
        raise ValueError("map_sources.lock.json must contain a mapping")
    return payload


def _fetch_verified(url: str, *, expected_sha256: str, expected_size: int) -> bytes:
    with urlopen(url) as response:
        payload = response.read()
    if len(payload) != expected_size:
        raise ValueError(f"size mismatch for {url}: expected {expected_size}, got {len(payload)}")
    actual = sha256(payload).hexdigest()
    if actual != expected_sha256:
        raise ValueError(f"SHA-256 mismatch for {url}: expected {expected_sha256}, got {actual}")
    return payload


def _pack(destination: Path, members: dict[str, bytes]) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(members):
            info = zipfile.ZipInfo(name, date_time=_ZIP_EPOCH)
            info.external_attr = 0o644 << 16
            archive.writestr(info, members[name])
    return destination


def fetch_sources(output: Path) -> tuple[Path, Path]:
    """Download, verify, and pack both source archives; return their paths."""

    lock = _lock()

    natural = lock["natural_earth"]
    natural_members: dict[str, bytes] = {}
    for name, entry in sorted(natural["files"].items()):
        url = natural["url_template"].format(version=natural["version"], name=name)
        natural_members[f"geojson/{name}"] = _fetch_verified(
            url, expected_sha256=entry["sha256"], expected_size=entry["size"]
        )

    historical = lock["historical_basemaps"]
    historical_members: dict[str, bytes] = {}
    for name, entry in sorted(historical["files"].items()):
        url = historical["url_template"].format(commit=historical["commit"], name=name)
        historical_members[f"geojson/{name}"] = _fetch_verified(
            url, expected_sha256=entry["sha256"], expected_size=entry["size"]
        )

    natural_archive = _pack(
        output / f"natural-earth-{natural['version']}.zip", natural_members
    )
    historical_archive = _pack(
        output / f"historical-basemaps-{historical['commit'][:7]}.zip", historical_members
    )
    return natural_archive, historical_archive


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    natural_archive, historical_archive = fetch_sources(arguments.output.resolve())
    print(
        json.dumps(
            {
                "historical_archive": str(historical_archive),
                "historical_archive_sha256": sha256(
                    historical_archive.read_bytes()
                ).hexdigest(),
                "natural_earth_archive": str(natural_archive),
                "natural_earth_archive_sha256": sha256(
                    natural_archive.read_bytes()
                ).hexdigest(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
