# Go-To-Market — anima-ai

## Positioning

**The animation library AI agents can trust:** author paint-style explainer videos as Python code, verify them deterministically without watching. One line against each alternative (full landscape in feasibility-report.md): Remotion — "that's React and a paid license; agents still eyeball frames"; HyperFrames — "that's a rendering layer; there's no scene graph to verify"; Manim wrappers — "that's retry-loops around an API built for humans"; Golpo/Simi — "that's a SaaS for people; agents can't author or check it." The wedge audience is history/geopolitics/tech/science explainer creation via agents; the category name to own long-term: **agent-verified video**.

## Pricing / monetization

None. Apache-2.0, free forever for the library. This is honest, not naive: the feasibility report shows the pure-library business is brutal even with traction (Revideo's founders pivoted away; Remotion sustains ~$270k-raised-scale, not venture-scale), so pretending v1 has a business model would distort design decisions. If adoption ever proves it, the logged candidate paths are hosted rendering and a style-pack/asset marketplace — a future decision for DECISIONS.md, not a v1 constraint. Budget stays ~$0 (GitHub/PyPI/GHCR/Pages free tiers).

## Acquisition

Users are agents, so acquisition means being findable and installable *by agents* — the channels are unusually concrete:

1. **Agent-skill distribution** (primary): SKILL.md in-repo from day one (cross-vendor standard: Claude Code, Codex CLI, Cursor, Gemini CLI, Copilot); listed in skill registries/marketplaces as they mature. Remotion's skill pulled ~25k installs in week one — the channel demonstrably works.
2. **Agent-docs infrastructure**: llms.txt + AGENTS.md + version-pinned docs, Context7 listing so agents retrieve real API docs instead of hallucinating (the feasibility report's key adoption lesson).
3. **PyPI + GitHub organic**: the searches that currently dead-end in Manim complaints ("python animated video library", "manim alternative explainer") are the long-tail entry.
4. **Show-don't-tell launches**: Show HN and r/Python posts anchored on a real agent-produced episode with its verify report — the demo *is* the argument. HN's documented affection for Manim-likes and open-source Remotion alternatives (feasibility report, sentiment section) makes this the right room.
5. **The founder's channel as living proof**: every episode published is a case study produced by the tool's own target loop; repo links in descriptions.

## Launch plan

Launch = **v0.1.0 on PyPI** when the ROADMAP's launch-phase bar is met (agent produces a multi-minute verified episode end-to-end; both style packs shipped; cookbook + SKILL.md tested against a fresh agent session). Launch assets, all produced by the tool itself: a 2–3 minute flagship episode (crude pack, history topic, subtitles on), a 60-second flat-pack tech explainer, the contact sheets and the verify JSON for both, and a README that leads with the agent loop (`new → verify → fix → render`) in under 30 lines. Announcement surfaces in order: Show HN, r/Python + r/opensource, the Manim/Motion-Canvas-adjacent communities where the pain is documented. External publication under Arnav's name (PyPI account, posts) → per the persona contract, each gets a heads-up first. Post-launch discipline: every "verify passed but a human flagged it" report from the wild becomes a constraint-rule issue — in public, because visibly converging verification is the marketing.

## Growth loops

1. **Output carries the signature.** Paint-style output is visually distinctive; every published video is an ad the way every Manim video advertises Manim. (Attribution is optional and default-off in rendered output — trust over growth-hacking — but the style itself is recognizable.)
2. **Verification-rule flywheel**: real-world misses → new rules → verify gets harder to fool → the "agents can trust it" claim strengthens → more agent usage surfaces more misses. This loop is the moat compounding.
3. **Cookbook/pack contributions**: style packs and asset packs are data + parameters — the lowest-friction contribution shape there is; community packs expand addressable genres without core changes.
4. **Agent-session word-of-mouth, literally**: agents that succeed with the library reproduce the pattern in future sessions from their harness's skill registry — skill installs are a compounding channel, not one-shot marketing.

## Competitive moat

Honest ranking. (1) **The constraint-rule corpus** — taste encoded as tested, versioned rules, accumulated from real failures; slow to build, slower to copy, and architecturally unavailable to browser-screenshot pipelines (their layout state lives in the DOM, not an inspectable graph). (2) **Verify/render single-geometry architecture** — a structural choice competitors would need a rewrite, not a feature sprint, to match. (3) **The map engine + vendored historical data** — unowned niche, real data-curation grunt work as the barrier. (4) **Python + Apache-2.0 + agent-first ergonomics** — real but thinnest; Remotion or HyperFrames could ship Python bindings or an authoring layer. What is *not* a moat: paint aesthetics (copyable), being first (HyperFrames went 0→34k stars in months; speed matters), open source itself. Timeline honesty from the feasibility report stands: ship the wedge before the giants notice the verification story.
