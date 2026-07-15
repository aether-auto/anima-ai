"""Deterministic pure-numpy PNG I/O and a YIQ perceptual image comparator.

No skia dependency: the comparator decodes PNGs itself (zlib + struct) into
``(H, W, 4)`` uint8 RGBA arrays, so it runs anywhere numpy is importable. The
perceptual distance and anti-aliased-edge exclusion are a faithful port of the
``pixelmatch`` algorithm (Mapbox), which uses the YIQ colour space so that
sub-pixel anti-aliasing differences can be told apart from material changes.

The encoder writes a minimal, deterministic RGBA PNG (single ``IDAT``, filter
type 0, fixed zlib level) so diff artifacts and any host-side round-trips are
byte-stable. Canonical baselines are still produced only inside the pinned
container; this module never blesses anything, it only measures.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

RGBA = npt.NDArray[np.uint8]

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_ZLIB_LEVEL = 9

# pixelmatch tuning constants.
_MAX_YIQ_DELTA = 35215.0  # maximum possible YIQ difference between two colours.
_DEFAULT_THRESHOLD = 0.1

_DIFF_COLOR = np.array([255, 0, 0], dtype=np.uint8)  # material change -> red.
_AA_COLOR = np.array([255, 255, 0], dtype=np.uint8)  # anti-aliased edge -> yellow.


class PngError(ValueError):
    """Raised when a byte stream is not a PNG this decoder supports."""


class DimensionMismatch(ValueError):
    """Raised when two images being compared have different dimensions."""


@dataclass(frozen=True)
class CompareResult:
    """Outcome of comparing a candidate image against a baseline.

    ``acceptable`` is the golden pass/fail signal: a candidate passes only when
    zero pixels differ beyond the per-pixel ``threshold`` after anti-aliased
    edges are excluded. ``metrics`` is a JSON-serializable summary.
    """

    width: int
    height: int
    threshold: float
    include_aa: bool
    diff_pixels: int
    aa_pixels: int
    diff_ratio: float
    diff_image: RGBA

    @property
    def acceptable(self) -> bool:
        return self.diff_pixels == 0

    @property
    def metrics(self) -> dict[str, object]:
        return {
            "width": self.width,
            "height": self.height,
            "threshold": self.threshold,
            "include_aa": self.include_aa,
            "diff_pixels": self.diff_pixels,
            "aa_pixels": self.aa_pixels,
            "diff_ratio": self.diff_ratio,
            "acceptable": self.acceptable,
        }


# --------------------------------------------------------------------------- #
# PNG decoding                                                                 #
# --------------------------------------------------------------------------- #


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def decode_png(data: bytes) -> RGBA:
    """Decode 8-bit RGB/RGBA PNG bytes into an ``(H, W, 4)`` uint8 array.

    Supports colour types 2 (RGB) and 6 (RGBA) at bit depth 8, non-interlaced,
    with all five scanline filters. This is exactly the surface skia's PNG
    encoder emits; anything else raises :class:`PngError`.
    """
    if data[:8] != _PNG_SIGNATURE:
        raise PngError("missing PNG signature")

    pos = 8
    width = height = bit_depth = color_type = interlace = -1
    idat = bytearray()
    saw_ihdr = False
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        ctype = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        pos += 12 + length  # 4 length + 4 type + body + 4 CRC.
        if ctype == b"IHDR":
            width, height, bit_depth, color_type, _comp, _filt, interlace = struct.unpack(
                ">IIBBBBB", body
            )
            saw_ihdr = True
        elif ctype == b"IDAT":
            idat += body
        elif ctype == b"IEND":
            break

    if not saw_ihdr:
        raise PngError("missing IHDR chunk")
    if bit_depth != 8:
        raise PngError(f"unsupported bit depth {bit_depth}; only 8 is supported")
    if interlace != 0:
        raise PngError("interlaced PNGs are not supported")
    if color_type == 6:
        channels = 4
    elif color_type == 2:
        channels = 3
    else:
        raise PngError(f"unsupported colour type {color_type}; only 2 (RGB) and 6 (RGBA)")

    raw = zlib.decompress(bytes(idat))
    stride = width * channels
    expected = (stride + 1) * height
    if len(raw) != expected:
        raise PngError(f"decompressed size {len(raw)} != expected {expected}")

    out = np.empty((height, width, channels), dtype=np.uint8)
    prev = bytearray(stride)
    idx = 0
    for row in range(height):
        filter_type = raw[idx]
        idx += 1
        line = bytearray(raw[idx : idx + stride])
        idx += stride
        if filter_type == 0:
            pass
        elif filter_type == 1:  # Sub
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif filter_type == 2:  # Up
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif filter_type == 3:  # Average
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif filter_type == 4:  # Paeth
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                upleft = prev[i - channels] if i >= channels else 0
                line[i] = (line[i] + _paeth(left, prev[i], upleft)) & 0xFF
        else:
            raise PngError(f"unsupported scanline filter {filter_type}")
        out[row] = np.frombuffer(bytes(line), dtype=np.uint8).reshape(width, channels)
        prev = line

    if channels == 3:
        rgba = np.empty((height, width, 4), dtype=np.uint8)
        rgba[..., :3] = out
        rgba[..., 3] = 255
        return rgba
    return out


def read_png(path: str | Path) -> RGBA:
    """Read a PNG file into an ``(H, W, 4)`` uint8 RGBA array."""
    return decode_png(Path(path).read_bytes())


# --------------------------------------------------------------------------- #
# PNG encoding                                                                 #
# --------------------------------------------------------------------------- #


def encode_png(image: RGBA) -> bytes:
    """Encode an ``(H, W, 4)`` uint8 RGBA array into deterministic PNG bytes."""
    if image.ndim != 3 or image.shape[2] != 4:
        raise ValueError("expected an (H, W, 4) RGBA array")
    arr = np.ascontiguousarray(image, dtype=np.uint8)
    height, width = arr.shape[0], arr.shape[1]

    def chunk(tag: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + tag
            + body
            + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    # Filter type 0 (None) prepended to every scanline for a stable byte stream.
    stride = width * 4
    raw = bytearray((stride + 1) * height)
    flat = arr.reshape(height, stride)
    for row in range(height):
        base = row * (stride + 1)
        raw[base] = 0
        raw[base + 1 : base + 1 + stride] = flat[row].tobytes()
    idat = zlib.compress(bytes(raw), _ZLIB_LEVEL)
    return _PNG_SIGNATURE + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def write_png(path: str | Path, image: RGBA) -> None:
    """Write an ``(H, W, 4)`` uint8 RGBA array to ``path`` as deterministic PNG."""
    Path(path).write_bytes(encode_png(image))


# --------------------------------------------------------------------------- #
# YIQ perceptual comparison (pixelmatch port)                                  #
# --------------------------------------------------------------------------- #


def _blend_channel(channel: npt.NDArray[np.float64], alpha: npt.NDArray[np.float64]) -> (
    npt.NDArray[np.float64]
):
    # Blend a colour channel against a white background by its alpha.
    return 255.0 + (channel - 255.0) * alpha


def _to_yiq(image: RGBA) -> tuple[
    npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]
]:
    f = image.astype(np.float64)
    alpha = f[..., 3] / 255.0
    r = _blend_channel(f[..., 0], alpha)
    g = _blend_channel(f[..., 1], alpha)
    b = _blend_channel(f[..., 2], alpha)
    y = r * 0.29889531 + g * 0.58662247 + b * 0.11448223
    i = r * 0.59597799 - g * 0.27417610 - b * 0.32180189
    q = r * 0.21147017 - g * 0.52261711 + b * 0.31114694
    return y, i, q


def _color_delta_field(
    a: RGBA, b: RGBA
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    """Signed YIQ delta per pixel plus both luminance fields (vectorised)."""
    ya, ia, qa = _to_yiq(a)
    yb, ib, qb = _to_yiq(b)
    dy = ya - yb
    di = ia - ib
    dq = qa - qb
    magnitude = 0.5053 * dy * dy + 0.299 * di * di + 0.1957 * dq * dq
    signed = np.where(ya > yb, -magnitude, magnitude)
    return signed, ya, yb


def _luminance(image: RGBA) -> npt.NDArray[np.float64]:
    y, _i, _q = _to_yiq(image)
    return y


def _delta_y(lum: npt.NDArray[np.float64], y0: int, x0: int, y1: int, x1: int) -> float:
    return float(lum[y0, x0] - lum[y1, x1])


def _has_many_siblings(image: RGBA, x: int, y: int, width: int, height: int) -> bool:
    x0 = max(x - 1, 0)
    y0 = max(y - 1, 0)
    x2 = min(x + 1, width - 1)
    y2 = min(y + 1, height - 1)
    zeroes = 1 if (x == x0 or x == x2 or y == y0 or y == y2) else 0
    center = image[y, x]
    for cx in range(x0, x2 + 1):
        for cy in range(y0, y2 + 1):
            if cx == x and cy == y:
                continue
            if bool(np.array_equal(image[cy, cx], center)):
                zeroes += 1
                if zeroes > 2:
                    return True
    return False


def _antialiased(
    image: RGBA,
    other: RGBA,
    x: int,
    y: int,
    width: int,
    height: int,
    lum: npt.NDArray[np.float64],
) -> bool:
    x0 = max(x - 1, 0)
    y0 = max(y - 1, 0)
    x2 = min(x + 1, width - 1)
    y2 = min(y + 1, height - 1)
    zeroes = 1 if (x == x0 or x == x2 or y == y0 or y == y2) else 0
    minv = 0.0
    maxv = 0.0
    min_x = min_y = max_x = max_y = -1
    for cx in range(x0, x2 + 1):
        for cy in range(y0, y2 + 1):
            if cx == x and cy == y:
                continue
            delta = _delta_y(lum, y, x, cy, cx)
            if delta == 0.0:
                zeroes += 1
                if zeroes > 2:
                    return False
            elif delta < minv:
                minv = delta
                min_x, min_y = cx, cy
            elif delta > maxv:
                maxv = delta
                max_x, max_y = cx, cy
    if minv == 0.0 or maxv == 0.0:
        return False
    return (
        _has_many_siblings(image, min_x, min_y, width, height)
        and _has_many_siblings(other, min_x, min_y, width, height)
    ) or (
        _has_many_siblings(image, max_x, max_y, width, height)
        and _has_many_siblings(other, max_x, max_y, width, height)
    )


def compare(
    baseline: RGBA,
    candidate: RGBA,
    *,
    threshold: float = _DEFAULT_THRESHOLD,
    include_aa: bool = False,
) -> CompareResult:
    """Compare ``candidate`` against ``baseline`` with YIQ perceptual distance.

    Raises :class:`DimensionMismatch` if the two images differ in size (strict:
    a golden that changed dimensions is always a failure, never a resize).
    Pixels whose YIQ distance exceeds ``threshold`` are counted as differences,
    except anti-aliased edges (unless ``include_aa`` is set), which are excluded
    and reported separately in ``aa_pixels``.
    """
    if baseline.shape != candidate.shape:
        raise DimensionMismatch(
            f"baseline {baseline.shape[1]}x{baseline.shape[0]} != "
            f"candidate {candidate.shape[1]}x{candidate.shape[0]}"
        )
    height, width = baseline.shape[0], baseline.shape[1]

    signed, ya, _yb = _color_delta_field(baseline, candidate)
    max_delta = _MAX_YIQ_DELTA * threshold * threshold
    candidates = np.abs(signed) > max_delta

    # Faded grayscale background from the baseline luminance (pixelmatch look).
    gray = (255.0 - (255.0 - ya) * 0.1).clip(0, 255).astype(np.uint8)
    diff_image = np.empty((height, width, 4), dtype=np.uint8)
    diff_image[..., 0] = gray
    diff_image[..., 1] = gray
    diff_image[..., 2] = gray
    diff_image[..., 3] = 255

    lum_base = _luminance(baseline)
    lum_cand = _luminance(candidate)

    diff_pixels = 0
    aa_pixels = 0
    ys, xs = np.nonzero(candidates)
    for y, x in zip(ys.tolist(), xs.tolist(), strict=True):
        is_aa = not include_aa and (
            _antialiased(baseline, candidate, x, y, width, height, lum_base)
            or _antialiased(candidate, baseline, x, y, width, height, lum_cand)
        )
        if is_aa:
            aa_pixels += 1
            diff_image[y, x, :3] = _AA_COLOR
        else:
            diff_pixels += 1
            diff_image[y, x, :3] = _DIFF_COLOR

    return CompareResult(
        width=width,
        height=height,
        threshold=threshold,
        include_aa=include_aa,
        diff_pixels=diff_pixels,
        aa_pixels=aa_pixels,
        diff_ratio=diff_pixels / float(width * height),
        diff_image=diff_image,
    )
