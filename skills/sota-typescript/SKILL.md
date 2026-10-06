---
name: sota-typescript
description: >-
  State-of-the-art TypeScript and JavaScript engineering (2026) for writing
  and auditing TS/JS code. Covers runtime and toolchain selection (Bun, Node,
  Deno), package and tsconfig setup, Biome and type-check gates, monorepo
  workspaces, strict typing and boundary validation, ESM/CJS and language
  pitfalls, promises and cancellation, npm supply-chain and injection
  hardening, measured performance work, and runner mechanics for bun test and
  vitest. Use for TypeScript or JavaScript source, package.json, tsconfig,
  biome/eslint config, bunfig, lockfiles, monorepos, reviews, modernization,
  debugging, or security audits. Triggers: TypeScript, JavaScript, .ts, .tsx,
  .js, .mjs, Bun, Node.js, Deno, npm, pnpm, yarn, package.json, tsconfig,
  tsc, Biome, ESLint, Prettier, ESM, CJS, vitest, bun test, workspaces.
license: MIT
metadata:
  source: local synthesis from TypeScript, Bun, Node.js, and Biome documentation
  maintained-for: opencode
---

# SOTA TypeScript (2026)

## Local integration policy

Read `AGENTS.md`, `package.json`, the lockfile, `tsconfig.json`, the
formatter/linter config, and CI before changing code. For a **new** project the
defaults are Bun for runtime and package management, Biome for lint and format,
and `tsc --noEmit` as a separate type gate.

Preserve an **established** project's runtime, package manager, module format,
lint/format stack, and test runner unless migration is requested. A working
Node + pnpm + ESLint + Prettier + Vitest repository is a normal, supported
setup — it is not an audit finding, and neither is Deno, Yarn, npm workspaces,
Nx, or Turborepo. Findings are defects, not tooling preferences.

Verify current TypeScript, Bun, Node, and Biome releases and their config
schemas from the primary references below rather than trusting version numbers
or config keys embedded in these rules; this ecosystem's majors move fast and
config formats break across them.

This skill owns TypeScript/JavaScript semantics, tooling, and runner syntax.
`sota-testing` owns language-neutral test strategy, doubles, test data, and
suite health. `sota-code-security` owns cross-language security architecture.
`deep-performance-audit` owns baseline/profile/equivalence methodology.
`debug-loop` owns debugging sequence.

## Purpose

This skill serves two modes:

- **BUILD**: write or modify production TypeScript/JavaScript to this standard.
- **AUDIT**: inspect existing TS/JS and report prioritized, evidenced findings.

Read this file fully, then load only the relevant files under `rules/`. Every
rule file ends with an audit checklist. Those commands produce leads; read the
code and trace data flow before reporting a finding.

## Quick start (new project)

```bash
bun init                                  # scaffolds package.json + tsconfig
bun add -d @biomejs/biome typescript @types/bun
bunx biome init

bun run src/index.ts                      # execute TS directly, no build step
bunx tsc --noEmit                         # type gate
bunx biome check --write .                # lint + format + import sort
bun test                                  # built-in runner
```

Details, and the equivalents for established Node/pnpm projects, are in
[rules/01](rules/01-tooling-project-setup.md).

## BUILD mode

1. **Establish the compatibility contract.** Inspect the runtime and its
   version, `package.json` `type`/`engines`/`exports`, `moduleResolution`, and
   the lockfile. Write only syntax and APIs the declared floor supports. Match
   the project's module format; do not introduce a second one.
2. **Make types load-bearing.** `strict` plus `noUncheckedIndexedAccess` are
   the floor. Model domain values as distinct types, not `string`. `any` is a
   boundary escape hatch that must be narrowed from `unknown` immediately, and
   a type assertion is never validation.
3. **Parse untrusted input at the boundary.** Network, filesystem, env, CLI,
   and IPC payloads are `unknown` until a schema validator produces a typed
   value. Inferred types from a validator beat hand-written interfaces that
   silently drift.
4. **Own every promise.** No floating promises, no unhandled rejections, a
   timeout and an `AbortSignal` path on every external await, and cancellation
   propagated rather than ignored. Reject with `Error`, and preserve `cause`.
5. **Keep risky behavior explicit.** No `eval`/`new Function` on runtime data,
   no unvalidated path joins, no user-controlled URLs fetched without an
   allowlist, no untrusted key merge into an object literal, no secrets in
   client bundles.
6. **Test behavior.** Use the project's existing runner; add tests for error
   paths, boundary parsing, and cancellation. Load `sota-testing` when writing
   non-trivial logic — this skill only owns the runner mechanics
   ([rules/07](rules/07-frameworks-testing.md)).
7. **Verify with the project's gates.** At minimum type-check, lint/format, and
   run affected tests before claiming done. New-project defaults are
   `biome check .`, `tsc --noEmit`, and `bun test`. Bundlers do not type-check;
   the type gate is always a separate command.

## AUDIT mode

1. **Recon first.** Inventory runtime and version, package manager and
   lockfile, module format, `tsconfig` strictness, lint/format config and
   whether CI runs it, test runner, frameworks, and the trust boundaries
   (HTTP handlers, deserializers, subprocess and filesystem calls).
2. **Run the configured gates before supplemental tools.** The repository's own
   type-check, lint, and test commands are authoritative. Do not impose a new
   profile on a legacy repository and report the resulting noise as findings.
3. **Apply the relevant checklists.** Treat `rg` and linter output as a heat
   map. Confirm reachability and attacker control before escalating severity.
4. **Separate defects from preferences.** Report unsound types at boundaries,
   unhandled rejections, injection, prototype pollution, lockfile drift, and
   ESM/CJS breakage. Do not inflate formatting, package-manager, or framework
   choices into defects.
5. **Report evidence and confidence.** Quote the line, name the concrete
   failure mode, and distinguish a traced data flow from a pattern that still
   needs tracing.

### Severity conventions

| Severity | Meaning | Examples |
|---|---|---|
| CRITICAL | Direct compromise or destructive corruption | `eval`/`new Function` on request data, command injection via `exec`, prototype pollution reaching a sink, secret shipped in a client bundle |
| HIGH | Realistic exploit or production-breaking correctness failure | unvalidated input typed by assertion, path traversal, SSRF on a user-supplied URL, unhandled rejection crashing the process, floating promise dropping writes, lockfile not enforced in CI |
| MEDIUM | Latent defect or materially weakened defense | `any` at a trust boundary, missing timeout/cancellation on external I/O, `noUncheckedIndexedAccess` off, ESM/CJS interop landmine, type gate absent from CI, swallowed error without `cause` |
| LOW | Maintainability or hygiene risk | duplicated tsconfig instead of `extends`, unused exports, non-null assertions in ordinary code, `enum`/`namespace` in new code, lint config not enforced in CI |
| INFO | Useful observation without required action | toolchain consolidation opportunity, dependency that could be dropped for a platform API |

Severity scales with attacker control, privilege, reachability, and blast
radius. Confidence is **confirmed** when the flow was traced and **suspected**
when more evidence is required.

### Finding format

```text
[SEVERITY/confidence] short title
  Where: path/to/file.ts:42 (module/function)
  Issue: defect and relevant data or control flow
  Impact: concrete exploit, failure, compatibility, or operational cost
  Evidence: offending code and any observed behavior
  Fix: smallest specific correction; cite rules/NN section
  Effort: trivial | small | medium | large
```

Group findings by severity. End with commands run, rule files applied,
explicitly clean areas, and anything not reviewed.

## Rules index

| File | Read this when... |
|---|---|
| [rules/01-tooling-project-setup.md](rules/01-tooling-project-setup.md) | Choosing a runtime or package manager; editing package.json, tsconfig, biome/eslint config, bunfig.toml, lockfiles, workspaces, project references, build or publish setup, or CI gates |
| [rules/02-types-and-correctness.md](rules/02-types-and-correctness.md) | Designing types and public APIs; strict-flag decisions, `unknown` narrowing, discriminated unions, branded types, generics, `satisfies`, declaration files, or schema validation at trust boundaries |
| [rules/03-idioms-and-pitfalls.md](rules/03-idioms-and-pitfalls.md) | Writing general TS/JS; ESM/CJS interop, module resolution, equality and coercion, dates and numbers, collections, immutability, error design, or platform APIs versus dependencies |
| [rules/04-async-and-concurrency.md](rules/04-async-and-concurrency.md) | Anything with `async`; promise combinators, floating promises, cancellation and `AbortSignal`, timeouts, streams and backpressure, workers, event-loop blocking, or graceful shutdown |
| [rules/05-security-supply-chain.md](rules/05-security-supply-chain.md) | Handling untrusted input, URLs, paths, subprocesses, templates, or deserialization; secrets, prototype pollution, npm dependency and lockfile hygiene, install scripts, or provenance |
| [rules/06-performance.md](rules/06-performance.md) | Investigating latency, throughput, memory, bundle size, startup, or serial awaits; benchmarking, profiling, or validating a performance claim |
| [rules/07-frameworks-testing.md](rules/07-frameworks-testing.md) | Writing or running tests and framework code: bun test / vitest mechanics, mocking and fake timers, coverage configuration, type-level tests, e2e wiring, and framework-specific traps. **Test strategy — suite shape, TDD, doubles, test data, flake policy — lives in `sota-testing`; load it for any build that writes logic. This file owns TypeScript runner mechanics only.** |

## Top-10 non-negotiables

1. **`strict: true` plus `noUncheckedIndexedAccess`.** `any` appears only at an
   unavoidable boundary and is narrowed from `unknown` immediately; a type
   assertion is not validation. (rules/02)
2. **Untrusted input is parsed into a typed value at the boundary.** Network,
   env, filesystem, CLI, and IPC data are `unknown` until a schema validates
   them. (rules/02, 05)
3. **No floating promises.** Every external await has a timeout and an
   `AbortSignal` path; cancellation propagates instead of being dropped.
   (rules/04)
4. **Reject with `Error` and preserve `cause`.** No empty `catch`, no
   stringly-typed failures, no swallowed rejection. (rules/03, 04)
5. **The lockfile is committed and installed frozen in CI.** New dependencies
   are justified against a platform API; install scripts are reviewed.
   (rules/01, 05)
6. **Type-checking is its own CI gate.** Bundlers and dev servers strip types
   without checking them; `tsc --noEmit` must run separately. (rules/01)
7. **One canonical tsconfig base; packages `extends` it and declare only their
   delta.** The same rule applies to lint config. (rules/01)
8. **Never build a shell string, a filesystem path, or an outbound URL from
   untrusted data.** Use argument arrays, resolve-then-verify containment, and
   allowlists. (rules/05)
9. **Test code is production code** — same lint rules, same review bar, no
   blanket `any` amnesty in test overrides. (rules/07)
10. **No performance claim without a benchmark and no optimization without a
    profile;** measure before and after on representative work. (rules/06)

## Primary references

- https://www.typescriptlang.org/tsconfig/
- https://www.typescriptlang.org/docs/handbook/modules/reference.html
- https://bun.com/docs
- https://nodejs.org/docs/latest/api/
- https://biomejs.dev/guides/getting-started/
- https://github.com/tc39/proposals
