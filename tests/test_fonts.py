from __future__ import annotations

import hashlib
import importlib.resources as resources
import json
import subprocess
import sys
from pathlib import Path

import pytest
from fontTools.ttLib import TTFont

FONTS_DIR = Path("src/anima/assets/fonts")
MANIFEST_PATH = FONTS_DIR / "manifest.json"
ATTRIBUTION_PATH = FONTS_DIR / "ATTRIBUTION.md"
ALLOWED_LICENSES = {"OFL-1.1", "Apache-2.0", "MIT", "CC0-1.0", "Unlicense"}
REQUIRED_ROLES = {
    ("crude", "display"),
    ("crude", "body"),
    ("flat", "display"),
    ("flat", "body"),
}
REQUIRED_FIELDS = {
    "pack",
    "role",
    "family",
    "weight",
    "style",
    "filename",
    "version",
    "sha256",
    "license_spdx",
    "license_file",
    "copyright_holder",
    "source_url",
}
NARRATION_CODEPOINTS = set(range(0x20, 0x7F)) | {
    0x2018,
    0x2019,
    0x201C,
    0x201D,
    0x2013,
    0x2014,
    0x2026,
}


def _manifest() -> list[dict[str, object]]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_has_vetted_roles_and_metadata() -> None:
    manifest = _manifest()

    assert len(manifest) == 4
    assert {(entry["pack"], entry["role"]) for entry in manifest} == REQUIRED_ROLES
    assert all(REQUIRED_FIELDS <= entry.keys() for entry in manifest)
    assert all(entry["license_spdx"] in ALLOWED_LICENSES for entry in manifest)
    assert all(
        isinstance(entry["source_url"], str) and entry["source_url"].startswith("https://")
        for entry in manifest
    )
    assert all(".." not in Path(str(entry["filename"])).parts for entry in manifest)


@pytest.mark.parametrize(
    "entry", _manifest() if MANIFEST_PATH.exists() else [], ids=lambda entry: str(entry["filename"])
)
def test_manifest_checksum_matches_bundled_file(entry: dict[str, object]) -> None:
    font_path = FONTS_DIR / str(entry["filename"])

    digest = hashlib.sha256(font_path.read_bytes()).hexdigest()

    assert digest == entry["sha256"]


@pytest.mark.parametrize(
    "entry", _manifest() if MANIFEST_PATH.exists() else [], ids=lambda entry: str(entry["filename"])
)
def test_manifest_license_text_is_bundled(entry: dict[str, object]) -> None:
    license_path = FONTS_DIR / str(entry["license_file"])

    text = license_path.read_text(encoding="utf-8")

    assert "SIL OPEN FONT LICENSE Version 1.1" in text
    assert str(entry["copyright_holder"]) in text.splitlines()[0]


@pytest.mark.parametrize(
    "entry", _manifest() if MANIFEST_PATH.exists() else [], ids=lambda entry: str(entry["filename"])
)
def test_font_loads(entry: dict[str, object]) -> None:
    font_path = FONTS_DIR / str(entry["filename"])

    with TTFont(font_path) as font:
        assert font["name"].names
        assert font["OS/2"].usWeightClass == entry["weight"]


@pytest.mark.parametrize(
    "entry", _manifest() if MANIFEST_PATH.exists() else [], ids=lambda entry: str(entry["filename"])
)
def test_glyph_coverage(entry: dict[str, object]) -> None:
    font_path = FONTS_DIR / str(entry["filename"])

    with TTFont(font_path) as font:
        covered = set(font.getBestCmap())

    assert NARRATION_CODEPOINTS <= covered


def test_attribution_is_generated_and_package_retrievable() -> None:
    result = subprocess.run(
        [sys.executable, "tools/generate_font_attribution.py", "--check"],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert resources.files("anima").joinpath("assets/fonts/ATTRIBUTION.md").read_text(
        encoding="utf-8"
    ) == (ATTRIBUTION_PATH.read_text(encoding="utf-8"))


def test_anima_source_does_not_resolve_os_fonts() -> None:
    forbidden = ("fc-match", "fontconfig", "/System/Library/Fonts", "Windows\\\\Fonts")
    source = "\n".join(path.read_text(encoding="utf-8") for path in Path("src/anima").rglob("*.py"))

    assert not any(token in source for token in forbidden)
