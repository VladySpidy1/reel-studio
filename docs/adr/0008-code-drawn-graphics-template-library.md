# 0008 — Code-drawn graphics: per-brand template library plus bespoke graphics

Status: Accepted (2026-10-10)

## Context

"AI video" in this project means code-drawn motion graphics, like the developer's fully code-generated
explainer (see `docs/references/claude_unity_sheet.jpg`), not generative video models. The subtitle renderer
already draws HTML/CSS in headless Chrome, so graphics can use the same engine. Unlike that explainer, the
creator's reels have a person in frame, so graphics must respect the face and product.

## Decision

- Graphics are rendered by the same HTML renderer as subtitles and placed by the same layout solver (person
  matte, text-behind-subject).
- Each brand has a library of parametric graphic templates, designed and polished once on the developer's
  account. First candidates: product callout (pointer + name + price), list cards ("3 mistakes"),
  before/after wipe, ingredient chips, counter/timer, glitch accent word, sparkle/circle around the product,
  CTA end card with logo, full-screen insert card.
- Bespoke graphics are a normal option when an idea calls for one; a bespoke graphic that works is promoted
  into the brand's library.
- In the editable project every graphic is its own alpha clip.

## Consequences

- Templates are a quality tool, not only a cost saver: polished, consistent, recognisable brand look.
- Generative video models are out of scope for now; revisit only with a concrete use case and brand approval.

## Notes

- 2026-10-20: the "glitch accent word" candidate is limited to at most one per reel, for a deliberate "error"
  beat (playbook 2.22).
