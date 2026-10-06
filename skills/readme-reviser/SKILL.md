---
name: readme-reviser
description: Revise the README and other project documentation so it describes the current state of the code, written as if it had always been that way. Use when docs have drifted behind the code — after shipping a feature, renaming a flag, changing install or config steps, or when asked to "update the readme", "revise docs", "sync documentation", or "fix stale docs". Not for release notes or changelogs (use changelog-generator), and not for authoring AGENTS.md.
---

# Readme Reviser

Bring documentation back in line with the code, in timeless voice: the docs must read as though the current behavior was always the behavior.

A changelog is change-relative and dated. A README is state-relative and timeless. If the project keeps a CHANGELOG, the change narrative goes there — not here.

## When to Use This Skill

- Docs pass after shipping a feature or renaming an interface
- Pre-release audit of README, install steps, and usage examples
- Docs contradict the code and need reconciling

## When NOT to Use This Skill

- Writing release notes or a changelog — use `changelog-generator`
- Documenting a project that has no docs yet — run `deep-project-primer` first
- A single typo or dead link — just fix it

## 1. Establish the change set

If the user names a range, tag, or branch, use it. Otherwise default to everything since the docs were last touched, and say so in the report.

```bash
git log -1 --format=%H -- README.md   # last time the README moved
git log --oneline <sha>..HEAD         # what shipped since
git diff --stat <sha>..HEAD
git status --short                    # uncommitted work counts too
```

## 2. Map documentation targets

In priority order: `README.md` → `docs/**` → `CONTRIBUTING.md` / `INSTALL.md` → `examples/**` → agent instruction files → man pages.

- **Generated blocks are off limits.** Look for `<!-- generated -->` markers or a generator script; regenerate instead of hand-editing.
- **Source-embedded docs are flag-only.** CLI `--help` strings, docstrings, and usage text live in code. Report drift there; never edit it. A docs pass must not change program behavior.

## 3. Revise in three directions

Doc drift is bidirectional. Adding what's new is only a third of the job.

- **Add** — new commands, flags, config keys, requirements, endpoints, prerequisites.
- **Correct** — renamed flags, changed defaults, moved paths, bumped versions and badges, altered install or config steps.
- **Remove** — deleted features, obsolete workarounds, dead links, and `TODO` / "coming soon" items that have since shipped.

## 4. Write in timeless voice

| Don't write | Write |
|-------------|-------|
| "We've added a `--json` flag" | "`--json` prints machine-readable output." |
| "Config is now stored in XDG dirs" | "Config lives in `$XDG_CONFIG_HOME/foo/`." |
| "New in v2: workspaces" | "Workspaces group related projects." |
| "This replaces the old `--format` option" | *(delete — the old option no longer exists)* |
| "Previously this required Docker" | *(delete — describe only what's required now)* |

No dates, no version labels as feature headings, no first-person change narration.

## 5. Verify before finishing

- Every documented command exists — check the project's task runner (`package.json` scripts, Makefile targets, `cabal run`, `cargo run -- --help`, `<cli> --help`).
- Every documented flag and config key appears in the code.
- Relative links and file paths resolve.
- Fenced code blocks carry a language tag consistent with the rest of the file.

## Scope guardrails

Surgical edits only. Match the existing heading depth, tone, and formatting. Don't restructure or reorder sections, don't add marketing adjectives, don't add sections nobody asked for, and touch only the docs the change set actually affects.

## Report

Close with three parts:

1. **Revised** — one line per file, what changed.
2. **Left alone** — docs deliberately untouched, and why.
3. **Flagged** — suspected-stale items that couldn't be verified, plus any source-embedded drift. Flag them; never guess.
