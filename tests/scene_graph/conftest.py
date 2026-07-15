from __future__ import annotations

import pytest
from anima.scene_graph import (
    Circle,
    ClosePath,
    CubicTo,
    Ellipse,
    Group,
    Layer,
    LineTo,
    MoveTo,
    Path,
    Polygon,
    Project,
    Rectangle,
    Resolution,
    Scene,
    Shape,
    StylePackRef,
    Text,
    Transform,
    Vector2,
    VisibilityWindow,
)


@pytest.fixture
def representative_project() -> Project:
    background = Shape(
        id="background",
        layer="art",
        z=-10,
        style_role="canvas",
        geometry=Rectangle(width=1920.0, height=1080.0),
    )
    sun = Shape(
        id="sun",
        layer="art",
        z=0,
        geometry=Circle(radius=96.0),
        transform=Transform(
            position=Vector2(x=1500.0, y=160.0),
            rotation=12.5,
            scale=Vector2(x=1.1, y=0.9),
            anchor=Vector2(x=0.5, y=0.5),
        ),
        visibility=VisibilityWindow(start=0.0, end=8.5),
    )
    cloud = Shape(
        id="cloud",
        layer="art",
        z=0,
        geometry=Ellipse(radius_x=180.0, radius_y=60.0),
        visibility=VisibilityWindow(start=1.0, end=None),
    )
    mountain = Shape(
        id="mountain",
        layer="art",
        z=1,
        geometry=Polygon(
            points=(
                Vector2(x=0.0, y=300.0),
                Vector2(x=320.0, y=0.0),
                Vector2(x=640.0, y=300.0),
            )
        ),
    )
    route = Path(
        id="route",
        layer="art",
        z=2,
        style_role="route.primary",
        commands=(
            MoveTo(point=Vector2(x=100.0, y=700.0)),
            LineTo(point=Vector2(x=400.0, y=620.0)),
            CubicTo(
                control1=Vector2(x=500.0, y=580.0),
                control2=Vector2(x=700.0, y=760.0),
                point=Vector2(x=900.0, y=650.0),
            ),
            ClosePath(),
            MoveTo(point=Vector2(x=1000.0, y=650.0)),
            LineTo(point=Vector2(x=1200.0, y=620.0)),
        ),
    )
    nested_caption = Text(
        id="nested-caption",
        layer="labels",
        content="Nested label",
        font_role="caption",
        size=22.0,
        z=-1,
    )
    nested_group = Group(
        id="nested-group",
        layer="labels",
        z=0,
        transform=Transform(position=Vector2(x=40.0, y=90.0)),
        children=(nested_caption,),
    )
    title = Text(
        id="title",
        layer="labels",
        z=0,
        content="Anima — 世界 🌍",
        font_role="heading",
        size=72.0,
    )
    title_group = Group(
        id="title-group",
        layer="labels",
        z=5,
        style_role="panel",
        visibility=VisibilityWindow(start=None, end=7.0),
        children=(title, nested_group),
    )
    outro_dot = Shape(
        id="outro-dot",
        layer="marks",
        geometry=Circle(radius=12.0),
    )

    return Project(
        style_pack=StylePackRef(id="crude", version="1.4.2"),
        resolution=Resolution(width=1280, height=720),
        fps=24.0,
        seed=8675309,
        wpm=165.0,
        scenes=(
            Scene(
                id="intro",
                layers=(
                    Layer(id="art", nodes=(background, sun, cloud, mountain, route)),
                    Layer(id="labels", nodes=(title_group,)),
                ),
            ),
            Scene(id="outro", layers=(Layer(id="marks", nodes=(outro_dot,)),)),
        ),
    )
