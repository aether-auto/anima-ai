"""Committed golden fixtures: deterministic direct-Skia renders.

Each fixture is a pure function ``(params) -> (H, W, 4) uint8 RGBA`` array. It
must render identically on every run inside the pinned golden container: fixed
canvas size, fixed anti-aliasing, no text (font rasterization is not yet pinned,
so text is deliberately excluded from Phase 0 fixtures), no time or randomness.

``skia`` is imported lazily at call time so the registry and comparator import
cleanly in environments without the heavy renderer installed.
"""

from __future__ import annotations

from typing import Any

from anima.testing import pixelcompare
from anima.testing.pixelcompare import RGBA


def trivial_shape(params: dict[str, Any] | None = None) -> RGBA:
    """Render a fixed 256x256 text-free shape: a filled square and stroked ring.

    Deterministic by construction: constant canvas, constant colours, constant
    geometry, anti-aliasing on. ``params`` is accepted for signature uniformity
    with parameterised fixtures but is unused here.
    """
    del params  # trivial fixture takes no parameters.

    import skia  # type: ignore[import-not-found]

    width = height = 256
    surface = skia.Surface(width, height)
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorSetARGB(255, 245, 245, 245))

    fill = skia.Paint(
        Color=skia.ColorSetARGB(255, 40, 90, 200),
        AntiAlias=True,
        Style=skia.Paint.kFill_Style,
    )
    canvas.drawRect(skia.Rect.MakeXYWH(48, 48, 96, 96), fill)

    ring = skia.Paint(
        Color=skia.ColorSetARGB(255, 210, 60, 60),
        AntiAlias=True,
        Style=skia.Paint.kStroke_Style,
        StrokeWidth=10.0,
    )
    canvas.drawCircle(168, 168, 56, ring)

    image = surface.makeImageSnapshot()
    png = image.encodeToData()
    if png is None:  # pragma: no cover - skia always encodes a raster snapshot.
        raise RuntimeError("skia failed to encode the trivial_shape fixture")
    return pixelcompare.decode_png(bytes(png))
