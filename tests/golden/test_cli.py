"""Tests for the ``python -m anima.testing.goldens`` CLI (generate/compare/update).

Uses a lightweight injected fixture module (no skia) so the CLI's control flow
is exercised deterministically and fast.
"""

from __future__ import annotations

import sys
import types
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from anima.testing import goldens, pixelcompare, registry
from anima.testing.pixelcompare import RGBA
from anima.testing.registry import GoldenBaseline

_REF = "ghcr.io/anima/anima-golden@sha256:" + "b" * 64
_COLOR = (30, 60, 90, 255)


def _solid(_params: dict[str, Any]) -> RGBA:
    arr = np.empty((8, 8, 4), dtype=np.uint8)
    arr[..., :] = _COLOR
    return arr


@pytest.fixture(autouse=True)
def _inject_fixture_module() -> Iterator[None]:
    module = types.ModuleType("clitestfix")
    module.solid = _solid  # type: ignore[attr-defined]
    sys.modules["clitestfix"] = module
    yield
    sys.modules.pop("clitestfix", None)


def _baseline() -> GoldenBaseline:
    return GoldenBaseline(
        id="solid",
        fixture="clitestfix:solid",
        params={},
        width=8,
        height=8,
        png_path="tests/golden/baselines/solid.png",
        tolerance=0.1,
        container_ref=_REF,
    )


def _setup(root: Path, *, commit_correct_baseline: bool) -> GoldenBaseline:
    baseline = _baseline()
    registry.write_manifest(root, [baseline])
    png = root / baseline.png_path
    png.parent.mkdir(parents=True, exist_ok=True)
    if commit_correct_baseline:
        pixelcompare.write_png(png, _solid({}))
    else:
        wrong = np.zeros((8, 8, 4), dtype=np.uint8)
        wrong[..., 3] = 255  # solid black, unlike the fixture's colour.
        pixelcompare.write_png(png, wrong)
    return baseline


def test_generate_then_compare_matches(tmp_path: Path) -> None:
    _setup(tmp_path, commit_correct_baseline=True)
    assert goldens.main(["--root", str(tmp_path), "generate", "--all"]) == 0
    assert (tmp_path / ".golden-work" / "solid.png").exists()
    assert goldens.main(["--root", str(tmp_path), "compare", "--all"]) == 0
    report = tmp_path / ".golden-work" / "solid.report.json"
    assert report.exists()


def test_generate_does_not_touch_committed_baseline(tmp_path: Path) -> None:
    baseline = _setup(tmp_path, commit_correct_baseline=True)
    before = (tmp_path / baseline.png_path).read_bytes()
    goldens.main(["--root", str(tmp_path), "generate", "--id", "solid"])
    after = (tmp_path / baseline.png_path).read_bytes()
    assert before == after


def test_compare_fails_on_material_difference(tmp_path: Path) -> None:
    _setup(tmp_path, commit_correct_baseline=False)
    goldens.main(["--root", str(tmp_path), "generate", "--all"])
    assert goldens.main(["--root", str(tmp_path), "compare", "--all"]) == 1


def test_compare_requires_candidate(tmp_path: Path) -> None:
    _setup(tmp_path, commit_correct_baseline=True)
    # No generate first -> operational error exit code 2.
    assert goldens.main(["--root", str(tmp_path), "compare", "--all"]) == 2


def test_update_refuses_without_matching_container_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = _setup(tmp_path, commit_correct_baseline=False)
    goldens.main(["--root", str(tmp_path), "generate", "--all"])
    monkeypatch.delenv(goldens.CONTAINER_REF_ENV, raising=False)
    before = (tmp_path / baseline.png_path).read_bytes()
    assert goldens.main(["--root", str(tmp_path), "update", "--all"]) == 2  # refused.
    assert (tmp_path / baseline.png_path).read_bytes() == before  # untouched.


def test_update_refuses_on_wrong_container_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, commit_correct_baseline=False)
    goldens.main(["--root", str(tmp_path), "generate", "--all"])
    monkeypatch.setenv(goldens.CONTAINER_REF_ENV, "ghcr.io/anima/anima-golden@sha256:" + "c" * 64)
    assert goldens.main(["--root", str(tmp_path), "update", "--all"]) == 2


def test_update_blesses_inside_pinned_container(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _setup(tmp_path, commit_correct_baseline=False)
    goldens.main(["--root", str(tmp_path), "generate", "--all"])
    monkeypatch.setenv(goldens.CONTAINER_REF_ENV, _REF)
    assert goldens.main(["--root", str(tmp_path), "update", "--all"]) == 0
    # Baseline now equals the fixture render; compare passes.
    assert goldens.main(["--root", str(tmp_path), "compare", "--all"]) == 0


def _two_baselines() -> list[GoldenBaseline]:
    return [
        GoldenBaseline(
            id=bid,
            fixture="clitestfix:solid",
            params={},
            width=8,
            height=8,
            png_path=f"tests/golden/baselines/{bid}.png",
            tolerance=0.1,
            container_ref=_REF,
        )
        for bid in ("solid_a", "solid_b")
    ]


def test_update_preflight_prevents_partial_bless(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baselines = _two_baselines()
    registry.write_manifest(tmp_path, baselines)
    black = np.zeros((8, 8, 4), dtype=np.uint8)
    black[..., 3] = 255
    for baseline in baselines:
        (tmp_path / baseline.png_path).parent.mkdir(parents=True, exist_ok=True)
        pixelcompare.write_png(tmp_path / baseline.png_path, black)
    # Generate a candidate for only ONE of the two selected baselines.
    goldens.main(["--root", str(tmp_path), "generate", "--id", "solid_a"])
    monkeypatch.setenv(goldens.CONTAINER_REF_ENV, _REF)
    before = {b.id: (tmp_path / b.png_path).read_bytes() for b in baselines}
    # update --all must refuse up front (solid_b has no candidate) and touch nothing.
    assert goldens.main(["--root", str(tmp_path), "update", "--all"]) == 2
    after = {b.id: (tmp_path / b.png_path).read_bytes() for b in baselines}
    assert before == after  # no partial bless of solid_a.


def test_select_requires_all_or_id(tmp_path: Path) -> None:
    _setup(tmp_path, commit_correct_baseline=True)
    # Neither --all nor --id -> operational error.
    assert goldens.main(["--root", str(tmp_path), "generate"]) == 2


def test_fmt_rewrites_manifest_canonically(tmp_path: Path) -> None:
    baseline = _baseline()
    registry.write_manifest(tmp_path, [baseline])
    # Corrupt formatting; fmt should restore canonical form.
    manifest = registry.manifest_path(tmp_path)
    manifest.write_text(manifest.read_text().replace("\n", " "))
    assert goldens.main(["--root", str(tmp_path), "fmt"]) == 0
    registry.load_manifest(tmp_path)  # loads without raising -> canonical.
