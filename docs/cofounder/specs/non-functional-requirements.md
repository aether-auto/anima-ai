# Non-Functional Requirements — anima-ai

Reference machine for all targets: the founder's Apple-Silicon laptop (M-series, 16GB+). CI numbers may be slower; targets are validated on the reference machine.

## Performance

- `anima verify` on a 100-beat / ~1000-node project: **≤30s**, and ≤5s for a 10-beat project (the hot-loop case an agent hits dozens of times per session).
- Single-scene re-render (typical ~60–90s of video, 1080p30): **≤2 minutes**.
- Full 15–20 min 1080p30 render (~27k–36k frames): **≤60 minutes** with static-layer caching on typical explainer content; fully-dynamic worst case may exceed this — acceptable, documented, and per-scene parallel render is the escape hatch (ships in the performance phase, see ROADMAP).
- Sustained render throughput floor on typical content: **≥8 frames/sec**; encoder must never be the bottleneck (frame production and encoding decoupled).
- `anima new`, `assets`, `inspect`: **≤3s** — these are inner-loop vocabulary lookups.
- Memory: **O(active scene), bounded ≤2GB** regardless of project length (streaming encode, no whole-video buffering).

## Reliability

- **No corrupt artifacts, ever:** renders write to temp and atomically move; an interrupted render leaves the previous output untouched.
- **No flaky behavior:** identical inputs ⇒ identical outputs (frames, reports, exit codes). A nondeterministic test or render is a P0 bug, not a retry candidate.
- **Failure = finding:** any foreseeable failure (bad reference, missing asset, invalid timing) surfaces as a structured finding with a fix hint. Raw tracebacks reaching the user are product bugs; the CLI's global handler converts unexpected exceptions to `INTERNAL.ERROR` findings with a bug-report pointer and nonzero exit.
- Degradation posture: there is no server to degrade; the failure domain is the user's machine. Partial renders (`--scene`) mean one broken scene never blocks work on others.

## Security

Threat model is supply-chain and trust-in-output, not runtime attack surface (no network, no server, no user data — see technical-architecture.md):

- Zero runtime network I/O, enforced by a socket-guard test in CI.
- Dependencies pinned; CI installs hash-locked; Dependabot/audit alerts triaged monthly (vendored-FreeType CVEs in skia-python are the known watch item — upgrade policy: bump, regenerate goldens, release).
- `verify --force`-style escape hatches always leave visible traces in output metadata — the verification promise must not be silently bypassable, because downstream trust in "verify passed" is the product.
- No shell invocation with user-controlled strings anywhere.

## Compliance

None applicable: no PII, no payments, no telemetry (explicitly: the library phones home never), no regulated-industry data. Licensing compliance is the one real obligation: all bundled fonts/assets/map data carry permissive licenses with attribution files shipped in-package (Natural Earth is public domain; historical-basemaps and fonts vetted per-asset before bundling).

## Observability

For a local tool, observability = the user's and agent's ability to see what happened:

- Structured logs to stderr with `--verbose` levels; `--json` on every command for machine consumption.
- Render/preview outputs stamped with metadata (engine/pack/dataset versions, seed, verify status, timing stats) — every artifact is self-describing and reproducible from its stamp.
- `anima inspect` is the debugger: full graph, compiled tracks, point-in-time resolution.
- CI is the fleet monitor: golden diffs, determinism property tests, nightly long-form render with timing regression tracking (a >20% render-time regression fails the nightly).
- Issue templates request the artifact metadata stamp — reproduction is one `git clone` + pinned versions away.

## Accessibility standards

Produced-video bars (enforced by verify, per ux-design-spec.md): subtitle contrast ≥4.5:1, minimum rendered text sizes, reading-time pacing, colorblind-safe palette roles in both launch packs. Tooling: CLI meaning never conveyed by color alone; docs site WCAG 2.1 AA basics. No formal certification claimed.
