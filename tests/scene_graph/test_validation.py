from __future__ import annotations

import math

import pytest

from anima.scene_graph import (
    Circle,
    Ellipse,
    Project,
    Rectangle,
    Resolution,
    SceneGraphValidationError,
    StylePackRef,
    Text,
    Vector2,
    VisibilityWindow,
)


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_resolution_rejects_non_positive_boolean_and_non_integer_width(value: object) -> None:
    with pytest.raises(SceneGraphValidationError) as caught:
        Resolution(width=value, height=1080)  # type: ignore[arg-type]

    assert caught.value.code in {"VALUE.INVALID_INTEGER", "VALUE.NON_POSITIVE"}
    assert caught.value.path == "$.resolution.width"


@pytest.mark.parametrize("value", [True, math.nan, math.inf, -math.inf])
def test_vectors_reject_boolean_and_non_finite_coordinates(value: object) -> None:
    with pytest.raises(SceneGraphValidationError) as caught:
        Vector2(x=value, y=0.0)  # type: ignore[arg-type]

    assert caught.value.code in {"VALUE.INVALID_NUMBER", "VALUE.NOT_FINITE"}
    assert caught.value.path == "$.vector.x"


def test_vectors_convert_huge_integer_overflow_into_structured_error() -> None:
    with pytest.raises(SceneGraphValidationError) as caught:
        Vector2(x=10**10_000, y=0.0)

    assert caught.value.code == "VALUE.NOT_FINITE"
    assert caught.value.path == "$.vector.x"


@pytest.mark.parametrize(
    ("factory", "path"),
    [
        (lambda: Rectangle(width=0.0, height=1.0), "$.rectangle.width"),
        (lambda: Circle(radius=-1.0), "$.circle.radius"),
        (lambda: Ellipse(radius_x=1.0, radius_y=math.inf), "$.ellipse.radius_y"),
    ],
)
def test_geometry_dimensions_must_be_positive_and_finite(
    factory: object,
    path: str,
) -> None:
    callable_factory = factory
    with pytest.raises(SceneGraphValidationError) as caught:
        callable_factory()  # type: ignore[operator]

    assert caught.value.path == path


@pytest.mark.parametrize("identifier", ["", " ", "\t\n"])
def test_identifiers_reject_empty_or_whitespace_only_values(identifier: str) -> None:
    with pytest.raises(SceneGraphValidationError) as caught:
        StylePackRef(id=identifier, version="1.0.0")

    assert caught.value.code == "VALUE.EMPTY_IDENTIFIER"
    assert caught.value.offending_id == identifier
    assert caught.value.path == "$.style_pack.id"


def test_visibility_rejects_negative_and_reversed_intervals() -> None:
    with pytest.raises(SceneGraphValidationError) as negative:
        VisibilityWindow(start=-0.1)
    assert negative.value.code == "VISIBILITY.NEGATIVE_BOUNDARY"
    assert negative.value.path == "$.visibility.start"

    with pytest.raises(SceneGraphValidationError) as reversed_interval:
        VisibilityWindow(start=2.0, end=1.0)
    assert reversed_interval.value.code == "VISIBILITY.REVERSED_INTERVAL"
    assert reversed_interval.value.path == "$.visibility"


@pytest.mark.parametrize(
    ("field", "value", "expected_path"),
    [
        ("fps", 0, "$.project.fps"),
        ("fps", True, "$.project.fps"),
        ("fps", math.nan, "$.project.fps"),
        ("wpm", -1, "$.project.wpm"),
        ("wpm", math.inf, "$.project.wpm"),
        ("seed", True, "$.project.seed"),
    ],
)
def test_project_numeric_settings_are_strict(
    field: str,
    value: object,
    expected_path: str,
) -> None:
    kwargs: dict[str, object] = {
        "style_pack": StylePackRef(id="crude", version="1.0.0"),
        field: value,
    }
    with pytest.raises(SceneGraphValidationError) as caught:
        Project(**kwargs)  # type: ignore[arg-type]

    assert caught.value.path == expected_path


def test_text_rejects_empty_font_role_and_non_positive_size() -> None:
    with pytest.raises(SceneGraphValidationError) as empty_role:
        Text(id="title", layer="labels", content="Hello", font_role="", size=24.0)
    assert empty_role.value.path == "$.text.font_role"

    with pytest.raises(SceneGraphValidationError) as bad_size:
        Text(id="title", layer="labels", content="Hello", font_role="heading", size=0.0)
    assert bad_size.value.path == "$.text.size"
    assert bad_size.value.offending_id == "title"


def test_node_local_common_field_errors_carry_stable_node_id() -> None:
    with pytest.raises(SceneGraphValidationError) as caught:
        Text(
            id="title",
            layer="labels",
            content="Hello",
            font_role="heading",
            size=24.0,
            z=True,  # type: ignore[arg-type]
        )

    assert caught.value.code == "VALUE.INVALID_INTEGER"
    assert caught.value.offending_id == "title"
    assert caught.value.path == "$.node.z"


def test_model_rejects_isolated_unicode_surrogates() -> None:
    with pytest.raises(SceneGraphValidationError) as caught:
        Text(
            id="title",
            layer="labels",
            content="\ud800",
            font_role="heading",
            size=24.0,
        )

    assert caught.value.code == "VALUE.INVALID_UNICODE"
    assert caught.value.offending_id == "title"
    assert caught.value.path == "$.text.content"


def test_error_string_includes_machine_fields() -> None:
    with pytest.raises(SceneGraphValidationError) as caught:
        StylePackRef(id="", version="1.0.0")

    message = str(caught.value)
    assert "VALUE.EMPTY_IDENTIFIER" in message
    assert "$.style_pack.id" in message
