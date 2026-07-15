"""Tests for the manifest-backed GoldenBaseline registry."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from anima.testing import pixelcompare, registry
from anima.testing.registry import GoldenBaseline, ManifestError

_REF = "ghcr.io/anima/anima-golden@sha256:" + "a" * 64


def _write_png(path: Path, width: int, height: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    arr = np.zeros((height, width, 4), dtype=np.uint8)
    arr[..., 3] = 255
    pixelcompare.write_png(path, arr)


def _baseline(baseline_id: str = "foo", *, width: int = 8, height: int = 8) -> GoldenBaseline:
    return GoldenBaseline(
        id=baseline_id,
        fixture="pkg.mod:fixture",
        params={},
        width=width,
        height=height,
        png_path=f"tests/golden/baselines/{baseline_id}.png",
        tolerance=0.1,
        container_ref=_REF,
    )


def _make_root(tmp_path: Path, baselines: list[GoldenBaseline]) -> Path:
    registry.write_manifest(tmp_path, baselines)
    for baseline in baselines:
        _write_png(tmp_path / baseline.png_path, baseline.width, baseline.height)
    return tmp_path


_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_committed_manifest_is_valid() -> None:
    # The real, committed manifest + baseline PNGs validate end-to-end:
    # canonical form, digest-pinned container refs, and matching image
    # dimensions. This guards against a baseline being committed out of shape.
    baselines = registry.validate(_REPO_ROOT)
    assert any(b.id == "trivial-shape-fixture" for b in baselines)
    trivial = registry.get(baselines, "trivial-shape-fixture")
    assert (trivial.width, trivial.height) == (256, 256)
    assert "@sha256:" in trivial.container_ref


def test_valid_manifest_loads_and_validates(tmp_path: Path) -> None:
    root = _make_root(tmp_path, [_baseline("foo"), _baseline("bar")])
    loaded = registry.validate(root)
    assert {b.id for b in loaded} == {"foo", "bar"}


def test_canonicalize_params_sorts_and_normalizes_floats() -> None:
    canonical = registry.canonicalize_params({"b": 2.0, "a": {"y": 1, "x": 3.5}})
    assert canonical == {"a": {"x": 3.5, "y": 1}, "b": 2}
    assert isinstance(canonical["b"], int)


def test_duplicate_ids_rejected(tmp_path: Path) -> None:
    # Two entries with the same id, written raw to bypass the dataclass set.
    obj = _baseline("dup").to_json_obj()
    registry.manifest_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    registry.manifest_path(tmp_path).write_text(
        json.dumps([obj, obj], indent=2, sort_keys=True) + "\n"
    )
    with pytest.raises(ManifestError, match="duplicate"):
        registry.load_manifest(tmp_path)


def test_missing_png_rejected(tmp_path: Path) -> None:
    registry.write_manifest(tmp_path, [_baseline("foo")])
    with pytest.raises(ManifestError, match="PNG missing"):
        registry.validate(tmp_path)


def test_orphan_png_rejected(tmp_path: Path) -> None:
    root = _make_root(tmp_path, [_baseline("foo")])
    _write_png(registry.baselines_dir(root) / "stray.png", 8, 8)
    with pytest.raises(ManifestError, match="orphan"):
        registry.validate(root)


def test_dimension_mismatch_rejected(tmp_path: Path) -> None:
    baseline = _baseline("foo", width=8, height=8)
    registry.write_manifest(tmp_path, [baseline])
    _write_png(tmp_path / baseline.png_path, 8, 6)  # actual image is 8x6, manifest 8x8.
    with pytest.raises(ManifestError, match="dimension mismatch"):
        registry.validate(tmp_path)


def test_non_canonical_serialization_rejected(tmp_path: Path) -> None:
    # A param float that should collapse to int (2.0 -> 2): on-disk 2.0 is not
    # canonical form and must be rejected so source-control diffs stay stable.
    obj = _baseline("foo").to_json_obj()
    obj["params"] = {"scale": 2.0}
    registry.manifest_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    registry.manifest_path(tmp_path).write_text(json.dumps([obj], indent=2) + "\n")
    with pytest.raises(ManifestError, match="canonical"):
        registry.load_manifest(tmp_path)


def test_bad_container_ref_rejected(tmp_path: Path) -> None:
    obj = _baseline("foo").to_json_obj()
    obj["container_ref"] = "ghcr.io/anima/anima-golden:latest"  # not digest-pinned.
    registry.manifest_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    registry.manifest_path(tmp_path).write_text(json.dumps([obj], indent=2, sort_keys=True) + "\n")
    with pytest.raises(ManifestError, match="digest"):
        registry.load_manifest(tmp_path)


def test_bad_fixture_path_rejected(tmp_path: Path) -> None:
    obj = _baseline("foo").to_json_obj()
    obj["fixture"] = "not_a_dotted_path"
    registry.manifest_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    registry.manifest_path(tmp_path).write_text(json.dumps([obj], indent=2, sort_keys=True) + "\n")
    with pytest.raises(ManifestError, match="dotted path"):
        registry.load_manifest(tmp_path)


def test_tolerance_out_of_range_rejected(tmp_path: Path) -> None:
    obj = _baseline("foo").to_json_obj()
    obj["tolerance"] = 1.5
    registry.manifest_path(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    registry.manifest_path(tmp_path).write_text(json.dumps([obj], indent=2, sort_keys=True) + "\n")
    with pytest.raises(ManifestError, match="tolerance"):
        registry.load_manifest(tmp_path)
