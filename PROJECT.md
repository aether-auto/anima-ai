# anima-ai

An open-source Python library + CLI that lets AI agents author paint-style animated explainer videos as code, and verify the result deterministically — without any human (or model) having to watch the video.

## Vision

Animated explainer channels (OverSimplified, Kurzgesagt, Armchair Historian) prove there is enormous appetite for history, geopolitics, tech, and science told through stylized 2D animation — but producing one episode takes a human team weeks. AI agents can already write scripts and code; what they cannot do is render a 15-minute animated video and *know* it came out right without a human watching it. anima-ai closes that loop: a deterministic scene-graph engine where "the program is correct" implies "the video is correct," so an agent can write scenes, run `verify`, iterate until green, and ship.

Why now: agent tooling (Claude Code, MCP-era agents) is exploding, LLMs write Python fluently, and no animation library is designed for LLM authorship or machine verification. Manim is human-first and math-shaped; Remotion is human-first and React-shaped; nothing owns "agent-authored explainer video."

Unfair advantage: founder is a strong software engineer deep in AI tooling, building the library *with* agents as user #1 — the tool is dogfooded by its own target user from day one.

Wildly successful in three years: anima-ai is the default library an AI agent reaches for when the task is "make an explainer video" — the Manim of this genre — and has grown from the paint-style wedge into a general agent-video platform. The paint-style explainer niche is the wedge, not the ceiling: core APIs stay general (scene-graph video engine), styles are packs on top.

## Users

Primary: AI agents (Claude, GPT, etc.) operating in coding loops — they write scene code against the Python API, run the CLI (`render`, `verify`, `preview`), read machine-readable errors, and iterate autonomously. API ergonomics, error messages, and verification output are designed for LLM consumption first.

Secondary (behind the agent): people like the founder — technically capable creators who love the animated-explainer genre and want to produce episodes for history/geopolitics/tech/science without a human animation team. Today their alternative is: don't make videos at all, or spend weeks per episode in After Effects/VideoScribe-class tools.

## Core value proposition

An AI agent can go from narration script to a verified, coherent, 15–20 minute paint-style animated video entirely in code — no human review needed in the loop.

## Business model

None. Open source (permissive license), zero revenue, ~zero budget (free tiers only: GitHub CI, PyPI). Deliberately deferred: if adoption ever proves it, hosted rendering / style-pack marketplace are plausible monetization paths — a decision for later, logged when made. This is reputation- and usage-driven for now.

## Non-goals

- **No photorealism, no real-footage editing.** Stylized 2D vector/paint rendering only. This is not a video editor.
- **No GUI editor, ever.** Code/agent-authored only. Preview output yes; timeline-drag UI no.
- **No AI-generated assets in core.** Art is procedural (wobbly strokes, paint textures) + curated bundled SVG packs — fully deterministic and offline. AI asset generation breaks verify-without-watching and the zero-budget constraint.
- **No audio rendering in v1** (deliberate phase, not a never): the timeline is narration-script-driven from day one (script sets timing, optional burned-in subtitles), TTS/audio mixing is a later phase.
- Not banned but not v1: 3D, realtime playback, MCP server. Architecture should not foreclose them.

## Technical foundation

Python library (pip-installable) + CLI as the agent interface. Deterministic 2D renderer (correct-by-construction: golden-image-tested primitives, verified scene graph ⇒ trusted output) with ffmpeg for encoding. Maps are a v1 core primitive: GeoJSON/Natural Earth data, historical borders, territory fills, invasion arrows, label pops. Two style packs at launch: OverSimplified-crude (history/geopolitics) and Kurzgesagt-flat (tech/science), as pluggable packs over a general engine. Verification is deterministic-only: scene-graph assertions (positions, overlaps, timing sums, on-screen guarantees, pacing/layout constraint rules) — no VLM, no paid APIs. Full detail: `docs/cofounder/specs/technical-architecture.md`.

## Success looks like

V1 done = an AI agent, using only the library + CLI, produces a coherent 15–20 minute script-driven silent video (maps + characters + text, subtitles optional) that passes verification end-to-end — and the founder watches it once and says "yes, that's the style." No deadline; quality over speed. Scale implication taken seriously: 15–20 min ≈ 100+ scenes/beats, so render performance, cross-scene consistency, and verification at scale are v1 requirements.

## Current state

Founding complete (2026-07-13): alignment interview done, feasibility research done (verdict: build, positioned verification-first — see `docs/cofounder/specs/feasibility-report.md`), all six founding specs and the roadmap written. Next: `cofounder:spec` task decomposition, then Phase 0 (foundations & determinism rig). No code yet.

## Key links

- Cofounder persona: `docs/cofounder/COFOUNDER_PERSONA.md`
- Decision log: `docs/cofounder/DECISIONS.md`
- Roadmap: `docs/cofounder/ROADMAP.md`
- Specs: `docs/cofounder/specs/`
