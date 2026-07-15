# Scene-graph authoring contract

Phase 1 public contract lives in `anima.scene_graph`. Package uses Python standard library
only. Timeline compilation, geometry evaluation, style-pack resolution, rendering, CLI
commands, map nodes, assets, and verification findings remain separate subsystems.

Generated `project.py` modules expose one typed module-level value:

```python
from anima.scene_graph import Project, StylePackRef

project: Project = Project(
    style_pack=StylePackRef(id="crude", version="1.0.0"),
)
```

Consumers import `project`; they do not search for classes, call factories by class path, or
mutate global state.

## Units and defaults

Coordinates, dimensions, anchors, and translation values use scene pixels. Rotation uses
degrees. Visibility boundaries use non-negative seconds. Scale values are dimensionless.

| Value | Default |
|---|---|
| `Resolution` | `1920 × 1080` |
| `Transform.position` | `(0.0, 0.0)` |
| `Transform.rotation` | `0.0` degrees |
| `Transform.scale` | `(1.0, 1.0)` |
| `Transform.anchor` | `(0.0, 0.0)` |
| `VisibilityWindow` | `start=None, end=None` |
| `Project.fps` | `30.0` |
| `Project.seed` | `0` |
| `Project.wpm` | `150.0` |
| `Project.engine_version` | current `anima._version.ENGINE_VERSION` |
| `Project.scenes` | empty tuple |

`Project.style_pack` has no default. Every project pins both style-pack `id` and `version`.
Style roles remain opaque non-empty strings in Phase 1.

Booleans never count as integers or numbers. Numeric values reject NaN and infinities.
Resolution, `fps`, `wpm`, text size, and geometry dimensions must be positive. Visibility
boundaries must be non-negative; resolved intervals require `start <= end`. Identifiers reject
empty and whitespace-only strings. Strings reject isolated UTF-16 surrogates that UTF-8 cannot
encode.

## Immutability and rebuild lifecycle

Every public model uses `@dataclass(frozen=True, slots=True, kw_only=True)`. Every ordered
caller collection is copied into tuple during construction. Later mutation of source list or
generator state cannot affect project.

Editing means rebuilding affected value, node, layer, scene, then project. Project construction
revalidates complete hierarchy and rebuilds traversal/lookup views. No subsystem mutates project
in place.

## Node payloads

All nodes provide stable `id`, declared `layer`, local `transform`, optional `style_role`, integer
`z`, and `visibility`. Child transforms inside group remain local to group. Later geometry
resolver composes ancestor transforms.

| Node | Discriminator | Typed payload |
|---|---|---|
| `Shape` | `shape` | `Rectangle`, `Circle`, `Ellipse`, or `Polygon` |
| `Path` | `path` | ordered `MoveTo`, `LineTo`, `CubicTo`, and `ClosePath` commands |
| `Text` | `text` | Unicode `content`, non-empty `font_role`, positive finite `size` |
| `Group` | `group` | recursive tuple of Phase 1 nodes |

| Geometry | Discriminator | Fields |
|---|---|---|
| `Rectangle` | `rectangle` | positive finite `width`, `height` |
| `Circle` | `circle` | positive finite `radius` |
| `Ellipse` | `ellipse` | positive finite `radius_x`, `radius_y` |
| `Polygon` | `polygon` | at least three finite `Vector2` points |

Path requires initial `MoveTo`. `ClosePath` requires open subpath containing at least one line or
cubic segment. Segment after close requires new `MoveTo`. Consecutive moves start or replace empty
subpaths.

## Ordering and traversal

Scene order, layer order, root-node order, group-child order, polygon-point order, and path-command
order preserve declaration order.

`Layer.render_order` and `Group.render_order` return immutable tuples sorted by
`(z, declared_sequence_index)`. Equal-`z` ties remain stable. Group occupies one item in parent
order; group children sort recursively within group.

`Project.preorder`, `iter_nodes()`, and `walk_nodes()` expose deterministic declared
scene/layer/root/child preorder. `node_lookup` and `nodes_by_id` expose same read-only mapping;
`get_node(id)` returns node or `None`.

Project validation enforces:

- project-unique scene IDs;
- scene-local layer IDs;
- project-wide node IDs, including nested groups;
- single-parent ownership for each node instance;
- exact agreement between node `layer` and containing layer.

Collisions fail; IDs never auto-rename.

## Structured errors

`SceneGraphValidationError` covers model/value/graph failures.
`SceneGraphDecodeError` covers malformed JSON and schema failures. Both inherit
`SceneGraphError` and expose:

| Field | Meaning |
|---|---|
| `code` | stable machine code such as `GRAPH.DUPLICATE_NODE_ID` |
| `offending_id` | related stable ID when one exists, otherwise `None` |
| `path` | model or JSON path locating failure |
| `message` | concise human-readable detail |

Verifier catches these errors and reports fields unchanged. Agent correction logic keys on
`code` and `path`, never message text.

## JSON compatibility policy

Public APIs:

- `project_to_dict(project)` produces full schema wrapper;
- `project_from_dict(value)` strictly decodes full schema wrapper;
- `dumps_project(project)` produces canonical JSON text;
- `loads_project(data)` accepts UTF-8 `str` or `bytes`.

Current wrapper:

```json
{"schema_version": "1.0", "project": {}}
```

Real `project` payload must contain every required field. Writer emits every default. Ordered
collections use arrays. Keys use snake_case. Nodes, geometry payloads, and path commands use
explicit `type` discriminators; class paths never enter JSON.

Canonical writer uses `sort_keys=True`, `ensure_ascii=False`, `allow_nan=False`, two-space
indentation, UTF-8, and exactly one trailing newline. Inspect writes this output unchanged.

Decoder rejects invalid JSON constants, duplicate keys, missing keys, extra keys, wrong primitive
types, non-finite values, unknown discriminators, malformed payloads, graph invariant violations,
and missing or unsupported schema versions.

Minor schema versions may add fields only when decoder explicitly supports that minor version.
Major schema versions may make breaking changes. Every accepted version requires explicit decoder
support. No implicit migration occurs; there is no implicit migration between versions.

## Downstream boundaries

- Timeline targets stable node IDs and reads `VisibilityWindow`; scene graph derives no timing.
- Inspect emits canonical codec output unchanged.
- Geometry resolver dispatches typed node payloads and later composes group transforms.
- Renderer consumes `Layer.render_order` and `Group.render_order` recursively.
- Verifier catches structured build errors and traverses same immutable project graph.
- Style-pack subsystem resolves pinned `StylePackRef` and opaque roles later without mutating
  project.
- Map nodes, assets, animation evaluation, paint behavior, render fields, and verification findings
  add no Phase 1 node variants or guessed fields.
