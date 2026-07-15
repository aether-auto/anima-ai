# Technical Architecture — anima-ai

## Stack

- **Python ≥3.10** — the language LLMs write best, the ecosystem agents live in, and the slot where the only incumbent (Manim) is weakest. Downside accepted: slower per-frame math than Rust/C++; mitigated by pushing rasterization into Skia (C++) and keeping Python as the orchestration layer.
- **skia-python (pinned exact version)** — 2D rasterization backend. Full path/shader/filter surface needed for wobbly strokes and paint textures, ~34× faster than Pillow for vector work, wheels on all mainstream platforms, vendored FreeType (pins text rasterization — good for determinism). Downsides accepted: rendering output can shift between Skia milestones (upgrade = regenerate goldens, documented policy), Linux CI images need GL/EGL system libs, and security fixes to the vendored FreeType arrive only via version bumps.
- **PyAV (pinned/capped)** — encoding. Bundles ffmpeg so `pip install anima-ai` is the entire setup (Manim's v0.19 switch to PyAV for exactly this reason is the precedent; their need to cap PyAV versions is the warning we heed). Rejected: ffmpeg-python (unmaintained since ~2019), raw subprocess pipes (loses the no-system-ffmpeg install story; moviepy's never-fixed multiprocess pipe deadlocks are the cautionary tale).
- **shapely + pyproj + topojson** — map geometry, projections, topology-aware simplification. Explicitly rejected: geopandas (drags pandas + GDAL/pyogrio; documented install-reliability risk; we read GeoJSON with stdlib `json` + `shapely.geometry.shape()`). PROJ version pinned for reproducibility.
- **Vendored map data** — Natural Earth 1:110m/1:50m pre-converted to GeoJSON, plus historical-basemaps, version-pinned and shipped as package data (or a data wheel if size demands). No runtime downloads — offline and deterministic.
- **numpy** — bulk coordinate math (shapely 2.x is numpy-native already).
- **pytest + custom golden-image harness** — pixelmatch-style comparison (YIQ perceptual diff, anti-aliased-pixel exclusion, configurable threshold; comparison logic vendored — it's small and the existing Python wrappers are single-maintainer projects). Baselines generated in a pinned Docker container (Playwright's lesson: even identical-spec machines diverge on fonts).
- **No web framework, no database, no server.** It's a library + CLI. State is files in the user's project directory.

## System architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Agent-facing surface                                         │
│  CLI (anima new/verify/render/preview/inspect/assets)        │
│  Python API (anima package)   SKILL.md / llms.txt / cookbook │
└──────────────┬──────────────────────────────────────────────┘
               ▼
┌─────────────────────────────────────────────────────────────┐
│ Authoring layer                                              │
│  Script/Beats ──► Timeline compiler ──► Keyframe tracks      │
│  Scene builders / node constructors / animation declarations │
└──────────────┬──────────────────────────────────────────────┘
               ▼
┌─────────────────────────────────────────────────────────────┐
│ Scene graph (single source of truth, JSON-serializable)      │
│  Project → Scenes → Layers → Nodes (+ per-property tracks)   │
└───────┬─────────────────────────────────┬───────────────────┘
        ▼                                 ▼
┌───────────────────────┐    ┌────────────────────────────────┐
│ Verification engine   │    │ Render pipeline                │
│  structural checks    │    │  Geometry resolver (shared ◄───┼── same code path
│  layout/readability   │◄───┤  with verifier)                │
│  taste constraints    │    │  Skia rasterizer               │
│  → JSON report        │    │  layer cache → frame stream    │
└───────────────────────┘    │  → PyAV encoder (1 thread)     │
                             └────────────────────────────────┘
Style packs (palette/fonts/wobble/textures/assets/constraint profiles)
Map engine (GeoJSON, projections, territory index) — feeds nodes + verifier
Seeded RNG service — feeds paint rendering; keyed by (project_seed, node_id)
```

The load-bearing structural rule: **the geometry resolver** — the code that answers "where is this node's rendered bounding box at time t, in output pixels" (including text shaping via Skia and map projection) — **is one module used by both the verifier and the renderer.** Verification claims are honest because they are computed from the same arithmetic that will paint the pixels. Any feature whose layout the verifier cannot resolve does not ship until it can.

## Data flow

**1. Authoring → verify (the hot loop).** Agent writes/edits Python scene code → `anima verify` imports the project, builds the scene graph, compiles the script to a timeline → structural checks walk the graph → geometry resolver computes text/shape/map bounding boxes at sampled times (beat boundaries + animation midpoints) → layout/readability/taste rules evaluate → JSON report to stdout, typed exit code. No rasterization; target ≤30s for 100+ beats.

**2. Render.** Same graph build → per-frame: evaluate keyframe tracks → resolve geometry → rasterize via Skia with static-layer cache (unchanged layers composite from cache; only animated layers redraw) → RGBA frames stream to a single PyAV encoder thread (frame production decoupled from encoding; Manim PR #3888 pattern) → atomic move of finished MP4 into place. `--scene/--beat/--range` renders subsets.

**3. Preview.** Same graph build → sample keyframes per beat → rasterize just those frames → compose annotated contact-sheet PNGs (beat IDs + timestamps) and optionally a low-res MP4.

## Key technical decisions

1. **Own scene-graph renderer, not browser screenshots.** Alternative: HyperFrames/Remotion-style headless-Chrome capture. Rejected because the browser hides scene state inside the DOM/CSS engine — you can't assert semantic layout without re-deriving it, which is exactly why those tools have no verification story. Downside accepted: we own text shaping, easing, compositing — more engine work before first pixels.
2. **Verification is geometric and static, not pixel-based, above the primitive level.** Golden images test primitives once (does a wobbly stroke rasterize correctly); everything compositional is checked on the scene graph. Alternative — golden-frame diffs per project — only detects drift against a previous render, useless for newly authored content. Downside accepted: a defect class outside the rule set can pass verify; the mitigation is metric #2 in the product spec (every human-caught miss becomes a rule).
3. **Determinism via seeded RNG keyed by (project_seed, stable node ID).** No `random`, no `Date.now`-equivalents, no dict-iteration-order dependence in the render path. Bit-exact per platform+version; cross-platform equality is tolerance-based, not bit-exact (matplotlib's 20-year war and resvg's bundle-everything counterexample both say: we bundle fonts and pin rasterizer, and still keep CI goldens in one pinned container rather than chasing bit-exactness on every OS).
4. **WPM-estimated timing now, real word timings later.** The `Beat` carries narration text and derives duration; the estimator is a swappable strategy. When TTS lands, forced-alignment timings drop into the same interface. Downside accepted: v1 pacing is approximate — mitigated by per-beat `hold` overrides and pacing rules in verify.
5. **Style packs as data + parameters + constraint profiles, not code forks.** Alternative: subclass the renderer per style. Rejected: two forks in month one becomes unmaintainable, and packs must be third-party-authorable eventually. Downside accepted: the pack schema must be designed carefully up front (it's in data-model.md).
6. **Python API as the authoring surface, JSON as the interchange.** Agents write Python (their strongest language, richest expressiveness); the built scene graph serializes to JSON for `inspect`, diffing, and future non-Python frontends. Alternative — YAML/JSON as the primary authoring format — rejected: loses loops/functions/composition that make 100+ beat projects tractable.
7. **Apache-2.0 license.** Patent grant matters for a rendering engine; matches the norm of the agent-tooling ecosystem it must live in (HyperFrames is Apache-2.0); positions cleanly against Remotion's BUSL friction. (Logged in DECISIONS.md.)

## Deployment & infrastructure

Distribution: PyPI package `anima-ai`, import name `anima` (name availability on PyPI to be confirmed before first publish; fallback import name `animaai`). Pure-Python package with pinned binary dependencies (skia-python, PyAV, shapely, pyproj wheels cover Win/macOS/Linux, x86_64+arm64). Map data vendored as package data; if the wheel exceeds ~60MB, split into `anima-ai-data` companion wheel — never a runtime download. CI: GitHub Actions free tier — lint, type-check (mypy strict on public API), unit tests on the 3-OS matrix, golden-image jobs inside the pinned container image (image published to GHCR). Docs: static site (mkdocs-material) on GitHub Pages. Releases: tagged, changelog-driven; publishing to PyPI is an external action under Arnav's name → flag per the persona contract.

## Security & privacy posture

The library handles no user data, makes zero network calls at runtime (assets and map data are vendored; this is enforced by a test that fails on any socket use in the render/verify path), and executes only the user's own project code. Threat model is therefore supply-chain-shaped: pinned dependencies with hash-locked lockfiles for CI, no install-time code execution beyond standard wheel install, GHCR container images built from committed Dockerfiles. `anima` never invokes a shell with user input. Nothing to comply with (no PII, no payments, no minors' data).

## Integrations

Deliberately none at runtime. Third-party surface is build/distribution only: PyPI, GitHub Actions, GHCR, GitHub Pages — all free tiers, all replaceable. If GitHub Actions is down, releases wait; nothing user-facing breaks. The MCP server and TTS integrations are future phases and must not be foreclosed: the CLI's `--json` contract is designed so an MCP wrapper is a thin shim, and the timeline's timing-strategy interface is where TTS alignment plugs in.

## Scalability

Scale axis is video length, not concurrent users. Targets: 15–20 min at 1080p30 ≈ 27k–36k frames. Design consequences: memory is O(active scene), never O(project) — frames stream to the encoder, nothing buffers the video; static-layer caching makes typical explainer frames (one or two animated elements over a stable map) cheap; verify is O(nodes × sampled times) with spatial indexing (an R-tree or simple grid over bounding boxes) so overlap checks stay subquadratic on 100-node scenes. Where it breaks first, honestly: single-machine render throughput on fully-dynamic scenes (camera moves invalidate the layer cache). Acceptable — a 15-min render measured in tens of minutes on a laptop still beats every alternative by weeks; per-scene parallel render (N processes, one encoder, concat at the end) is the designed escape hatch and ships in the performance phase.

## Testing strategy

- **Unit tests** on all timeline math, geometry resolution, easing, map projection round-trips, and every verification rule (each rule gets fixture scenes that violate it and fixtures that pass).
- **Golden-image tests** for every renderer primitive and style-pack element (strokes at parameter extremes, textures, each character asset, arrow heads, subtitle rendering), generated and compared in the pinned container; tolerance comparison locally.
- **Property-based tests** (hypothesis) on determinism: same seed ⇒ identical serialized graph and identical frame hashes; different node IDs ⇒ decorrelated wobble.
- **End-to-end**: cookbook examples render fully in CI (low res) and their verify reports are snapshot-tested; the flagship long-form project renders nightly, not per-commit.
- **Agent-in-the-loop tests** (the novel one): scripted harness where a real agent session is given a deliberately broken project + the verify output and must fix it without rendering — this is how "could an agent fix its scene from this error alone" stops being rhetoric and becomes a regression suite.
- **Confident enough to ship** = all of the above green in CI + the definition of done in the persona: for user-facing features, an actual render was produced and checked.
