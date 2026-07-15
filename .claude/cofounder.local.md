---
gpt_terra_model: gpt-5.6-terra
gpt_sol_model: gpt-5.6-sol
---

# Cofounder plugin — local config

Not committed to project history if this project's `.gitignore` excludes `.claude/*.local.md`
(recommended — this file is machine/account-specific).

`gpt_terra_model` / `gpt_sol_model` are the exact `--model` values `cofounder:spec` and
`cofounder:execute` pass to `codex-companion.mjs task` for the GPT worker lanes. These are not
guessed or hardcoded in the skills themselves — edit them here to match whatever GPT-5.6 model
IDs are actually available in this Codex account. If a preflight check at the start of a sprint
finds one of these doesn't resolve, that lane is disabled for the run (logged to
`docs/cofounder/LEARNINGS.md`) rather than failing the whole sprint.
