"""Shared strict validation helpers for scene-graph dataclasses."""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import TypeVar

from anima.scene_graph.errors import SceneGraphValidationError

T = TypeVar("T")


def require_identifier(value: object, *, path: str) -> str:
    """Return non-empty string identifier without modifying caller spelling."""
    if not isinstance(value, str):
        raise SceneGraphValidationError(
            code="VALUE.INVALID_STRING",
            path=path,
            message="expected string",
        )
    if has_unicode_surrogate(value):
        raise SceneGraphValidationError(
            code="VALUE.INVALID_UNICODE",
            path=path,
            message="string contains isolated UTF-16 surrogate code point",
            offending_id=value,
        )
    if not value.strip():
        raise SceneGraphValidationError(
            code="VALUE.EMPTY_IDENTIFIER",
            path=path,
            message="identifier must contain non-whitespace characters",
            offending_id=value,
        )
    return value


def require_string(value: object, *, path: str) -> str:
    """Return string value, including empty content."""
    if not isinstance(value, str):
        raise SceneGraphValidationError(
            code="VALUE.INVALID_STRING",
            path=path,
            message="expected string",
        )
    if has_unicode_surrogate(value):
        raise SceneGraphValidationError(
            code="VALUE.INVALID_UNICODE",
            path=path,
            message="string contains isolated UTF-16 surrogate code point",
        )
    return value


def has_unicode_surrogate(value: str) -> bool:
    """Return whether string contains code point UTF-8 cannot encode."""
    return any(0xD800 <= ord(character) <= 0xDFFF for character in value)


def require_integer(value: object, *, path: str) -> int:
    """Return integer while rejecting bool, Python's int subtype."""
    if type(value) is not int:
        raise SceneGraphValidationError(
            code="VALUE.INVALID_INTEGER",
            path=path,
            message="expected integer; boolean is not accepted",
        )
    return value


def require_positive_integer(value: object, *, path: str) -> int:
    result = require_integer(value, path=path)
    if result <= 0:
        raise SceneGraphValidationError(
            code="VALUE.NON_POSITIVE",
            path=path,
            message="expected integer greater than zero",
        )
    return result


def require_finite_number(value: object, *, path: str) -> float:
    """Normalize a finite int or float to float while rejecting bool."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise SceneGraphValidationError(
            code="VALUE.INVALID_NUMBER",
            path=path,
            message="expected number; boolean is not accepted",
        )
    try:
        result = float(value)
    except OverflowError as error:
        raise SceneGraphValidationError(
            code="VALUE.NOT_FINITE",
            path=path,
            message="number is outside finite floating-point range",
        ) from error
    if not math.isfinite(result):
        raise SceneGraphValidationError(
            code="VALUE.NOT_FINITE",
            path=path,
            message="expected finite number",
        )
    return result


def require_positive_number(value: object, *, path: str) -> float:
    result = require_finite_number(value, path=path)
    if result <= 0.0:
        raise SceneGraphValidationError(
            code="VALUE.NON_POSITIVE",
            path=path,
            message="expected number greater than zero",
        )
    return result


def require_instance(value: object, expected_type: type[T], *, path: str) -> T:
    if not isinstance(value, expected_type):
        raise SceneGraphValidationError(
            code="VALUE.INVALID_MODEL",
            path=path,
            message=f"expected {expected_type.__name__}",
        )
    return value


def normalize_models(
    values: Iterable[object],
    expected_type: type[T],
    *,
    path: str,
) -> tuple[T, ...]:
    """Copy ordered caller collection into tuple and validate every member."""
    if isinstance(values, str | bytes | bytearray):
        raise SceneGraphValidationError(
            code="VALUE.INVALID_COLLECTION",
            path=path,
            message="expected ordered collection",
        )
    try:
        copied = tuple(values)
    except TypeError as error:
        raise SceneGraphValidationError(
            code="VALUE.INVALID_COLLECTION",
            path=path,
            message="expected ordered collection",
        ) from error

    normalized: list[T] = []
    for index, value in enumerate(copied):
        normalized.append(require_instance(value, expected_type, path=f"{path}[{index}]"))
    return tuple(normalized)
