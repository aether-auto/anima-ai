# UX / Design Spec — anima-ai

The "user interface" of anima-ai is three surfaces: the Python API an agent writes against, the CLI + machine-readable outputs an agent reads, and the visual output + preview artifacts a human judges. This spec covers all three; there are no screens in the app sense.

## Design principles & voice

1. **The agent is the user.** Every surface is judged by one test: *could an agent fix its scene from this output alone, without seeing a pixel?* Human convenience never wins a conflict with agent legibility (it rarely has to — clarity serves both).
2. **Errors are steering, not blame.** Every failure states what's wrong, what was expected, and a concrete next action, in stable machine-readable form. A bare stack trace reaching an agent is a product bug.
3. **Deterministic or absent.** No surface may behave differently across runs with identical inputs. If a feature can't be made deterministic, it doesn't ship (this is the non-goal boundary, restated as a design principle).
4. **Visual voice — two poles, both committed:** `crude` is confident scrappiness (wobbly linework, blobby characters, punchy label pops, comedic timing tolerated by its constraint profile — OverSimplified is the reference); `flat` is calm precision (geometric shapes, generous whitespace, smooth easing — Kurzgesagt is the reference). "On-brand" means a frame is unmistakably one of the two; the failure mode both packs forbid is the generic corporate-explainer middle (stock-flat characters, default easing everywhere, palette soup) — that's the aesthetic of the tools users called "generic" in the sentiment research.
5. **Text is a craft object.** Procedural stroke quality on text, real reading-time pacing, contrast floors — the details review-mining showed users notice and incumbents fumble.

## Information architecture

- **Python API (`anima`)**: `Project` / `Scene` / `Script`+`Beat` / node constructors / animation verbs / `StylePack` — small, flat, typed, fully type-hinted; public API is everything importable from `anima`; anything else is private by convention and by docs. One obvious way per task; kwargs-soup and Manim-style public/private ambiguity are the named anti-patterns.
- **CLI (`anima`)**: `new` · `verify` · `render` · `preview` · `inspect` · `assets`. Verbs are the workflow, in order. Global flags: `--json`, `--quiet`, `--project`.
- **Project directory** (what `anima new` scaffolds): `project.py` (or package for big projects), `script.md` (narration, beat-annotated), `out/` (renders, previews, reports — gitignored), pinned pack/dataset versions in `project.py` itself. Everything an agent needs to understand a project is in tracked text files.
- **Docs**: quickstart → cookbook (complete runnable examples, smallest first) → API reference → verification-rule catalog (every code, meaning, fix patterns) → SKILL.md/llms.txt/AGENTS.md mirroring the same content for agent retrieval.

## Key flows

### Flow 1 — Agent authors an episode (the core loop)
1. `anima new epic-of-gilgamesh --style crude` → scaffold + skeleton script.
2. Agent writes `script.md` narration split into beats; writes scene code binding beats to nodes/animations. Vocabulary discovery via `anima assets --json` (characters, poses, territories, palette roles) — never guessed.
3. `anima verify --json` → findings. Exit 0 = pass; exit 3 = findings (machine-parseable). Agent edits source per `fix_hint`s, re-verifies. Loop until green. Errors gate; warnings are judgment calls the agent may accept.
4. `anima preview --scenes 1-3` → contact sheet for the human checkpoint (optional but expected at style-decision moments).
5. `anima render` (or `--scene N` incrementally) → MP4. Render refuses to run with error-severity findings unless `--force` (visible escape hatch, logged in output metadata).
Failure paths: Python exception in project code → caught, reported as `BUILD.EXCEPTION` finding with file/line, not a raw traceback dump; missing asset/territory → `REF.*` finding naming nearest matches ("did you mean `prussia_1866`?").

### Flow 2 — Human style checkpoint
Founder opens contact sheet PNG(s): beats labeled, timestamps, style-pack name and versions in the header. Judges style/tone only. Feedback goes to the agent as prose; the agent translates it into scene-code changes. The human never edits engine state directly — there is nothing to edit but code.

### Flow 3 — Verification failure autopsy (when verify passed but the human spots a defect)
`anima inspect --at 12.4 --json` dumps resolved geometry/graph state at the offending time; the gap becomes a new rule (or a rule-threshold change) in the style pack's constraint profile; LEARNINGS.md records it. This flow is product-critical: it is how the constraint system converges on taste (success metric #2).

### Flow 4 — Long-form assembly (15–20 min episode)
Project as a package: chapters as modules, each with its own scenes; `anima verify` runs whole-project (cross-scene continuity rules especially); `anima render --scene`/`--chapter` incrementally during authoring; full render is a finale step. Contact sheets per chapter keep human review tractable (~1 sheet per 2–3 min of video).

## Screen / view breakdown (CLI outputs and artifacts)

- **`verify` human format**: summary line (`✗ 3 errors, 5 warnings in 14 beats`), findings grouped by scene→beat, each one line: code, node(s), t-window, then indented fix_hint. Color only when TTY. `--json`: the VerificationReport schema (data-model.md) — the human format is rendered *from* the JSON, one code path.
- **`render`/`preview` progress**: single-line progress (frames, fps, ETA) on stderr; final artifact path + metadata (duration, frames, verify status, engine/pack versions) as the stdout payload (`--json` structured).
- **Contact sheet**: grid PNG, 4–6 columns; each cell a keyframe with beat id + timestamp caption; header strip: project, scene, pack+version, seed. Neutral gray chrome that never color-clashes with either pack's palette.
- **`inspect`**: JSON only (it *is* the machine view): full graph, `--compiled` tracks, `--at <t>` resolved snapshot.
- **`assets`**: table (human) / JSON (agent) of ids, types, poses, license tags; territories filterable by dataset and date.

## Accessibility

For the produced videos: optional burned-in subtitles ship in v1 (deaf/HoH viewers and the enormous muted-autoplay audience); verify enforces subtitle contrast ratio ≥ 4.5:1 against resolved background, minimum rendered subtitle size, and reading-time pacing; both launch palettes avoid red/green-only semantic distinctions (colorblind-safe roles checked at pack build time, not per video). For the tool: CLI human output never encodes meaning in color alone (symbols + text carry it); docs site meets WCAG 2.1 AA basics. No formal certification target — the concrete bars above are the commitment.

## Platform-specific behavior

None by design at the feature level: identical CLI surface and behavior on macOS/Linux/Windows (paths handled properly; no shell-isms in subprocess use — there are no subprocesses in the hot path anyway). Known platform seams, handled explicitly rather than papered over: cross-platform renders are tolerance-equal, not bit-equal — the reproducibility contract is per-platform+version, and CI goldens live in the pinned Linux container; Windows console gets plain-ASCII fallback for the summary glyphs. Agent environments (headless CI, containers) are first-class: no GUI dependency anywhere, `preview` writes files and never tries to open a viewer.
