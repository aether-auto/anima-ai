"""Manifest-backed registry of golden baselines.

A :class:`GoldenBaseline` is the immutable description of one deterministic
render: a stable ``id``, the dotted fixture path that produces it, its canonical
parameters, the expected image dimensions, the committed PNG path, a per-pixel
``tolerance``, and the ``container_ref`` (``tag@sha256:digest``) of the pinned
golden image that is the *only* thing allowed to bless it.

The manifest is a stable-sorted JSON array at ``tests/golden/manifest.json``.
Loading it is strict: duplicate IDs, missing/orphan PNGs, non-canonical
parameter serialization, out-of-range tolerances, and manifest/image dimension
mismatches are all hard failures. Nothing is silently repaired — an agent that
reads the error can fix the manifest, which is the whole point.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from anima.testing import pixelcompare

MANIFEST_RELPATH = "tests/golden/manifest.json"
BASELINES_RELDIR = "tests/golden/baselines"
WORK_RELDIR = ".golden-work"

_TOLERANCE_MIN = 0.0
_TOLERANCE_MAX = 1.0

# A container_ref must be pinned by a full 64-hex sha256 digest (immutable), not
# a mutable tag. e.g. ghcr.io/owner/anima-golden@sha256:<64 hex>.
_DIGEST_REF_RE = re.compile(r"^\S+@sha256:[0-9a-f]{64}$")

CanonicalParams = dict[str, Any]


class ManifestError(ValueError):
    """Raised when the golden manifest is malformed or inconsistent."""


@dataclass(frozen=True)
class GoldenBaseline:
    """Immutable description of one golden baseline."""

    id: str
    fixture: str  # dotted path, e.g. "anima.testing.fixtures:trivial_shape".
    params: CanonicalParams
    width: int
    height: int
    png_path: str  # repo-relative, e.g. "tests/golden/baselines/foo.png".
    tolerance: float
    container_ref: str  # "tag@sha256:digest".

    def to_json_obj(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "fixture": self.fixture,
            "params": canonicalize_params(self.params),
            "width": self.width,
            "height": self.height,
            "png_path": self.png_path,
            "tolerance": self.tolerance,
            "container_ref": self.container_ref,
        }


def _validate_png_path(baseline_id: str, png_path: str) -> None:
    """Reject baseline PNG paths that escape ``tests/golden/baselines/``.

    The manifest is the source of truth for which files ``update`` may replace,
    so an absolute path, a ``..`` traversal, or a path outside the baselines
    directory is a hard failure — otherwise a mistyped manifest could bless an
    arbitrary file on disk.
    """
    pure = PurePosixPath(png_path)
    prefix = BASELINES_RELDIR + "/"
    if (
        pure.is_absolute()
        or ".." in pure.parts
        or not png_path.startswith(prefix)
        or pure.suffix != ".png"
        or png_path == prefix
    ):
        raise ManifestError(
            f"baseline {baseline_id!r} png_path must be a relative path of the form "
            f"{prefix}<name>.png, got {png_path!r}"
        )


def canonicalize_params(params: dict[str, Any]) -> CanonicalParams:
    """Return a canonical copy of ``params``: sorted keys, normalized floats.

    Keys are recursively sorted; integral floats collapse to ``int`` so that
    ``2.0`` and ``2`` serialize identically and never churn source control.
    """

    def norm(value: Any) -> Any:
        if isinstance(value, bool):
            return value
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ManifestError(f"non-finite float in params: {value!r}")
            if value.is_integer():
                return int(value)
            return value
        if isinstance(value, dict):
            return {key: norm(value[key]) for key in sorted(value)}
        if isinstance(value, list | tuple):
            return [norm(item) for item in value]
        return value

    result = norm(dict(params))
    assert isinstance(result, dict)
    return result


def _canonical_dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def baseline_from_json(obj: dict[str, Any]) -> GoldenBaseline:
    required = (
        "id",
        "fixture",
        "params",
        "width",
        "height",
        "png_path",
        "tolerance",
        "container_ref",
    )
    missing = [key for key in required if key not in obj]
    if missing:
        raise ManifestError(f"baseline is missing fields: {', '.join(missing)}")
    if not isinstance(obj["params"], dict):
        raise ManifestError(f"baseline {obj['id']!r} params must be an object")
    tolerance = float(obj["tolerance"])
    if not _TOLERANCE_MIN <= tolerance <= _TOLERANCE_MAX:
        raise ManifestError(
            f"baseline {obj['id']!r} tolerance {tolerance} outside "
            f"[{_TOLERANCE_MIN}, {_TOLERANCE_MAX}]"
        )
    for dim in ("width", "height"):
        if not isinstance(obj[dim], int) or obj[dim] <= 0:
            raise ManifestError(f"baseline {obj['id']!r} {dim} must be a positive int")
    if not _DIGEST_REF_RE.match(str(obj["container_ref"])):
        raise ManifestError(
            f"baseline {obj['id']!r} container_ref must be pinned by a full digest "
            "(ref@sha256:<64 hex>), not a mutable tag or truncated digest"
        )
    if ":" not in str(obj["fixture"]):
        raise ManifestError(
            f"baseline {obj['id']!r} fixture must be a dotted path 'module:callable'"
        )
    _validate_png_path(str(obj["id"]), str(obj["png_path"]))
    return GoldenBaseline(
        id=str(obj["id"]),
        fixture=str(obj["fixture"]),
        params=canonicalize_params(obj["params"]),
        width=int(obj["width"]),
        height=int(obj["height"]),
        png_path=str(obj["png_path"]),
        tolerance=tolerance,
        container_ref=str(obj["container_ref"]),
    )


def manifest_path(root: Path) -> Path:
    return root / MANIFEST_RELPATH


def baselines_dir(root: Path) -> Path:
    return root / BASELINES_RELDIR


def work_dir(root: Path) -> Path:
    return root / WORK_RELDIR


def parse_manifest(root: Path) -> list[GoldenBaseline]:
    """Parse and structurally validate the manifest without the canonical check.

    Validates required fields and rejects duplicate IDs, but does not require the
    on-disk serialization to already be canonical (that is what ``fmt`` fixes).
    """
    path = manifest_path(root)
    if not path.exists():
        raise ManifestError(f"manifest not found: {path}")
    raw = json.loads(path.read_text())
    if not isinstance(raw, list):
        raise ManifestError("manifest must be a JSON array of baselines")

    baselines: list[GoldenBaseline] = []
    seen: set[str] = set()
    for obj in raw:
        baseline = baseline_from_json(obj)
        if baseline.id in seen:
            raise ManifestError(f"duplicate baseline id: {baseline.id!r}")
        seen.add(baseline.id)
        baselines.append(baseline)
    return baselines


def load_manifest(root: Path) -> list[GoldenBaseline]:
    """Load the manifest and require it to already be in canonical form.

    Structural validation (duplicate IDs, field checks) plus a rejection of
    non-canonical on-disk serialization so source-control diffs stay stable.
    Does not touch PNG files; call :func:`validate` for the image-aware check.
    """
    baselines = parse_manifest(root)
    canonical = dump_manifest_text(baselines)
    if _normalize_text(manifest_path(root).read_text()) != _normalize_text(canonical):
        raise ManifestError(
            f"manifest {manifest_path(root)} is not in canonical form; run "
            "'python -m anima.testing.goldens fmt' or regenerate it"
        )
    return baselines


def get(baselines: list[GoldenBaseline], baseline_id: str) -> GoldenBaseline:
    for baseline in baselines:
        if baseline.id == baseline_id:
            return baseline
    raise ManifestError(f"unknown baseline id: {baseline_id!r}")


def dump_manifest_text(baselines: list[GoldenBaseline]) -> str:
    ordered = sorted(baselines, key=lambda b: b.id)
    body = [b.to_json_obj() for b in ordered]
    return json.dumps(body, indent=2, sort_keys=True) + "\n"


def write_manifest(root: Path, baselines: list[GoldenBaseline]) -> None:
    path = manifest_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_manifest_text(baselines))


def _normalize_text(text: str) -> str:
    # Compare structure, not incidental whitespace, when checking canonical form.
    return _canonical_dumps(json.loads(text))


def validate(root: Path, *, check_images: bool = True) -> list[GoldenBaseline]:
    """Full validation: structure plus image existence and dimension match.

    Raises :class:`ManifestError` for missing PNGs, orphan PNGs in the
    baselines directory, or manifest dimensions that disagree with the actual
    committed image.
    """
    baselines = load_manifest(root)
    referenced: set[Path] = set()
    for baseline in baselines:
        png = root / baseline.png_path
        referenced.add(png.resolve())
        if not png.exists():
            raise ManifestError(f"baseline {baseline.id!r} PNG missing: {png}")
        if check_images:
            image = pixelcompare.read_png(png)
            actual_h, actual_w = image.shape[0], image.shape[1]
            if (actual_w, actual_h) != (baseline.width, baseline.height):
                raise ManifestError(
                    f"baseline {baseline.id!r} dimension mismatch: manifest "
                    f"{baseline.width}x{baseline.height} != image {actual_w}x{actual_h}"
                )

    bdir = baselines_dir(root)
    if bdir.exists():
        for png in bdir.glob("*.png"):
            if png.resolve() not in referenced:
                raise ManifestError(f"orphan baseline PNG not in manifest: {png}")
    return baselines
