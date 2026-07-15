"""``python -m anima.testing.goldens`` — generate / compare / update goldens.

Three verbs, all selecting baselines by ``--all`` or one-or-more ``--id``:

* ``generate`` renders each selected fixture into the gitignored working
  directory (``.golden-work/``). It never touches committed baselines.
* ``compare`` measures each candidate against its committed baseline with the
  deterministic YIQ comparator, writes actual/diff/report artifacts, and exits
  non-zero if any baseline is not an acceptable match.
* ``update`` atomically promotes a working candidate to its committed baseline
  path — but *refuses* unless the environment variable
  ``ANIMA_GOLDEN_IMAGE_REF`` equals the baseline's pinned ``container_ref``. A
  developer host cannot bless baselines; only a run inside the pinned golden
  container can.

``fmt`` rewrites the manifest in canonical form.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, cast

from anima.testing import pixelcompare, registry
from anima.testing.pixelcompare import RGBA
from anima.testing.registry import GoldenBaseline

CONTAINER_REF_ENV = "ANIMA_GOLDEN_IMAGE_REF"

FixtureFn = Callable[[dict[str, Any]], RGBA]


class GoldenError(RuntimeError):
    """Raised for operational failures (missing candidate, wrong container)."""


def _resolve_fixture(dotted: str) -> FixtureFn:
    module_name, _sep, attr = dotted.partition(":")
    module = importlib.import_module(module_name)
    fn = getattr(module, attr, None)
    if fn is None or not callable(fn):
        raise GoldenError(f"fixture {dotted!r} does not resolve to a callable")
    return cast(FixtureFn, fn)


def _select(
    baselines: list[GoldenBaseline], all_: bool, ids: Sequence[str]
) -> list[GoldenBaseline]:
    if all_ and ids:
        raise GoldenError("pass either --all or --id, not both")
    if all_:
        return baselines
    if not ids:
        raise GoldenError("select baselines with --all or one or more --id")
    return [registry.get(baselines, baseline_id) for baseline_id in ids]


def _candidate_path(root: Path, baseline: GoldenBaseline) -> Path:
    return registry.work_dir(root) / f"{baseline.id}.png"


def cmd_generate(root: Path, baselines: list[GoldenBaseline]) -> int:
    work = registry.work_dir(root)
    work.mkdir(parents=True, exist_ok=True)
    for baseline in baselines:
        fixture = _resolve_fixture(baseline.fixture)
        image = fixture(dict(baseline.params))
        actual_h, actual_w = image.shape[0], image.shape[1]
        if (actual_w, actual_h) != (baseline.width, baseline.height):
            raise GoldenError(
                f"fixture {baseline.fixture!r} produced {actual_w}x{actual_h}, "
                f"manifest declares {baseline.width}x{baseline.height}"
            )
        out = _candidate_path(root, baseline)
        pixelcompare.write_png(out, image)
        print(f"generated {baseline.id} -> {out}")
    return 0


def cmd_compare(root: Path, baselines: list[GoldenBaseline]) -> int:
    work = registry.work_dir(root)
    work.mkdir(parents=True, exist_ok=True)
    failed = False
    for baseline in baselines:
        candidate_path = _candidate_path(root, baseline)
        if not candidate_path.exists():
            raise GoldenError(
                f"no candidate for {baseline.id!r} at {candidate_path}; run 'generate' first"
            )
        baseline_png = root / baseline.png_path
        base_img = pixelcompare.read_png(baseline_png)
        cand_img = pixelcompare.read_png(candidate_path)

        report: dict[str, Any] = {
            "id": baseline.id,
            "baseline_path": str(baseline.png_path),
            "candidate_path": str(candidate_path),
        }
        try:
            result = pixelcompare.compare(base_img, cand_img, threshold=baseline.tolerance)
        except pixelcompare.DimensionMismatch as exc:
            report["dimension_mismatch"] = str(exc)
            report["acceptable"] = False
            failed = True
            _write_report(work, baseline, report)
            print(json.dumps(report, sort_keys=True))
            continue

        diff_path = work / f"{baseline.id}.diff.png"
        actual_path = work / f"{baseline.id}.actual.png"
        pixelcompare.write_png(diff_path, result.diff_image)
        pixelcompare.write_png(actual_path, cand_img)
        report.update(result.metrics)
        report["tolerance"] = baseline.tolerance
        report["diff_path"] = str(diff_path)
        report["actual_path"] = str(actual_path)
        _write_report(work, baseline, report)
        print(json.dumps(report, sort_keys=True))
        if not result.acceptable:
            failed = True
    return 1 if failed else 0


def _write_report(work: Path, baseline: GoldenBaseline, report: dict[str, Any]) -> None:
    (work / f"{baseline.id}.report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )


def cmd_update(root: Path, baselines: list[GoldenBaseline]) -> int:
    env_ref = os.environ.get(CONTAINER_REF_ENV, "")
    # Preflight ALL selected baselines before replacing any committed PNG, so a
    # failure partway through can never leave a partial bless on disk.
    for baseline in baselines:
        if env_ref != baseline.container_ref:
            raise GoldenError(
                f"refusing to bless {baseline.id!r}: {CONTAINER_REF_ENV}={env_ref!r} "
                f"does not match pinned container_ref {baseline.container_ref!r}. "
                "Baselines can only be blessed inside the pinned golden container."
            )
        if not _candidate_path(root, baseline).exists():
            raise GoldenError(
                f"no candidate for {baseline.id!r} at {_candidate_path(root, baseline)}; "
                "run 'generate' first"
            )
    for baseline in baselines:
        candidate_path = _candidate_path(root, baseline)
        target = root / baseline.png_path
        target.parent.mkdir(parents=True, exist_ok=True)
        # Atomic promote: replace within the same filesystem under the repo root.
        tmp = target.with_suffix(".png.tmp")
        tmp.write_bytes(candidate_path.read_bytes())
        os.replace(tmp, target)
        print(f"blessed {baseline.id} -> {target}")
    return 0


def cmd_fmt(root: Path) -> int:
    baselines = registry.parse_manifest(root)
    registry.write_manifest(root, baselines)
    print(f"canonicalized {registry.manifest_path(root)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="anima.testing.goldens", description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="repository root containing tests/golden/ (default: cwd)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for verb in ("generate", "compare", "update"):
        sp = sub.add_parser(verb)
        sp.add_argument("--all", action="store_true", help="select every baseline")
        sp.add_argument(
            "--id", action="append", default=[], help="select baseline by id (repeatable)"
        )
    sub.add_parser("fmt")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root: Path = args.root
    try:
        if args.command == "fmt":
            return cmd_fmt(root)
        baselines = registry.load_manifest(root)
        selected = _select(baselines, args.all, args.id)
        if args.command == "generate":
            return cmd_generate(root, selected)
        if args.command == "compare":
            return cmd_compare(root, selected)
        if args.command == "update":
            return cmd_update(root, selected)
        raise GoldenError(f"unknown command {args.command!r}")  # pragma: no cover
    except (GoldenError, registry.ManifestError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
