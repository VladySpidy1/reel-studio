# 0002 — A reel is Brand × Format + footage + brief

Status: Accepted (2026-10-10)

## Context

The creator works for 2–3 brands and shoots every genre (skits, tutorials, before/after, GRWM, reviews,
unboxings). "Being well-watched in the niche" cannot mean the model watching thousands of reels: it sees
frames and transcripts, not motion, and per-reel analysis is noisy. What actually varies is how a reel looks
(brand) and how it is cut (format), and these are independent.

## Decision

- **Brand** (`brands/<brand>/`): fonts, colours, subtitle animation, grade/LUT, music mood, SFX palette,
  logo/CTA, tone of voice, prohibitions, graphic templates, learned rules, "what worked" notes.
- **Format** (`formats/<format>/`): structure, pacing, hook placement, freezes, product holds, typical SFX
  moments, learned rules.
- **Universal grammar** covers any talking reel and ships first; specialised formats are onboarded as they
  appear (first reel of the genre + 2–3 competitor references).
- A new reel = brand + format + footage + brief. The tool asks for whatever the brief is missing, e.g. which
  brand.
- Brand onboarding (since ADR-0010 on either Mac) is a one-time session: brand book (when available) + 3–5 of the
  creator's best reels for that brand. A reference attached to a single reel is format onboarding, saved for
  reuse.

## Consequences

- The current TOSUMI code must be split: style into `brands/tosumi/`, the skit into `formats/skit-hoche-a/`,
  the rest into universal grammar. A second brand proves the split.
- Every creator correction lands in the brand or format file as a learned rule.
