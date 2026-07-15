# Product Spec — anima-ai

## Positioning

anima-ai is an open-source Python library + CLI that lets an AI agent author a paint-style animated explainer video as code and *prove it came out right without anyone watching it*. Every existing option fails the agent somewhere: Remotion and HyperFrames are TypeScript/HTML rendering layers whose agents still verify by eyeballing frames; Manim is Python but has a maintainer-acknowledged unstable API that LLMs demonstrably fail against; prompt-to-video SaaS (Golpo, Simi, VideoScribe-class) produces opaque output with no code artifact an agent can author, diff, or check. anima-ai's bet, grounded in the feasibility report: verification is the product. A deterministic scene-graph engine where correctness is checked by construction — golden-tested primitives, scene-graph assertions, taste encoded as constraint rules — so "verify passes" is a real guarantee, not a vibe.

## Users

**Primary: AI agents in coding loops** (Claude Code, Codex-class tools). Their job-to-be-done: given a narration script and a topic, produce a finished, coherent, stylistically consistent animated video, and know it is correct without human review. Today they either can't do this at all, or they bolt retry-loops and VLM frame-review onto Manim/Remotion — scaffolding that measurably barely works (VLM visual-regression accuracy 45.2%; layout defects are the lowest-scoring metric in every LLM-animation benchmark). Everything in this product — API shape, error format, CLI output, docs — is designed for LLM consumption first. The design test for any surface: *could an agent fix its scene from this output alone, without seeing a single pixel?*

**Secondary: the human behind the agent** — technically capable creators (the founder is user zero) who love the animated-explainer genre (OverSimplified, Kurzgesagt) and want to produce history/geopolitics/tech/science episodes without an animation team. They interact through the agent and through preview artifacts; they judge style and content, never fix render bugs.

## Core value proposition

An AI agent goes from narration script to a verified, coherent, 15–20 minute paint-style animated video entirely in code — no human review in the loop. This holds up because the engine is deterministic end-to-end (same project + seed + version ⇒ same frames), primitives are golden-image-tested once in CI, and everything above the primitives is checked by scene-graph assertions and constraint rules that run in seconds without rendering. The agent iterates against `verify` the way it iterates against a compiler.

## Full capability set

### 1. Scene-graph engine (core)

A declarative scene tree: a `Project` contains `Scene`s; a scene contains layers of typed nodes (shapes, paths, text, SVG assets, characters, map elements, groups). Every node has a stable ID, transform (position/rotation/scale/anchor), style reference, z-order, and a visibility window on the timeline. The scene graph is the single source of truth: the renderer draws it and the verifier inspects it — both from the same geometry code path, so verification and rendering cannot disagree about where things are. The graph is fully serializable (JSON) for debugging, diffing, and machine inspection. Nothing in core knows about "history videos" — genre lives in style packs and asset packs.

### 2. Narration-shaped timeline

The timeline is driven by a narration script even though v1 renders no audio. A `Script` is an ordered list of `Beat`s; each beat carries narration text, an estimated duration derived from a configurable words-per-minute model (default 150 wpm, per-beat overridable with explicit `hold`/`pause`), and the scene actions that happen during it (node entrances/exits, animations, camera moves). All timing flows from the script — an agent never hand-computes frame numbers. Beats compile to per-property keyframe tracks. Optional burned-in subtitles render the narration text with style-pack typography, timed to beats. The model is explicitly TTS-ready: when audio lands in a later phase, real word timings replace the WPM estimator and nothing else changes.

### 3. Animation system

Declarative, deterministic animations attached to nodes and beats: enter/exit families (fade, slide, pop, paint-reveal where strokes draw on progressively), transforms (move, scale, rotate along paths), map-specific animations (territory fill sweep, border morph, arrow growth along a curve, label pop), camera animations (pan, zoom, focus-on-node, map viewport flight), and scene transitions (cut, crossfade, wipe, paper-slide). Every animation is a pure function of time — no wall-clock, no randomness outside the seeded RNG — with a standard easing library. Duration and choreography come from the beat structure.

### 4. Procedural paint rendering

The signature look, generated deterministically: noise-displaced "wobbly" stroke paths with variable width and jitter, paint/paper texture fills, hand-drawn imperfection — all driven by a project-level seed combined with stable node IDs, so re-renders are identical and two nodes never wobble in sync. Includes procedural text stroking that traces glyph outlines properly (a documented craft failure in Doodly that users notice). Wobble parameters, texture choice, and stroke behavior are style-pack properties, not core constants.

### 5. Style packs (two at launch)

A style pack is a pluggable bundle: palette (named roles, not raw hexes), typography (bundled open-license fonts), stroke/wobble parameters, texture set, transition defaults, and an asset pack of characters/props. Launch packs: **`crude`** (OverSimplified-inspired: MS-Paint-ish characters, blob nations, comedic label pops — for history/geopolitics) and **`flat`** (Kurzgesagt-inspired: clean flat vectors, geometric characters, smooth easing — for tech/science). Style packs also ship *constraint profiles* (see capability 7): the crude pack tolerates crowding the flat pack forbids. Core engine renders any pack; packs are data + parameters + assets, not forks of the renderer.

### 6. Map engine (core primitive, not a plugin)

First-class geographic scenes for the history/geopolitics genre: GeoJSON ingestion with vendored, version-pinned Natural Earth data (1:110m and 1:50m) and historical-borders dataset support; map projections via pyproj with sane defaults (equal-earth for world, azimuthal for regional); topology-aware simplification so adjacent territories never gap or overlap; typed map nodes — `BaseMap`, `Territory` (fill/highlight by dataset ID or custom polygon), `Border`, `InvasionArrow` (curved, growing arrows with style-pack heads), `MapLabel`, `MapMarker`; and a map camera with animated viewport (center/zoom/flight paths). Territories are addressable by dataset ID with date awareness for historical datasets. Map state (colors, fills, camera) persists across scenes unless changed — recurring-map continuity is engine-managed, not agent-managed.

### 7. Verification engine (the differentiator)

`anima verify` checks a project without rendering it, in seconds, and reports machine-readable results. Three layers:

- **Structural checks** (always on, errors): scene-graph validity (unique IDs, resolvable references, assets exist, fonts available), timing arithmetic (beat durations sum to scene durations; every animated property resolves to exactly one value at every t; no animation targets a node outside its visibility window), and map validity (territory IDs exist in the pinned dataset, arrows land inside the camera viewport, projections defined).
- **Layout & readability constraints** (errors and warnings, computed from the renderer's own geometry): no unintended overlap between text and text, or text and salient nodes; safe-area margins respected; minimum rendered font size at output resolution; on-screen text duration ≥ reading time (configurable wpm reading model); subtitle/label contrast ratio against the resolved background color meets threshold.
- **Taste constraints** (style-pack profiles, mostly warnings, promotable to errors): pacing rules (beat too long without visual change, too many simultaneous entrances, scene density ceilings), palette adherence (only pack roles used), cross-scene continuity (a character/territory keeps its assigned color across the project; camera doesn't teleport without a transition).

Output: a JSON report — each finding has a stable error code (e.g. `OVERLAP.TEXT_TEXT`, `TIMING.READ_TIME`, `MAP.UNKNOWN_TERRITORY`, `CONTINUITY.COLOR_DRIFT`), severity, the node IDs and beat IDs involved, the time window, expected vs actual values, and a concrete `fix_hint` ("delay label_7 entry to t≥14.0 or move below y=820"). The +37–40pp agent-task-completion evidence for structured repair suggestions is the design basis. Human-readable output is a formatting of the same report, never a separate code path.

### 8. Rendering & encoding pipeline

Frame-exact rasterization of the scene graph via a pinned Skia backend; encoding via PyAV (bundled ffmpeg — `pip install` is the entire setup, the anti-Manim install story). Renders 1080p30 by default (resolution/fps configurable). Static layers are cached and composited; frame production is decoupled from encoding (render workers feed a single encoder, never per-worker ffmpeg pipes). Partial renders: `--scene`/`--beat`/time-range flags so an agent re-renders only what it changed. Output is written atomically — no corrupt MP4s on interruption.

### 9. Preview artifacts

For the human checkpoint without a full render: `anima preview` produces a contact sheet (grid of keyframe PNGs, one or more per beat, annotated with beat IDs and timestamps) and/or a low-res fast-encoded MP4 of selected scenes. Contact sheets are the primary human review surface — cheap, diffable, and they show style and layout at a glance.

### 10. Agent-facing CLI

`anima new` (scaffold a project with style pack and script skeleton), `anima verify`, `anima render`, `anima preview`, `anima inspect` (dump scene graph / timeline / resolved timings as JSON), `anima assets` (list available characters, props, territories, fonts for the active pack — so agents discover vocabulary instead of hallucinating it). Every command: `--json` structured output, typed exit codes distinguishing success / verification-failure / user-error / internal-error, strict stdout-data-stderr-diagnostics separation, non-interactive by default, `--help` written as agent documentation.

### 11. Agent onboarding surface

Shipped in-repo and versioned with the code: a SKILL.md (cross-vendor agent-skills standard) teaching the authoring loop (scaffold → write scenes → verify → fix → preview → render), llms.txt + AGENTS.md, and a cookbook of complete worked examples (a 3-beat map scene, a character dialogue scene, a full 2-minute episode) that agents can pattern-match from. Docs are version-pinned and structured for retrieval — the feasibility report's evidence says badly structured agent docs make agents *worse*, so this surface is engineered and tested (see success metrics), not written as an afterthought.

### 12. Determinism & trust infrastructure

Project-level seed; no wall-clock or ambient randomness anywhere in the render path; bundled fonts (never system fonts); pinned Skia/PyAV/PROJ versions with a documented upgrade-and-regenerate-goldens policy; golden-image tests for every renderer primitive and style-pack element, generated and compared inside a pinned CI container; tolerance-based comparison (anti-aliasing-aware) for developer machines. This is what makes "verified scene graph ⇒ trusted video" an honest claim rather than marketing.

## Explicit non-goals

- **No photorealism, no real-footage editing.** Stylized 2D vector/paint only. Different product, different users.
- **No GUI editor, ever.** Code/agent-authored only; preview artifacts yes, timeline-drag UI no. A GUI would fork every design decision toward humans and away from agents.
- **No AI-generated assets in core.** Procedural art + curated bundled packs only. AI asset generation breaks determinism (the core promise), requires paid APIs (zero-budget violation), and creates license ambiguity.
- **No VLM or paid API anywhere in the verify path.** Deterministic-only verification is the product's identity; the moment verify needs a model call it's just another probabilistic judge like the ones that measurably barely work.
- **No audio rendering in v1** — deliberate phase, not a never. The timeline is narration-shaped from day one; TTS/mixing lands later without a timeline rewrite.
- **Not in v1, architecture must not foreclose:** 3D, realtime playback, MCP server, audio.

## Competitive landscape

(Grounded in `feasibility-report.md`; summarized here for positioning.)

- **Remotion** — incumbent, React/TS, agent skills with ~126k+ installs, BUSL license. Position against: Python (the agent's native language), genuinely open license, and verification — Remotion's own docs have no rendered-output verification story.
- **HyperFrames (HeyGen)** — Apache-2.0, agent-first, deterministic rendering + golden regression. Position against: it's an HTML→video rendering layer, not an authoring library — no scene graph to assert against, no semantic verification, no animation vocabulary, no maps, no style system. Scene-graph-native verification is architecturally hostile to retrofit onto browser-screenshot pipelines; that structural difference is the moat.
- **Manim + its agent-wrapper ecosystem** — the Python incumbent and the clearest demand signal: an entire cottage industry of retry-loop wrappers exists because Manim's API fails agents. Position against: LLM-first API, machine-readable errors, painless install, non-math aesthetic.
- **Prompt-to-video SaaS (Golpo, Simi, VideoScribe/Doodly class)** — proves output demand; competes for a different user (non-technical humans). No code artifact, no API, no verification. An agent cannot use them.
- **Generative pixel video (Sora/Veo/Kling)** — not a competitor for this genre: ~15–20s clip ceilings, no cross-shot consistency, garbled text, per-second API cost vs our zero-marginal-cost local rendering.
- **Do nothing / status quo** — human teams in After Effects (weeks per episode, $1.5k–4k+/min) or not making videos at all. This is the actual alternative for the secondary user.

## Success metrics

1. **The v1 bar (from PROJECT.md):** an AI agent, using only the library + CLI + shipped docs, produces a coherent 15–20 minute script-driven silent video (maps + characters + text, subtitles on) that passes `verify` end-to-end — and the founder watches it once and says "yes, that's the style."
2. **Verification honesty rate:** when `verify` passes and a human then watches the render, the rate of "a human would have flagged this" defects trends toward zero; every such miss becomes a new constraint rule (tracked in LEARNINGS.md). This metric is the product.
3. **Agent-fixability:** in dogfooding, ≥90% of verification failures are fixed by the agent in one iteration without rendering or human help. Measured continuously during development, since the founder builds with agents.
4. **Iteration economics:** `verify` on a 100-beat project completes in ≤30s; a single-scene re-render in ≤2 min on the founder's machine — fast enough that the agent loop feels like a compiler loop.
5. **Post-launch (directional, not vanity):** external agents/creators producing videos we didn't make — GitHub issues referencing real projects, videos in the wild, skill installs. No numeric target until launch data exists.
