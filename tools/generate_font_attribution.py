from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FONTS_DIR = ROOT / "src/anima/assets/fonts"
MANIFEST_PATH = FONTS_DIR / "manifest.json"
ATTRIBUTION_PATH = FONTS_DIR / "ATTRIBUTION.md"
LICENSE_NAMES = {
    "Apache-2.0": "Apache License 2.0",
    "CC0-1.0": "Creative Commons Zero v1.0 Universal",
    "MIT": "MIT License",
    "OFL-1.1": "SIL Open Font License 1.1",
    "Unlicense": "The Unlicense",
}


def render_attribution(entries: list[dict[str, object]]) -> str:
    lines = ["# Font attribution", "", "Generated from `manifest.json`. Do not edit manually.", ""]
    for entry in sorted(entries, key=lambda item: (str(item["pack"]), str(item["role"]))):
        license_spdx = str(entry["license_spdx"])
        lines.extend(
            [
                f"## {entry['family']} — {entry['weight']} {entry['style']}",
                "",
                f"- Pack: `{entry['pack']}`",
                f"- Role: `{entry['role']}`",
                f"- File: `{entry['filename']}`",
                f"- Version: {entry['version']}",
                f"- SHA-256: `{entry['sha256']}`",
                f"- License: {LICENSE_NAMES[license_spdx]} (`{license_spdx}`)",
                f"- License file: `{entry['license_file']}`",
                f"- Copyright: {entry['copyright_holder']}",
                f"- Source: {entry['source_url']}",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    attribution = render_attribution(manifest)

    if args.check:
        if (
            ATTRIBUTION_PATH.exists()
            and ATTRIBUTION_PATH.read_text(encoding="utf-8") == attribution
        ):
            return 0
        print("ATTRIBUTION.md stale. Run tools/generate_font_attribution.py.")
        return 1

    ATTRIBUTION_PATH.write_text(attribution, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
