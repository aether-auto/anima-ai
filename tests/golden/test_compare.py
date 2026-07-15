"""Tests for the pure-numpy PNG comparator (no skia required)."""

from __future__ import annotations

import numpy as np
import pytest

from anima.testing import pixelcompare
from anima.testing.pixelcompare import RGBA


def _rgba(height: int, width: int, color: tuple[int, int, int, int]) -> RGBA:
    arr = np.empty((height, width, 4), dtype=np.uint8)
    arr[..., :] = color
    return arr


def _hard_edge(width: int, height: int, split: int) -> RGBA:
    """White image with a black column block starting at ``split`` (hard edge)."""
    arr = _rgba(height, width, (255, 255, 255, 255))
    arr[:, split : split + 8, :3] = 0
    return arr


def _aa_seam(width: int, height: int, seam: int) -> RGBA:
    """White|black vertical edge with a one-column gray anti-aliasing seam.

    Columns left of ``seam`` are white, ``seam`` is mid-gray (the anti-aliased
    transition), columns right of ``seam`` are black.
    """
    arr = _rgba(height, width, (255, 255, 255, 255))
    arr[:, seam, :3] = 128
    arr[:, seam + 1 :, :3] = 0
    return arr


def test_png_roundtrip_is_byte_stable() -> None:
    image = _hard_edge(24, 24, 6)
    encoded_once = pixelcompare.encode_png(image)
    encoded_twice = pixelcompare.encode_png(image)
    assert encoded_once == encoded_twice  # deterministic encoder.
    decoded = pixelcompare.decode_png(encoded_once)
    assert np.array_equal(decoded, image)


def test_identical_images_have_zero_diff() -> None:
    image = _hard_edge(32, 32, 10)
    result = pixelcompare.compare(image, image.copy())
    assert result.diff_pixels == 0
    assert result.aa_pixels == 0
    assert result.diff_ratio == 0.0
    assert result.acceptable is True
    assert result.metrics["width"] == 32
    assert result.metrics["height"] == 32


def test_dimension_mismatch_raises() -> None:
    a = _rgba(10, 10, (0, 0, 0, 255))
    b = _rgba(10, 12, (0, 0, 0, 255))
    with pytest.raises(pixelcompare.DimensionMismatch):
        pixelcompare.compare(a, b)


def test_material_change_in_flat_region_counts_as_diff() -> None:
    baseline = _rgba(40, 40, (255, 255, 255, 255))
    candidate = baseline.copy()
    # Recolor a solid interior block far from any edge -> a real, non-AA change.
    candidate[16:24, 16:24, :3] = (0, 0, 0)
    result = pixelcompare.compare(baseline, candidate)
    assert result.diff_pixels == 64  # 8x8 block.
    assert result.acceptable is False
    assert result.diff_ratio == pytest.approx(64 / 1600)


def test_antialiased_edge_shift_is_excluded_by_default() -> None:
    # A one-column shift of an anti-aliased seam changes only midtone edge
    # pixels; the AA detector should classify them as anti-aliasing.
    baseline = _aa_seam(40, 40, 19)
    candidate = _aa_seam(40, 40, 20)
    result = pixelcompare.compare(baseline, candidate)
    assert result.aa_pixels > 0
    assert result.diff_pixels == 0
    assert result.acceptable is True

    # With include_aa=True the same pixels now count as differences.
    included = pixelcompare.compare(baseline, candidate, include_aa=True)
    assert included.diff_pixels > 0
    assert included.acceptable is False


def test_threshold_controls_sensitivity() -> None:
    baseline = _rgba(20, 20, (120, 120, 120, 255))
    candidate = baseline.copy()
    candidate[5:15, 5:15, :3] = (128, 128, 128)  # small luminance nudge.
    strict = pixelcompare.compare(baseline, candidate, threshold=0.0)
    lenient = pixelcompare.compare(baseline, candidate, threshold=0.5)
    assert strict.diff_pixels > lenient.diff_pixels


def test_diff_image_marks_changed_pixels_red() -> None:
    baseline = _rgba(30, 30, (255, 255, 255, 255))
    candidate = baseline.copy()
    candidate[12:18, 12:18, :3] = (0, 0, 0)
    result = pixelcompare.compare(baseline, candidate)
    assert tuple(result.diff_image[15, 15, :3]) == (255, 0, 0)
    assert result.diff_image.shape == (30, 30, 4)
