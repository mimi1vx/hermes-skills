# 03 — Idioms & Pitfalls

JavaScript semantics that TypeScript does not save you from, plus the module
system that causes more lost hours than anything else in the ecosystem.

## 3.1 ESM/CJS and module resolution

Most "cannot find module" and "X is not a function" failures are one of four
mismatches: the package's format, your `type` field, your `moduleResolution`,
and the runtime's resolver.

- **Decide the format once.** `"type": "module"` in `package.json` means `.js`
  files are ESM. Omitting it means CJS. Mixed repos need `.mjs`/`.cjs`
  extensions to disambiguate, which is a tax — pick ESM for new code.
- **ESM specifiers are exact.** No extensionless imports, no implicit
  `/index.js`. Under `moduleResolution: "bundler"` you may omit extensions
  because a bundler resolves them; under `nodenext` you may not. Choose the one
  matching how the code actually runs.
- **Set `moduleResolution` to what runs your code**: `bundler` for
  bundler/Bun-executed code, `nodenext` for code Node resolves directly.
  Getting this wrong produces types that compile and imports that fail at
  runtime.
- **You cannot `require()` an ESM-only package from CJS.** Use dynamic
  `import()`, or move the consumer to ESM. Newer Node versions relax this for
  some cases; do not rely on it across your supported range.
- **Default-import interop**: a CJS module's `module.exports` becomes the ESM
  default import. `esModuleInterop` smooths the TypeScript side but does not
  change runtime shape — `import * as x` on a CJS module gives you a namespace
  object, not a callable.
- **`verbatimModuleSyntax` requires `import type`** for type-only imports
  (`rules/01`). Without it, a transpiler can leave an import of a module that
  only ever provided a type, pulling real code — and its side effects — into
  the bundle.

## 3.2 Equality, coercion, nullish

- `===` always. The one sanctioned `==` is `x == null`, which tests `null` and
  `undefined` together.
- **`??` and `||` are different.** `||` falls back on every falsy value, so
  `port || 3000` turns a configured `0` into `3000` and `name || "anon"` turns
  `""` into `"anon"`. Use `??` unless you specifically mean "any falsy value".
- **`?.` short-circuits the whole chain**, and `a?.b.c` still throws if `a` is
  present but `b` is not. Optional chaining is not a blanket safety net.
- `NaN !== NaN`; use `Number.isNaN`. `typeof null === "object"`; check
  `x === null` explicitly. `Array.isArray` for arrays — `typeof []` is
  `"object"`.
- Never rely on implicit `toString`/`valueOf` for domain logic; template
  literals will happily interpolate `[object Object]`.

## 3.3 Numbers and money

`number` is an IEEE-754 double. `0.1 + 0.2 !== 0.3`, and integers above
`Number.MAX_SAFE_INTEGER` lose precision silently.

- **Never represent money as a float.** Store and compute in minor units as
  integers (`Cents`, branded per `rules/02` §2.5), or use a decimal library.
  Format only at the presentation edge with `Intl.NumberFormat`.
- **`BigInt` for identifiers and counters that exceed 2^53** — database
  bigint keys, Snowflake ids, nanosecond timestamps. Note `JSON.stringify`
  throws on `BigInt`; serialize as a string deliberately.
- **JSON round-trips lose precision** on large integers: `JSON.parse` produces
  a `number`. If an upstream API sends 64-bit ids, parse them as strings.
- Guard division by zero and validate parsed numbers: `Number("")` is `0` and
  `parseInt("12abc")` is `12`. Prefer `Number()` plus an explicit
  `Number.isFinite` check, or a schema coercion (`rules/02` §2.7).

## 3.4 Dates and time

`Date` is a mutable, timezone-lossy wrapper around a millisecond timestamp,
with a parser that accepts non-ISO strings inconsistently across engines.

- **Store and transport UTC ISO-8601 strings or epoch millis.** Convert to a
  local zone only for display.
- **`new Date("...")` only with a full ISO-8601 string.** Date-only strings
  (`"2026-06-12"`) parse as UTC midnight, while `"2026/06/12"` parses as local
  midnight — a silent off-by-one-day across half the world's timezones.
- **A timestamp is not a calendar date.** "The user's birthday" and "the
  billing day of month" are calendar concepts; storing them as instants
  produces the classic day-shift bug.
- **Never compute with `86400000`.** Days are not always 24 hours (DST). Use a
  date library or `Temporal` where available.
- **Temporal** (immutable, explicit-zone, calendar-aware) is the direction the
  platform is going. Prefer it where your runtime ships it; otherwise use a
  maintained immutable date library and keep the conversion at the boundary.
- Inject the clock rather than calling `Date.now()` deep in domain logic — the
  testability argument is `sota-testing` rules/02 §2.6, the mechanics are
  `rules/07` §7.4.

## 3.5 Strings and Unicode

- **`"".length` counts UTF-16 code units**, not characters. Emoji, many CJK
  characters, and combining sequences count as 2+. Truncating by `length`
  splits surrogate pairs and produces replacement characters.
- Iterate with `for...of` or `[...str]` for code points; use `Intl.Segmenter`
  for user-perceived characters (graphemes) when you need real "characters".
- **Normalize before comparing or storing** identifiers that come from users:
  `str.normalize("NFC")`. Two visually identical strings can differ byte-wise.
- Case-insensitive comparison is locale-dependent (`toLowerCase` on Turkish
  `İ`); use `localeCompare` with explicit options for ordering, and prefer
  case-*sensitive* exact matching for security decisions.
- Building a regex from user input requires escaping — an unescaped
  user-supplied pattern is a ReDoS vector (`rules/05`).

## 3.6 Collections and iteration

- **`Map` over a plain object** for a keyed collection: any key type,
  insertion-ordered, `size`, no prototype collisions (`__proto__` as an object
  key is a real hazard — `rules/05` §5.4). Use objects for fixed-shape records.
- **`Set` for membership.** `arr.includes` inside a loop is a quadratic
  algorithm hiding as idiomatic code.
- **Object key order is specified but surprising**: integer-like keys sort
  numerically first. Never depend on insertion order for object keys — use a
  `Map`.
- **Prefer non-mutating array methods** (`toSorted`, `toReversed`, `with`,
  `toSpliced`) over the in-place versions. `arr.sort()` mutates the caller's
  array, and `sort()` without a comparator sorts lexicographically —
  `[10, 9].sort()` is `[10, 9]`.
- Chained `map/filter/reduce` over large arrays allocates an intermediate array
  per stage; that is fine until it is a hot path (`rules/06`).
- `Object.groupBy` / `Map.groupBy` replace hand-rolled reduce-into-object
  grouping where available.

## 3.7 Error design

- **Throw `Error` (or a subclass), never a string or object literal.** Only
  `Error` carries a stack; `catch (e)` on a thrown string gives you nothing to
  debug.
- **Preserve the chain with `cause`:**

```ts
class RepositoryError extends Error {
  constructor(message: string, options?: { cause?: unknown }) {
    super(message, options);
    this.name = "RepositoryError";
  }
}

try {
  await db.query(sql);
} catch (cause) {
  throw new RepositoryError("failed to load order", { cause });
}
```

- **`catch` variables are `unknown`.** Narrow with `instanceof Error` before
  reading `.message`; a thrown non-Error is otherwise stringified as
  `[object Object]` in your logs.
- **Never swallow.** An empty `catch {}` deletes evidence. If a failure is
  genuinely ignorable, log it at debug level with a comment saying why.
- **Distinguish expected outcomes from exceptions.** "User not found" is a
  return value; "the database socket died" is an exception. Modelling expected
  failures as a result union (`rules/02` §2.4) makes the caller handle them;
  throwing for control flow makes them invisible.
- Subclass per subsystem with a discriminant field so callers can branch
  without string-matching messages. Error messages are not an API — codes are.

## 3.8 Structure: classes, closures, and data

- **Plain data plus functions** is the default. Reach for a class when you have
  invariants to protect across mutations, or a lifecycle to own.
- **Do not create a class to hold zero state.** A "service" whose methods never
  touch `this` is a module with extra ceremony.
- **`this` is dynamically bound.** Passing `obj.method` as a callback loses the
  receiver; use an arrow property or bind explicitly. This is a runtime bug the
  type checker does catch — do not silence it.
- Prefer composition and explicit dependency parameters over inheritance;
  constructor injection is also what makes the code testable without module
  mocking (`rules/07` §7.3).
- `#private` fields are enforced at runtime; TypeScript's `private` is
  erased and reachable from JavaScript. Use `#` when the boundary matters.

## 3.9 Platform APIs beat dependencies

The standard library absorbed most of the small-utility ecosystem. Before
adding a dependency, check for: `fetch`, `URL`/`URLSearchParams`,
`structuredClone`, `AbortController`, `crypto.randomUUID` and
`crypto.subtle`, `Intl.*` (dates, numbers, plurals, lists, segmentation),
`Object.groupBy`, `Array.prototype.at`, `Promise.withResolvers`, and
`node:util.parseArgs` for CLIs.

Each removed dependency is one less supply-chain entry (`rules/05` §5.6), one
less version to bump, and usually faster. Do keep a dependency when it encodes
real domain complexity — dates, decimals, and validation schemas earn their
place.

## 3.10 Newer language features

- **`using` / `await using`** (explicit resource management) makes cleanup
  lexical: a disposable's `[Symbol.dispose]`/`[Symbol.asyncDispose]` runs at
  scope exit, including on throw. Prefer it over `try/finally` chains for
  connections, file handles, and locks where your runtime supports it.
- **Decorators**: the TC39 standard decorators are a different feature from the
  legacy `experimentalDecorators` many frameworks still require. Do not enable
  both; follow whatever your framework specifies and do not introduce
  decorators into plain domain code.
- Verify feature availability against your declared runtime floor (`rules/01`
  §1.1) rather than the TypeScript version — TypeScript will happily compile
  syntax your production runtime cannot execute.

## Audit checklist

- [ ] Format mismatch: `"type": "module"` absent while sources use ESM
      syntax and are executed directly by Node → HIGH (runtime failure).
- [ ] `moduleResolution` not matching the runtime: `bundler` in a package Node
      resolves directly → HIGH.
- [ ] Extensionless relative imports under `nodenext`:
      `rg -n "from ['\"]\./[^'\"]*[^s]['\"]" --glob '**/*.ts'` cross-checked with
      tsconfig → HIGH.
- [ ] `||` used for defaulting where `0`/`""`/`false` are valid:
      `rg -n '\|\|\s*(0|""|\x27\x27|\[\]|\{\})' --glob '**/*.ts'` → MEDIUM.
- [ ] Loose equality: `rg -n '[^=!]==[^=]' --glob '**/*.ts'` excluding `== null`
      → LOW–MEDIUM.
- [ ] Money as float: `rg -n '(price|amount|total|balance|cost)\s*:\s*number'`
      → HIGH if arithmetic is performed on them.
- [ ] Day arithmetic with magic constants:
      `rg -n '86400000|24 \* 60 \* 60|\* 1000 \* 60 \* 60 \* 24'` → MEDIUM (DST bugs).
- [ ] Non-ISO date parsing: `rg -n 'new Date\((?!\))' --pcre2` and inspect the
      argument shapes → MEDIUM for date-only or slash-separated strings.
- [ ] Naive string truncation on user text:
      `rg -n '\.slice\(0,\s*\d+\)|\.substring\(0,\s*\d+\)'` on rendered strings
      → LOW–MEDIUM (splits grapheme clusters).
- [ ] Thrown non-Errors: `rg -n 'throw (?!new )' --pcre2 --glob '**/*.ts'` → MEDIUM.
- [ ] Swallowed errors: `rg -n 'catch\s*(\([^)]*\))?\s*\{\s*\}' --glob '**/*.ts'`
      → MEDIUM each.
- [ ] Lost causes: `rg -n 'throw new \w+Error\(' -A1` without `cause` where the
      throw is inside a `catch` → MEDIUM (debugging blind spot).
- [ ] Error-message string matching as control flow:
      `rg -n '\.message\s*(===|\.includes\()' --glob '**/*.ts'` → MEDIUM (use codes).
- [ ] Mutating sorts on shared arrays: `rg -n '\.sort\(\)' --glob '**/*.ts'`
      → LOW (also lexicographic on numbers).
- [ ] Quadratic membership checks: `rg -n -B2 '\.includes\(' --glob '**/*.ts'`
      inside loops over large collections → LOW–MEDIUM (`rules/06`).
- [ ] Objects used as dynamic-key maps with user-controlled keys → HIGH
      (prototype pollution, `rules/05`).
- [ ] Dependencies duplicating platform APIs (uuid, node-fetch, lodash for
      one helper, date formatting) in a modern runtime → INFO–LOW.
