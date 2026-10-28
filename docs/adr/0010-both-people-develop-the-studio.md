# 0010 — Both people develop the studio

Status: Accepted (2026-10-28). Supersedes the creator lock-down of the 2026-10-20 content-studio design
(`docs/superpowers/specs/2026-10-20-content-studio/marina-layer.md`) and ADR-0002's "brand onboarding is a one-time
session on the developer's account" (either Mac onboards a brand).

## Context

The first handover gave Marina's Mac a "creator mode": deny rules for git commits and pushes, code edits, setup and
deletions; corrections kept in a gitignored `learned/` until the developer promoted them. It followed CONTEXT.md's
"the creator only runs the finished tool". The developer rejected it: Marina should be able to improve the studio
with her own Claude exactly as he does.

## Decision

- Same rights on both Macs: either person makes reels, changes any file, commits and pushes to `main`.
- `CLAUDE.local.md` with `Person: Marina` only changes how Claude talks: Ukrainian, plain words, every command run
  by Claude, changes explained by their effect. There is no per-person deny list; `.claude/settings.local.json` is
  personal and untouched by the repository.
- Shared discipline instead of locks: `git pull --rebase` before a change, selftest and unit tests before a push,
  small commits, no force push, `main` must run on her M1 with 8 GB (CLAUDE.md "Changing the studio").
- `learned/` is tracked: corrections from a reel are committed and reach the other Mac with the next pull.
- Deleting files asks on both Macs: the shared `.claude/settings.json` has an ask rule for `cleanup.py apply`, and
  selftest checks that no allow rule matches it.

## Consequences

- Both Macs can push conflicting changes; `git pull --rebase` and small commits keep that manageable.
- A change by either person can break the other's reels; selftest, the unit tests and a check draft before a push
  are the guard, and `git revert` the way back.
- Marina's Mac needs her own GitHub account with collaborator access (`INSTALL.md` step 9). A Mac set up before
  this decision drops its old `.claude/settings.local.json` once (`INSTALL.md`, Updates).
