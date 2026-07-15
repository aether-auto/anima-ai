<!--
  docs/cofounder/DECISIONS.md — append-only. Newest entries at the bottom.
  Log consequential autonomous calls as you make them, not in a batch afterward. Skip
  trivial implementation choices (variable names, which loop construct) — this is for
  things a returning cofounder or the human would actually want to know were decided and why.
  Keep each entry to a few lines; this file is meant to be skimmed, not read end to end.
-->

# Decisions

Format per entry:

```
## YYYY-MM-DD — [short decision title]
**Context:** why this came up
**Decision:** what was decided
**Reasoning:** the one or two lines that justify it
**Reversible:** yes/no — and if no, what made it worth deciding without a check-in
```

---

## 2026-07-13 — Founding scope settled in alignment interview
**Context:** Project kickoff; Arnav's idea was "library for AI models to generate paint-style animated videos, verified without watching."
**Decision:** Library-first (videos are the flagship demo, not the product); Python + CLI (no MCP in v1); open source, zero budget, no deadline; users are AI agents directly; deterministic-only verification; procedural + bundled assets (no AI image gen in core); maps are a v1 core primitive; two style packs (OverSimplified-crude, Kurzgesagt-flat); no photorealism, no GUI editor as permanent non-goals; 3D/realtime not banned but not v1.
**Reasoning:** These were interview answers, confirmed explicitly by Arnav in the restatement.
**Reversible:** Mostly yes, but treated as the founding contract — changes go through Arnav.

## 2026-07-13 — Silent v1 resolved as "script-driven, no audio"
**Context:** Tension between "silent for now" and v1 bar of "15–20 min coherent videos" — that genre coheres through narration; a truly silent 18-minute video isn't watchable content.
**Decision:** V1 timeline is narration-script-driven: the agent writes a narration script, the script drives timing (words-per-minute estimates, beats, holds) and optional burned-in subtitles; no audio rendering in v1. TTS/audio mixing is a later roadmap phase, not a never.
**Reasoning:** Keeps v1 scope tight while making audio retrofit-safe — the timeline model never has to be rewritten when TTS lands.
**Reversible:** Yes (audio can be pulled forward if v1 output feels hollow without it).

## 2026-07-13 — Wedge/platform split written into architecture stance
**Context:** Arnav wants "broad agent-video platform" as the 3-year ambition but open-source/zero-revenue now; those collide eventually (platform = infra spend).
**Decision:** Core engine stays a general scene-graph video engine; paint-style explainers are pluggable style packs (the wedge). Monetization decision explicitly deferred until adoption proves it.
**Reasoning:** Lets today's zero-budget open-source reality coexist with the platform ambition without bloating v1 or hardcoding the niche into core APIs.
**Reversible:** Yes.

## 2026-07-13 — Cofounder named Fresco; game-design-doc template removed
**Context:** Arnav asked me to name myself; project is not a game.
**Decision:** Cofounder persona is "Fresco"; deleted the unused `game-design-doc.md` spec template.
**Reasoning:** Paint-on-plaster metaphor fits a paint-style animation library; the game template would otherwise sit as a permanent stub, which the persona forbids.
**Reversible:** Yes.

## 2026-07-13 — Research runs killed and salvaged instead of re-run
**Context:** The initial five deep-research workflows fanned out ~140 subagents before Arnav killed them as wasteful; the cofounder plugin was amended to a budget-capped research design (≤10 subagents). Arnav instructed: compile existing artifacts, no restart.
**Decision:** Salvaged all five workflow journals (25 search-result sets + ~79 claim extractions), compiled them into per-angle digests, synthesized `feasibility-report.md` inline with zero new subagents. The adversarial-verification stage never ran, so the report carries an explicit provenance caveat; the single verdict-critical claim (HyperFrames) was re-verified by direct fetch.
**Reasoning:** The salvaged corpus already covered all five angles with named sources; re-running research would have duplicated ~90% of it for marginal verification gain.
**Reversible:** Yes — specific claims can be spot-verified later if a decision ever hinges on one.

## 2026-07-13 — Founding specs written; key technical positions locked
**Context:** Arnav approved the feasibility verdict ("go"); Phase 4–5 of the plan skill.
**Decision:** All six founding specs + ROADMAP.md written. Consequential calls made inside them: **Apache-2.0 license** (patent grant for a rendering engine; matches agent-ecosystem norms; positions against Remotion's BUSL); **own scene-graph renderer** rather than browser-screenshot capture (verification needs an inspectable graph — the moat is architectural); **verify and render share one geometry-resolver module** (verification honesty by construction); **skia-python + PyAV + shapely/pyproj/topojson, all version-pinned, no geopandas**; **stack: Python ≥3.10, package `anima-ai`, import `anima`** (PyPI availability check gated to launch phase); **golden baselines generated only in a pinned container**, tolerance comparison elsewhere; **style packs as data + constraint profiles**, two at launch (`crude`, `flat`); **no runtime network I/O, enforced by test**; roadmap sequenced 0–8 with the determinism rig first.
**Reasoning:** Each traces to feasibility-report evidence (Manim's install/API failures, HyperFrames' unclaimed semantic-verification gap, matplotlib/resvg determinism lessons, moviepy/ffmpeg-python maintenance record).
**Reversible:** License and public API shape are hard to reverse after launch; everything else is pre-code and cheap to revisit. Launch itself (PyPI publish, posts under Arnav's name) remains explicitly flagged.

## 2026-07-14 — Task backlog completed via conservative sonnet-only rerun
**Context:** The first cofounder:spec run (24 agents, Fable/Opus + GPT lanes) died on session limits with only 14 of 40 planned task specs written, and every per-sprint QA verdict was BLOCK (empty tasks.json, `created_at: "undefined"`, gh-workflow verification commands that can't run without a GitHub remote, golden generate-then-compare rubber stamps, missing dependency edges, mislabeled complexity). Arnav directed a restart with fewer agents, sonnet only.
**Decision:** Salvaged the 40-task decomposition from the failed run's journal (no re-decompose), fixed `created_at` mechanically with jq, then ran a 13-agent sonnet-only workflow: 9 writers for the 26 missing specs (with hardened grounding rules distilled from the old QA findings), 3 fixers applying those findings to the existing 14 files, 1 full-backlog QA. All 40 specs validate; tasks.json rebuilt (40 tasks, 18 dependency layers); knowledge graph warmed.
**Reasoning:** The decompose output and QA findings were already paid for — reusing them cut the rerun to roughly half the agents and a third of the tokens of the original run, and baking the QA lessons into writer prompts prevented re-introducing the same defects.
**Reversible:** Yes — individual specs are direct-editable (validate-spec.mjs + build-tasks-index.mjs after).

## 2026-07-14 — REF.UNKNOWN_STYLE_ROLE ownership moved to style-pack-system
**Context:** Final backlog QA found exactly one phase-order violation: verify-structural-checks (Phase 2) depended on style-pack-system (Phase 3) because its REF.* checks validated `style_role` names against the pack role namespace that Phase 3 defines. ROADMAP.md promises each phase finishes before the next begins.
**Decision:** `REF.UNKNOWN_STYLE_ROLE` ships with style-pack-system (Phase 3), where the namespace is defined; verify-structural-checks explicitly excludes it and drops the forward dependency. Both spec files state the ownership on each side.
**Reasoning:** A check can't be honest before its namespace exists; moving the check to the namespace's task preserves strict phase gating without scaffolding. Alternative (re-sequencing style-pack-system into Phase 2) would drag paint-rendering concerns forward for one rule.
**Reversible:** Yes.
