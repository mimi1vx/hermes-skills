# 07 — Frameworks & Testing Mechanics

TypeScript runner and framework mechanics only. **Test *strategy* — suite
shape, what to test, TDD, doubles discipline, test data, coverage philosophy,
flake policy — lives in `sota-testing`; load it for any build that writes
logic.** This file tells you which buttons to press; that skill tells you what
to build.

## 7.1 Choosing a runner

| Runner | Use when |
|---|---|
| **`bun test`** | Bun projects. Fast, zero-config, Jest-compatible API, built-in coverage and DOM-free component testing |
| **Vitest** | Vite-based frontends (shares the Vite transform pipeline and config), or when you need browser mode / workspace features |
| **`node:test`** | Node projects that want zero dependencies and are happy with a smaller matcher set |
| **Jest** | Established Jest suites. Migrating a working Jest suite is a project, not a cleanup — do not propose it unasked |

Bun's API is Jest-compatible and also exposes a `vi` alias, so most Jest and
Vitest tests port without rewriting mocks. That compatibility is a migration
aid, not a reason to migrate.

## 7.2 `bun test` mechanics

```bash
bun test                          # discovers *.test.ts, *.spec.ts, *_test.ts
bun test path/to/file.test.ts     # one file
bun test --watch
bun test -t "rejects expired"     # filter by test name
bun test --coverage
bun test --bail                   # stop at first failure (local loop)
```

```ts
import { describe, test, expect, beforeEach, afterEach } from "bun:test";

describe("RateLimiter", () => {
  test("rejects the request that exceeds the limit within the window", () => {
    // ...
  });
});
```

- Import from `bun:test` explicitly. Globals may work, but explicit imports
  keep the file honest about what it depends on and survive a runner change.
- Lifecycle hooks are `beforeAll`/`beforeEach`/`afterEach`/`afterAll`. Teardown
  belongs in `afterEach` so it runs on failure too.
- Shared setup goes in a preload module (7.3), not copy-pasted per file.

## 7.3 Doubles: the mechanics

`sota-testing` rules/03 decides *what* may be doubled — boundaries you own,
never internals, never types you don't own. This section is only *how*.

```ts
import { mock, spyOn, expect, test, afterEach } from "bun:test";

const charge = mock(async (amount: number) => ({ id: "ch_1", amount }));

const spy = spyOn(gateway, "charge");        // wraps, keeps the real impl
spy.mockResolvedValue({ id: "ch_1" });       // ...unless you override it

afterEach(() => {
  mock.restore();          // restores spied originals
  mock.clearAllMocks();    // clears call history, keeps implementations
});
```

| Call | Effect |
|---|---|
| `mock.clearAllMocks()` | clears `.mock.calls`/`.results`; implementations survive |
| `jest.resetAllMocks()` | also drops implementations set by `mockImplementation`/`mockReturnValue` |
| `mock.restore()` | restores originals replaced by `spyOn`; does **not** undo `mock.module()` |

**Module mocks and import-time side effects.** `mock.module(specifier,
factory)` overrides a module even after it has been imported, and ESM live
bindings update — but *the original module has already been evaluated by then*,
so its top-level side effects (opening a connection, registering a handler,
reading env) have already happened. To prevent evaluation entirely, register
the mock in a preload:

```toml
# bunfig.toml
[test]
preload = ["./test/setup.ts"]   # calls mock.module(...) before any test imports
```

- Put the `afterEach` restore in that preload rather than repeating it in every
  file.
- **Bun has no `__mocks__` directory and no auto-mocking.** Suites ported from
  Jest that rely on either need explicit `mock.module` calls.
- Prefer constructor/parameter injection of a fake over module mocking. Module
  mocking reaches around the module graph; a fake passed in is visible in the
  test's arrange block and survives refactors.

## 7.4 Determinism levers

`sota-testing` rules/02 §2.6 requires that a test consume only inputs it
controls. In TypeScript that means:

```ts
import { setSystemTime, afterEach } from "bun:test";

setSystemTime(new Date("2026-06-12T12:00:00.000Z"));
afterEach(() => setSystemTime());   // back to real time
```

- **`bun test` runs in UTC (`Etc/UTC`) by default** — the correct default, and
  it means a passing suite says nothing about local-timezone behavior. Exercise
  other zones deliberately with `TZ=America/New_York bun test` or by setting
  `process.env.TZ` in the test.
- Unlike Jest, `bun:test`'s `useFakeTimers` leaves the `Date` constructor
  identity intact, so `instanceof Date` and `Date === Date` still hold.
- Injecting a clock parameter still beats mutating global time. Reserve
  `setSystemTime` for code you cannot thread a clock through.
- Randomness: inject the generator or seed it. Never assert on a `crypto
  .randomUUID()` value — assert on shape, or inject the generator.
- Network: no unit test touches a socket. Integration tests talk only to
  dependencies the suite started itself (7.7).

## 7.5 Coverage mechanics

```toml
# bunfig.toml
[test]
coverage = true
coverageReporter = ["text", "lcov"]     # lcov.info for CI services
coverageDir = "coverage"
coveragePathIgnorePatterns = ["src/generated/**", "**/*.config.ts"]
```

`coverageThreshold` accepts a number or `{ lines, functions, statements }` and
fails the run when unmet.

**Use it as a ratchet, not a target.** Store the currently measured value and
raise it when it improves; never pick a round number and write tests to reach
it. A flat `coverageThreshold = 0.8` is precisely the gamed global gate
`sota-testing` rules/07 §7.2 warns against — it manufactures assertion-light
tests on easy code while risky code stays bare. Read the uncovered lines on the
diff; that is the part that finds bugs.

Exclude generated and vendored code from measurement, or the number inflates
and buries the signal.

## 7.6 Type-level tests

Types are behavior; a public generic that infers wrongly is a bug that no
runtime test catches.

```ts
import { expectTypeOf } from "expect-type";   // or vitest's built-in

expectTypeOf(parseConfig).returns.toEqualTypeOf<Config>();
expectTypeOf<Branded<string>>().not.toEqualTypeOf<string>();

// @ts-expect-error — id must be branded, a bare string must not compile
getUser("raw-string");
```

- `@ts-expect-error` **is** an assertion: it fails the type-check if the line
  stops erroring. That makes it the cheapest negative type test available.
- A bare `@ts-ignore` asserts nothing and hides regressions — ban it in favor
  of `@ts-expect-error` with a comment.
- Type tests run under `tsc --noEmit`, not the test runner. They belong in the
  type gate (`rules/01` §1.4).

## 7.7 Integration test mechanics

- **Exercise your HTTP app through its real handler**, not by calling the
  controller function. Modern TS frameworks expose the app as a
  `Request → Response` function, so a full-stack request test needs no port
  and no server lifecycle:

```ts
const res = await app.fetch(new Request("http://x/orders/42", {
  headers: { authorization: `Bearer ${tokenFor(otherTenant)}` },
}));
expect(res.status).toBe(404);          // authz negative test, no network
```

  This runs routing, middleware ordering, serialization, and auth — where the
  expensive bugs live — at unit-test speed.
- **Real dependencies in containers**, per `sota-testing` rules/04:
  Testcontainers has a Node package that works under Bun and Node; pin the
  image to the production version, let the library assign the port, and start
  one container per suite with per-test isolation inside it.
- Never hardcode `localhost:5432`. It couples the suite to the machine and
  breaks parallelism.

## 7.8 E2E wiring

Playwright is the default for browser e2e. This file owns wiring only —
selector strategy, critical-path selection, auto-waiting, and the deletion
discipline are `sota-testing` rules/05.

- Run e2e as a **separate command and CI stage** from `bun test`; they have
  different budgets, different flake profiles, and different failure artifacts.
- Turn on trace/video/screenshot on failure in CI. An e2e failure that can only
  be reproduced locally costs hours.
- Arrange via API or a seeded session cookie, act and assert through the UI.

## 7.9 Framework traps

- **React / Testing Library**: query by role and accessible name; `getByTestId`
  is the fallback, not the default. `userEvent` over `fireEvent` — it models
  real interaction sequences. Never assert on component internals or state;
  assert on what the user can observe.
- **Hono / Elysia / modern Node frameworks**: test through `app.fetch` (7.7).
  Assert status plus the contract-relevant fields, not whole-body equality —
  additive response fields must not break tests.
- **Express / Koa**: use the framework's supertest-style client so middleware
  ordering is exercised; calling the handler with a fake `req`/`res` skips
  exactly the layer that breaks.
- **Next.js / SSR frameworks**: server components and route handlers are
  plain async functions — test them directly. Reserve the framework's test
  harness for the rendering behavior that genuinely needs it.
- **Any framework**: a test that mounts the whole app to check one pure
  function is a slow-poke at the wrong layer (`sota-testing` rules/02 §2.7).

## 7.10 Test code is production code

Same lint rules, same type strictness, same review bar. Concretely:

- **No lint or type amnesty for `*.test.ts`.** A config override disabling
  `noExplicitAny` in tests creates a weaker standard for the code that is
  supposed to be the safety net, and `any` in a test is how an assertion
  silently stops checking anything.
- Test helpers and builders are reviewed like library code: valid defaults,
  narrow surface, no inheritance trees.
- A merged test with no assertion is worse than no test.

## Audit checklist

- [ ] Test files with no assertion:
      `rg --files-without-match -e 'expect\(|assert' --glob '**/*.{test,spec}.ts' .`
      → CRITICAL each.
- [ ] Type/lint amnesty in tests:
      `rg -n -B2 -A6 '(test|spec)\.(ts|tsx)' biome.json* .eslintrc* | rg -n 'off|noExplicitAny'` → MEDIUM.
- [ ] Bare `@ts-ignore` (asserts nothing) vs `@ts-expect-error`:
      `rg -n '@ts-ignore' --glob '**/*.{ts,tsx}'` → LOW–MEDIUM each.
- [ ] Real time in tests: `rg -n 'new Date\(\)|Date\.now\(\)' --glob '**/*.{test,spec}.ts'`
      without `setSystemTime`/injected clock → HIGH (boundary flakes).
- [ ] Hard sleeps as synchronization:
      `rg -n 'setTimeout\(.*\b(resolve|done)\b|Bun\.sleep\(|waitForTimeout|page\.waitForTimeout'`
      in test paths → HIGH each.
- [ ] Mocks of modules you don't own:
      `rg -n "mock\.module\(['\"][^./]" --glob '**/*.{test,spec}.ts'` → HIGH
      (wrap the dependency in your own port and fake that — `sota-testing` rules/03 §3.3).
- [ ] Module mocks registered after import with no preload:
      `mock.module` inside test files while `rg -n 'preload' bunfig.toml` is empty →
      MEDIUM (original side effects already ran).
- [ ] Missing mock cleanup: no `mock.restore()`/`clearAllMocks` in an
      `afterEach` or preload → MEDIUM (state leaks between tests).
- [ ] Ported Jest suite relying on unsupported features:
      `rg -n '__mocks__|jest\.mock\(' --glob '**/*.{test,spec}.ts'` in a Bun repo
      → HIGH (silently not mocking).
- [ ] Flat coverage gate: `rg -n 'coverageThreshold' bunfig.toml` with a round
      number and no ratchet history → MEDIUM.
- [ ] Generated code included in coverage: no `coveragePathIgnorePatterns`
      while `src/generated` exists → LOW.
- [ ] Hardcoded infrastructure endpoints:
      `rg -n 'localhost:(5432|3306|6379|9092|27017)' --glob '**/*.{test,spec}.ts'` → HIGH.
- [ ] Whole-body response equality:
      `rg -n 'toEqual\(\s*\{' --glob '**/*api*.{test,spec}.ts'` → MEDIUM (brittle
      to additive fields).
- [ ] Protected routes without a 401/403 test: sample 5 authenticated routes
      against the test files → HIGH on sensitive routes (`rules/05`).
- [ ] E2E sharing the unit-test command/stage, or no failure artifacts
      configured in CI → MEDIUM.
- [ ] Structural selectors in e2e:
      `rg -n 'querySelector\(|nth-child|\.css-[a-z0-9]' --glob 'e2e/**/*.ts'` → MEDIUM.
