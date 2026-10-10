# 0001 — Quality first: deterministic code for mechanics, model effort for taste

Status: Accepted (2026-10-10)

## Context

The first TOSUMI reel was expensive mostly because of subagent fan-outs that re-researched references and ran
five review lenses — about 84% of output tokens. The initial instinct was to make every reel as cheap as
possible. The developer rejected that: the goal is reels that beat competitors who edit by hand; a Max plan is
acceptable; speed does not matter.

"Training" the tool does not mean the model learns. It means moving decisions out of the model and into code,
presets and written rules, so they are made the same way, well, every time.

## Decision

- Mechanical work is deterministic code and never re-decided by the model per reel: transcription, take
  cutting, white-balance matching, HDR→SDR, layout solving, mixing, rendering.
- Model effort is spent where taste lives: competitor research, ideas, hooks, scripts, accent-word and
  line-break choices, graphic choices, bespoke graphics, and one real self-review of each draft before the
  creator sees it.
- Do not re-research what is already codified (brand styles, formats, templates). Do not trade quality for
  tokens.

## Consequences

- Each recurring decision that the model keeps getting wrong is a candidate for code or a learned rule.
- Per-reel cost is driven by creative stages, not by plumbing; it is measured on real batches to pick the plan.
