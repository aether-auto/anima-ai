#!/usr/bin/env python3
"""Build deterministic map package resources from pinned source archives."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from anima.data.builder import BuildPaths, build_vendored_data


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--natural-earth-archive", type=Path, required=True)
    parser.add_argument("--historical-archive", type=Path, required=True)
    parser.add_argument("--historical-version", required=True)
    parser.add_argument("--natural-earth-version", default="5.1.2")
    parser.add_argument("--quantization", type=int, default=1_000_001)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    return parser.parse_args()


def main() -> int:
    arguments = _arguments()
    root = arguments.project_root.resolve()
    result = build_vendored_data(
        arguments.natural_earth_archive.resolve(),
        arguments.historical_archive.resolve(),
        paths=BuildPaths(
            main_data=root / "src/anima/data",
            companion_data=(
                root
                / "packages/anima-ai-data/src/anima_ai_data/historical_basemaps"
            ),
            manifests=root / "docs/manifests",
        ),
        historical_source_version=arguments.historical_version,
        natural_earth_source_version=arguments.natural_earth_version,
        quantization=arguments.quantization,
    )
    print(
        json.dumps(
            {
                "generated_files": [
                    path.relative_to(root).as_posix() for path in result.generated_files
                ]
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
