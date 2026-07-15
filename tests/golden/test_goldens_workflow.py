"""Structural assertions on the golden GitHub Actions workflows.

These workflows cannot be executed locally (no remote yet; GHCR publish is a
flagged external action). They are asserted here so their guarantees — pinned
digest, generate-then-compare, artifact upload on failure, never-bless, least
privilege, immutable tag — are locked in and cannot silently regress.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

_GOLDENS = Path(".github/workflows/goldens.yml")
_CONTAINER = Path(".github/workflows/golden-container.yml")


def test_goldens_workflow_parses() -> None:
    assert yaml.safe_load(_GOLDENS.read_text()), "goldens.yml did not parse"


def test_goldens_runs_in_pinned_digest_container() -> None:
    doc = yaml.safe_load(_GOLDENS.read_text())
    image = doc["jobs"]["goldens"]["container"]["image"]
    assert "@sha256:" in image, "golden container image must be pinned by digest"
    assert re.search(r"@sha256:[0-9a-f]{64}$", image), "digest must be 64 hex chars"


def test_goldens_generates_then_compares_and_never_updates() -> None:
    text = _GOLDENS.read_text()
    assert "goldens generate" in text
    assert "goldens compare" in text
    assert "goldens update" not in text, "CI must never bless baselines"


def test_goldens_uploads_artifacts_on_failure() -> None:
    doc = yaml.safe_load(_GOLDENS.read_text())
    steps = doc["jobs"]["goldens"]["steps"]
    upload = [s for s in steps if "upload-artifact" in str(s.get("uses", ""))]
    assert upload, "goldens.yml must upload artifacts"
    assert upload[0].get("if") == "failure()", "artifacts uploaded only on failure"


def test_goldens_least_privilege() -> None:
    doc = yaml.safe_load(_GOLDENS.read_text())
    assert doc["permissions"] == {"contents": "read"}


def test_goldens_renders_from_checked_out_source() -> None:
    # The job must reinstall the checked-out package so it does not test the
    # stale image-baked source.
    text = _GOLDENS.read_text()
    assert "pip install --no-deps --no-build-isolation -e ." in text


def test_container_publish_is_manual_only() -> None:
    # No auto-publish: golden-container.yml must NOT trigger on push (that would
    # publish to GHCR without approval). Manual workflow_dispatch only.
    doc = yaml.safe_load(_CONTAINER.read_text())
    # PyYAML parses the bare key `on` as the boolean True.
    triggers = doc[True]
    assert "workflow_dispatch" in triggers
    assert "push" not in triggers


def test_container_workflow_parses() -> None:
    assert yaml.safe_load(_CONTAINER.read_text()), "golden-container.yml did not parse"


def test_container_workflow_least_privilege_packages_write() -> None:
    doc = yaml.safe_load(_CONTAINER.read_text())
    assert doc["permissions"] == {"contents": "read", "packages": "write"}


def test_container_tags_immutable_source_revision_not_latest() -> None:
    doc = yaml.safe_load(_CONTAINER.read_text())
    text = _CONTAINER.read_text()
    assert "${{ github.sha }}" in text, "image must be tagged by immutable source revision"
    assert ":latest" not in text, "golden image must never be tagged latest"
    # Ensure a build-push step exists and pushes.
    steps = doc["jobs"]["build-and-publish"]["steps"]
    build = [s for s in steps if "build-push-action" in str(s.get("uses", ""))]
    assert build and build[0]["with"]["push"] is True


def test_container_actions_are_sha_pinned() -> None:
    text = _CONTAINER.read_text()
    for action in ("docker/login-action", "docker/build-push-action"):
        assert re.search(rf"{re.escape(action)}@[0-9a-f]{{40}} ", text), (
            f"{action} must be pinned to a full commit SHA"
        )


def test_container_resolves_and_smoke_pulls_digest() -> None:
    text = _CONTAINER.read_text()
    assert "steps.build.outputs.digest" in text, "must report the resolved digest"
    assert "docker pull" in text and "import skia" in text, "must smoke-pull digest and import skia"
