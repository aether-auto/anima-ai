# Roadmap

Build order for anima-ai. Each phase is finished — shippable, not scaffolded — before the next begins. Full scope lives in `docs/cofounder/specs/product-spec.md`; every capability there appears in exactly one phase below. If a phase runs long, it gets more time, not a narrower definition of done. (Audio/TTS, MCP server, 3D, realtime are v1 non-goals per the product spec — deliberately absent here, not deferred into a vague bucket.)

## Current phase

**Phase 0: Foundations & determinism rig** — not started

## Phase 0: Foundations & determinism rig

Repo, packaging, CI, and the trust infrastructure everything else stands on (product-spec capability 12). First because retrofitting determinism and golden testing is exactly the trap the feasibility research documents (matplotlib's decades of tolerance warfare).

**Done when:**
- [ ] Repo scaffolded: `pyproject.toml` (package `anima-ai`, import `anima`), Apache-2.0 LICENSE, lockfile, mypy-strict + ruff, pytest wired.
- [ ] Pinned deps installed and importing on the 3-OS CI matrix: skia-python, PyAV, shapely, pyproj, topojson, numpy.
- [ ] Seeded-RNG service implemented: keyed by (project_seed, node_id), property-tested (same key ⇒ same stream; different node ids ⇒ decorrelated).
- [ ] Golden-image harness working end-to-end: pinned Docker container published to GHCR, baseline generate/compare/update commands, vendored AA-aware tolerance comparison, one trivial Skia-rendered fixture passing in CI.
- [ ] Socket-guard test fixture exists and passes (no network in library code paths).
- [ ] Fonts bundled (both packs' typography candidates, licenses vetted, attribution file).

## Phase 1: Scene graph, timeline, and first pixels

Core engine (capabilities 1, 2 minus subtitles, 3, 8, and CLI skeleton from 10): typed scene graph, script/beat timeline compiler, animation system, geometry resolver, Skia rasterization with static-layer cache, PyAV streaming encode, `anima new/render/preview/inspect`. This is the largest phase; everything downstream consumes it.

**Done when:**
- [ ] A scripted 60–90s multi-scene project (shapes, text, groups; entrances/exits/transforms; camera pan/zoom; scene transitions) renders to a correct 1080p30 MP4 from `anima render`.
- [ ] All timing derives from a beat-annotated script via the WPM model with `hold`/`pause` overrides; timing-strategy interface is TTS-shaped (swappable estimator).
- [ ] Geometry resolver answers bounding-box-at-t for every node type shipped so far, unit-tested against rendered-pixel bounds on fixtures.
- [ ] Determinism proven: same project+seed renders byte-identical frame hashes across two runs in CI; property tests green.
- [ ] Static-layer cache measurably works (cached vs uncached benchmark in CI, ≥3× on the fixture project) and renders stream with bounded memory.
- [ ] `anima new` scaffolds a runnable project; `preview` emits annotated contact sheets; `inspect`/`inspect --compiled`/`--at t` dump the documented JSON; atomic output writes verified by a kill-test.
- [ ] CLI contract in place on all commands: `--json`, typed exit codes, stdout/stderr separation, agent-readable `--help`.

## Phase 2: Verification engine v1 + subtitles

The differentiator (capability 7, structural + layout/readability layers; subtitle rendering from capability 2 lands here because its verify rules — contrast, reading time — arrive with it). Depends on Phase 1's geometry resolver.

**Done when:**
- [ ] Structural checks complete: `REF.*`, ID uniqueness, timing closure invariants, animation-outside-visibility, `BUILD.EXCEPTION` capture with file/line (no raw tracebacks).
- [ ] Layout/readability rules live: `OVERLAP.TEXT_TEXT`, `OVERLAP.TEXT_NODE`, `MARGIN.SAFE_AREA`, `FONT.MIN_SIZE`, `TIMING.READ_TIME`, `CONTRAST.LOW` — each with violating + passing fixture tests and concrete `fix_hint`s.
- [ ] VerificationReport JSON schema published and snapshot-tested; human output rendered from the same report object; `render` gates on error-severity findings (`--force` leaves a metadata trace).
- [ ] Burned-in subtitles render from beat narration with per-pack typography, and their verify rules pass on fixtures.
- [ ] `verify` ≤5s on a 10-beat project, ≤30s on a synthetic 100-beat/1000-node project (spatial index in place).
- [ ] Agent-in-the-loop regression suite exists: ≥10 deliberately-broken fixture projects; a fresh agent session given only verify JSON fixes ≥9 without rendering — measured, in-repo harness, repeatable.

## Phase 3: Paint rendering + `crude` style pack

The signature look (capabilities 4, 5-crude): procedural wobble strokes, paint/paper textures, paint-reveal animation, glyph-tracing text strokes, style-pack schema + constraint-profile plumbing, first character/prop asset pack.

**Done when:**
- [ ] Stroke/texture/wobble primitives golden-tested at parameter extremes; wobble decorrelation across nodes property-tested.
- [ ] Style-pack schema implemented (palette roles, fonts, stroke profile, textures, transitions, asset manifest, constraint profile) with pack-version pinning in projects.
- [ ] `crude` pack ships: full palette, typography, ≥12 characters with ≥3 poses each, ≥20 props, blob-nation shapes, comedic label-pop animation set — every asset golden-tested and license-vetted.
- [ ] `anima assets --json` lists the real vocabulary; `STYLE.PALETTE_VIOLATION` rule active.
- [ ] The Phase 1 fixture project re-rendered in `crude` looks unmistakably OverSimplified-adjacent — founder style checkpoint passed (logged).

## Phase 4: Map engine

The genre-defining primitive (capability 6) and its verify rules. After paint rendering so map elements ship styled, not placeholder-flat.

**Done when:**
- [ ] Vendored Natural Earth (1:110m, 1:50m) + historical-basemaps datasets load offline with a territory index (id → geometry, date validity); packaging stays under the wheel-size policy or splits into the data wheel.
- [ ] Projections (equal-earth default, azimuthal regional) via pinned pyproj; topology-aware simplification proven gap/overlap-free on adjacent-country fixtures.
- [ ] Node types shipped and golden-tested in both pack styles: BaseMap, Territory (dataset-ref and inline polygon), Border, InvasionArrow (curved growth animation), MapLabel, MapMarker.
- [ ] Map camera flights (center/zoom paths) render smoothly and deterministically.
- [ ] Engine-managed map-state persistence across scenes works (fills/camera/labels carry over unless changed).
- [ ] Map verify rules live with fixtures: `MAP.UNKNOWN_TERRITORY` (with nearest-match hints), `MAP.ARROW_OUT_OF_VIEW`, `MAP.DATE_MISMATCH`, projection-defined checks.
- [ ] A 2-minute map-driven mini-episode (borders shift, arrows advance, labels pop, camera flies) verifies and renders end-to-end in `crude`.

## Phase 5: `flat` pack + taste constraints + continuity

Second style pack proves packs are actually pluggable (capability 5-flat); the taste-constraint layer and cross-scene continuity rules complete capability 7.

**Done when:**
- [ ] `flat` pack ships at parity bar: palette, typography, ≥12 geometric characters, ≥20 props, smooth-easing transition set — golden-tested, license-vetted.
- [ ] Rendering the same fixture project under each pack requires zero scene-code changes beyond the pack id (pluggability proof).
- [ ] Taste rules live, thresholds per-pack: `PACING.BEAT_STALL`, `PACING.ENTRANCE_STORM`, `PACING.SCENE_DENSITY`, `CONTINUITY.COLOR_DRIFT`, `CONTINUITY.CAMERA_TELEPORT` — each with fixtures in both packs (crude tolerates what flat forbids, tested).
- [ ] Severity configuration (promote/demote per project) works and is visible in report metadata.
- [ ] Founder style checkpoint on a flat-pack tech-explainer fixture passed (logged).

## Phase 6: Long-form scale & performance

The 15–20 min requirement made real (NFR targets; the scalability design in technical-architecture.md). After all content features exist, because optimizing before the map engine and packs land would optimize the wrong profile.

**Done when:**
- [ ] Chapter/package project structure supported and documented; whole-project verify runs cross-scene rules over 100+ beats in ≤30s.
- [ ] Per-scene parallel render (N worker processes, single encoder/concat, deterministic output identical to serial) ships.
- [ ] NFR targets hit on the reference machine: single-scene re-render ≤2 min; full 15-min typical-content render ≤60 min; memory ≤2GB throughout; ≥8 fps sustained on typical content.
- [ ] Nightly CI renders a long-form fixture with timing-regression gate (>20% fail).
- [ ] A complete 15–20 minute silent episode (maps + characters + text + subtitles) verifies and renders end-to-end — the pipeline proof, ahead of the polished flagship.

## Phase 7: Agent onboarding surface + the v1 bar

Capability 11 and the product's success metric #1. Last before launch because the docs must describe the real, frozen surface.

**Done when:**
- [ ] SKILL.md (authoring-loop skill), llms.txt, AGENTS.md shipped in-repo; verification-rule catalog documents every finding code with fix patterns.
- [ ] Cookbook complete: map scene, character scene, full 2-minute episode — all CI-rendered, verify-snapshot-tested.
- [ ] Fresh-agent test passes: an agent session with no prior context, given only the installed package + shipped docs, produces a verified multi-scene video without human debugging (the harness from Phase 2, pointed at onboarding instead of repair).
- [ ] **The v1 bar:** an agent produces a coherent 15–20 minute script-driven episode passing verify end-to-end, and Arnav watches it once and says "yes, that's the style." Misses feed the Flow-3 autopsy loop until this passes.

## Phase 8: Launch v0.1.0

Go-to-market execution per `go-to-market.md`.

**Done when:**
- [ ] PyPI name confirmed (`anima-ai`; import-name fallback decision logged if needed) and v0.1.0 published (external action — flagged to Arnav first).
- [ ] Docs site live on GitHub Pages; Context7 listing submitted.
- [ ] Launch assets produced by the tool itself: flagship crude episode (2–3 min cut for the post), 60s flat explainer, contact sheets + verify JSON published alongside.
- [ ] Show HN + r/Python posts drafted, approved by Arnav (his name), posted.
- [ ] Post-launch flywheel running: "verify passed but human flagged it" issue template live; first week's reports triaged into constraint-rule issues.
