# Data Model — anima-ai

There is no database; these are the in-memory/serialized entities of a project. The scene graph serializes to JSON (`anima inspect`) and that serialization is a public, versioned contract — agents and tests depend on it.

## Entities

### Project
The root. Fields: `name`, `style_pack` (id + version), `resolution` (default 1920×1080), `fps` (default 30), `seed` (int, drives all procedural randomness), `wpm` (narration timing model default), `scenes` (ordered), `engine_version` (stamped at build for reproducibility). Exists separately from Scene because determinism, style, and timing policy are global — a scene must not be able to disagree with the project about fps or seed.

### Script / Beat
`Script` is the ordered list of `Beat`s for a scene (or spanning scenes — beats reference their scene). `Beat`: `id`, `narration` (text), `duration` (derived: wpm model over narration unless explicit `hold`/`pause` override), `subtitle` (bool/inherited), `actions` (ordered animation/camera/scene-op declarations). Beat is its own entity — not folded into Scene — because it is the unit of timing, the unit of verification reporting ("error in beat b12"), and later the unit of TTS alignment.

### Scene
A titled segment with its own layer stack and background. Fields: `id`, `layers` (ordered), `transition_in/out` (style-pack default unless overridden), derived `duration` (sum of its beats — never set directly; invariant below).

### Node (abstract) → Shape, Path, Text, Asset, Character, Group, BaseMap, Territory, Border, InvasionArrow, MapLabel, MapMarker
Everything drawable. Common fields: `id` (stable, unique per project, human/agent-readable — auto-suffix collision is an error, not a rename), `transform` (pos/rot/scale/anchor), `style_role` (palette role, not raw color; raw color allowed but verify's palette rule flags it), `z`, `visible_window` (entry/exit times, derived from the beats that animate it in/out), `layer`. Subtype fields where meaningful (Text: content, font role, size; Territory: dataset ref + territory id + date, or inline polygon; InvasionArrow: from/to (points or territory ids), curvature, head style; Character: asset id + pose). Nodes are typed subclasses rather than one bag-of-props node so the verifier can apply type-specific rules (text readability, arrow-in-viewport) without heuristics.

### Track / Keyframe (compiled, not authored)
The timeline compiler lowers beats + actions into per-(node, property) tracks of keyframes with easing. Authored code never touches these directly; they exist as an entity because verify's "exactly one value at any t" invariant and render's evaluation both operate here. Serialized in `inspect --compiled` output.

### StylePack
`id`, `version`, `palette` (named roles → colors), `fonts` (roles → bundled font files), `stroke_profile` (wobble amplitude/frequency/width-variation/jitter params), `textures`, `transition_defaults`, `assets` (manifest of Characters/props with ids, poses, license notes), `constraint_profile` (rule thresholds/severities). Versioned because a pack update can change layout metrics (font swap) — a project pins pack version.

### AssetRef / MapDataset
`AssetRef`: pack-qualified id resolved at build; missing asset is a structural verify error, never a runtime surprise. `MapDataset`: vendored dataset id + version + license; provides the territory index (id → geometry, valid date range) that Territory/Border/Arrow nodes resolve against and that `anima assets --territories` lists.

### VerificationReport / Finding
Report: `project`, `engine_version`, `pack_version`, `counts`, `findings[]`, `pass` (bool: zero error-severity findings). Finding: `code` (stable, namespaced: `OVERLAP.TEXT_TEXT`, `TIMING.READ_TIME`, `MAP.UNKNOWN_TERRITORY`, `CONTINUITY.COLOR_DRIFT`, …), `severity` (`error`|`warning`), `beat_ids`, `node_ids`, `t_window`, `expected`, `actual`, `fix_hint` (concrete, actionable), `rule_version`. This schema is public API — agents program against it; changes are versioned and changelogged.

### GoldenBaseline (repo-internal)
Primitive/pack-element id + parameters + container image tag + PNG. Exists as an entity because the upgrade policy ("pin and regenerate goldens") needs baselines to be addressable and diffable, not loose files.

## Relationships

```
Project 1─n Scene 1─n Layer 1─n Node
Project 1─1 Script 1─n Beat n─n Node        (beats animate nodes via actions)
Beat    1─n Action ──► compiles to ──► Track n─1 (Node, property)
Node    n─1 StylePack.role   Node(map types) n─1 MapDataset.territory
Project n─1 StylePack (pinned version)
verify(Project) ──► VerificationReport 1─n Finding ──► references Beat/Node ids
```
Enforcement: all in application logic at graph-build time (there is no DB); reference resolution failures are structural verify errors with the same Finding schema.

## Invariants

1. **Timing closure:** scene duration ≡ Σ beat durations; project duration ≡ Σ scene durations (+ transitions); no track keyframe outside its node's visible window; every animated property has exactly one resolved value ∀t. Enforced by the timeline compiler (construction) and re-checked by verify (belt and suspenders).
2. **Determinism:** identical (project source, seed, engine version, pack version) ⇒ identical serialized graph, identical compiled tracks, identical frame hashes. No wall-clock, env, locale, or iteration-order dependence in build/render paths. Enforced by design + property-based tests.
3. **Referential integrity:** every `style_role`, font role, asset id, territory id, node id reference resolves; ids unique. Enforced at build; violations are `REF.*` findings.
4. **Verify/render agreement:** any geometry the verifier reasons about is computed by the same resolver the renderer uses. Enforced structurally (one module) and by tests that compare verifier-predicted bounding boxes against rendered-pixel bounding boxes on fixtures.
5. **Offline purity:** no network I/O in build/verify/render. Enforced by a socket-guard test fixture.
6. **Report stability:** finding codes are append-only; a code's meaning never changes (deprecate, don't mutate). Enforced by schema tests + changelog discipline.

## Lifecycle & state

- **Project build:** authored Python → graph construction (`REF.*`/structure errors surface here) → timeline compilation (timing invariants enforced) → immutable built artifact consumed by verify/render/preview/inspect. Built graphs are never mutated; edits happen in source and rebuild.
- **Finding lifecycle:** raised → agent fixes source → rebuild → gone. No suppression mechanism in v1 except explicit per-rule severity config in the project (a visible, diffable choice — silent inline suppressions invite agents to cheat verify).
- **Style pack / dataset / engine versions:** pinned in project; upgrading any of them is an explicit action expected to change renders (goldens regenerate; verify may raise new findings). Within one pinned set, behavior is frozen — that is the reproducibility contract.
- **Map state across scenes:** map camera, territory fills, and label states persist scene-to-scene unless a beat changes them (engine-managed continuity); the continuity verifier rules check drift against this persisted state.
