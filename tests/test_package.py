from __future__ import annotations

import importlib
from pathlib import Path


def test_package_import_exposes_development_version() -> None:
    anima = importlib.import_module("anima")

    assert anima.__version__ == "0.0.0.dev0"


def test_build_requirements_include_license_expression_support() -> None:
    pyproject = Path("pyproject.toml").read_text()

    assert 'requires = ["packaging>=24.2", "setuptools>=77"]' in pyproject
