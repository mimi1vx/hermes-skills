# 02 — Types & Correctness

TypeScript's value is entirely in what it makes *impossible*. Every rule here
converts a runtime failure into a compile error. A codebase that types
everything as `any`, asserts with `as`, and disables checks has paid the whole
cost of TypeScript and bought nothing.

## 2.1 The strictness floor, and what to add above it

`strict: true` plus `noUncheckedIndexedAccess` is the floor (`rules/01` §1.3).
Above the floor, in rough order of value-per-annoyance:

| Flag | Catches | Cost |
|---|---|---|
| `exactOptionalPropertyTypes` | `{ a?: string }` silently accepting `{ a: undefined }` — the difference between "absent" and "explicitly nothing", which matters for PATCH semantics and object spreads | low; occasional explicit `\| undefined` |
| `noImplicitReturns` | a branch that forgets to return | low |
| `noUnusedLocals` / `noUnusedParameters` | dead code | prefer the linter here — it can autofix |
| `noPropertyAccessFromIndexSignature` | `config.someKey` on an index signature, where the key may not exist | medium; forces `config["someKey"]` |
| `erasableSyntaxOnly` | TS-only runtime syntax (`enum`, `namespace`, parameter properties) that runtimes stripping types cannot execute | low if you follow §2.10 anyway |

Adopt these on new projects. On an existing project, turn one on, fix the
fallout in its own commit, and move on — a strictness bump bundled into a
feature PR gets reverted.

**Never** ship `// @ts-nocheck`, a project-wide `strict: false`, or a `skipLibCheck`
added to silence your *own* declaration errors.

## 2.2 `unknown`, then narrow — never `any`

`any` disables checking for everything it touches and spreads silently through
every expression it participates in. `unknown` is the honest type for
"I don't know yet": it accepts anything and permits nothing until narrowed.

```ts
// BAD — every downstream access is unchecked; a typo compiles fine
function handle(payload: any) {
  return payload.user.emailAdress.toLowerCase();
}

// GOOD — the compiler forces the check that the runtime needs anyway
function handle(payload: unknown) {
  const parsed = PayloadSchema.parse(payload);   // §2.7
  return parsed.user.emailAddress.toLowerCase();
}
```

Narrowing tools, in preference order:

1. **Control-flow narrowing** — `typeof`, `instanceof`, `in`, truthiness,
   discriminant checks (§2.4). Free and always correct.
2. **Type predicates** — `function isUser(v: unknown): v is User` when the
   check is reusable. The predicate body is trusted, so it must actually check
   every field it claims.
3. **Assertion functions** — `function assertUser(v: unknown): asserts v is User`
   when failure should throw rather than branch.

`catch` variables are `unknown` under `strict` — narrow with
`e instanceof Error` before touching `.message` (§3.7).

## 2.3 A type assertion is not validation

`as` tells the compiler to stop arguing. It changes no runtime behavior and
checks nothing. `await res.json() as User` is the single most common way
untrusted data enters a "typed" codebase wearing a costume.

```ts
// BAD — this is a lie the compiler is required to believe
const user = (await res.json()) as User;

// GOOD — a real check that produces the type
const user = UserSchema.parse(await res.json());
```

Legitimate uses of `as` are narrow: widening to `unknown`, `as const`, and
telling the compiler something it structurally cannot know about a value *you*
just constructed. Everything else needs a runtime check.

**`satisfies` instead of a type annotation** when you want the check without
losing inference:

```ts
// annotation widens: routes.home is string
const routes: Record<string, string> = { home: "/", about: "/about" };

// satisfies checks AND keeps the literal types: routes.home is "/"
const routes = { home: "/", about: "/about" } satisfies Record<string, string>;
```

**Non-null `!`** is an assertion too. Acceptable immediately after a check the
compiler cannot see; a smell anywhere else, and a bug wherever the invariant
is actually violable.

## 2.4 Discriminated unions and exhaustiveness

Model alternatives as a union with a literal discriminant, not as one object
with optional fields for every case. The optional-fields version makes illegal
combinations representable and pushes the checking into your head.

```ts
// BAD — nothing stops { status: "success", error: "boom" }
type Result = { status: string; data?: Data; error?: string };

// GOOD — the compiler knows which fields exist in which branch
type Result =
  | { status: "success"; data: Data }
  | { status: "failure"; error: AppError };

function render(r: Result) {
  switch (r.status) {
    case "success": return show(r.data);      // r.error does not exist here
    case "failure": return show(r.error);
    default: return assertNever(r);           // exhaustiveness, checked at compile time
  }
}

function assertNever(x: never): never {
  throw new Error(`unhandled variant: ${JSON.stringify(x)}`);
}
```

`assertNever` is the payoff: adding a third variant turns every non-exhaustive
switch into a compile error instead of a silent fallthrough in production.

## 2.5 Branded types for domain values

Structural typing means every `string` is interchangeable. `UserId`,
`OrderId`, `Email`, and raw user input all have type `string`, so passing the
wrong one compiles.

```ts
declare const brand: unique symbol;
type Brand<T, B> = T & { readonly [brand]: B };

type UserId = Brand<string, "UserId">;
type Email  = Brand<string, "Email">;

// The ONLY way to make one — validation lives with the constructor
function toEmail(raw: string): Email {
  if (!raw.includes("@")) throw new ValidationError("invalid email");
  return raw as Email;              // the one sanctioned `as`, inside the gate
}

getUser("some-string");             // compile error — not a UserId
```

Use for identifiers that must not be swapped, validated strings, and units
(`Cents`, `Milliseconds`). Cost is one constructor per type; the payoff is that
the id-swap class of bug becomes unrepresentable.

## 2.6 Make illegal states unrepresentable

- **Parse, don't validate.** A function that returns `Email` proves validation
  happened; a function returning `boolean` leaves the caller holding a `string`
  that it must remember to trust.
- **Push optionality up.** `type User = { name: string; address?: Address }`
  forces every consumer to handle absence. If the address is required after
  onboarding, model `OnboardedUser` separately.
- **`readonly` by default** on interface fields and array parameters
  (`readonly T[]`). It documents intent and blocks accidental mutation of
  shared state.
- **Prefer unions over booleans** for anything with more than two eventual
  states. `status: "draft" | "review" | "published"` extends; three booleans
  produce eight states of which five are illegal.

## 2.7 Validate at the trust boundary, infer the type from the schema

Every value crossing into the program from outside — HTTP body, query string,
env, config file, CLI args, message payload, third-party response, `localStorage`
— is `unknown` until validated.

```ts
const ConfigSchema = z.object({
  port: z.coerce.number().int().positive(),
  databaseUrl: z.string().url(),
  logLevel: z.enum(["debug", "info", "warn", "error"]).default("info"),
});

export type Config = z.infer<typeof ConfigSchema>;      // one source of truth
export const config = ConfigSchema.parse(process.env);  // fail fast at startup
```

- **Derive the type from the schema**, never maintain a parallel `interface`.
  Two declarations drift; the drift is invisible until production.
- **Validate env at startup**, not at first use. A missing variable should kill
  the process on boot, not throw during a request at 3am.
- **Reject unknown keys** on inbound payloads (`.strict()` and equivalents) —
  silently accepting extra fields is how mass-assignment bugs start
  (`rules/05`).
- Any schema library with static inference works (zod, valibot, ArkType,
  TypeBox). Pick one per repository; the cost of two is two mental models and
  two ways to be wrong.

## 2.8 Generics discipline

A type parameter earns its place only if it appears **at least twice** —
otherwise it is a disguised `any`.

```ts
// BAD — T appears once; this is `(x: unknown) => void` with extra ceremony
function log<T>(value: T): void;

// GOOD — the parameter relates input to output
function first<T>(items: readonly T[]): T | undefined;
```

- Constrain parameters (`<T extends { id: string }>`) so the body can actually
  use them and errors point at the call site.
- Prefer inference over explicit type arguments at call sites; if callers must
  always spell out `<Foo>`, the signature is wrong.
- Conditional and mapped types are powerful and unreadable in bulk. If a type
  needs a comment to explain what it produces, consider whether a simpler
  runtime design would do — clever types have maintenance cost too.

## 2.9 Third-party types

- Prefer packages that ship their own types; `@types/*` is a fallback and can
  lag the runtime package.
- **`skipLibCheck: true` hides broken vendor declarations.** It is the right
  default for build speed but means a dependency's type errors surface as
  confusing failures in *your* code. Turn it off temporarily when debugging a
  types mismatch.
- When a dependency is untyped, write a **narrow** local `.d.ts` declaring only
  what you use, rather than `declare module "x": any`. The narrow version is a
  contract; the `any` version is a hole.
- Never patch vendor types by re-declaring their module globally — wrap the
  dependency in your own module with your own types (`rules/05` §5.1 gives the
  same advice for a security reason).

## 2.10 Avoid in new code

| Avoid | Use instead | Why |
|---|---|---|
| `enum` | `as const` object + `keyof typeof`, or a string-literal union | `enum` emits runtime code, breaks type-stripping runtimes, and numeric enums accept arbitrary numbers |
| `namespace` | ES modules | same runtime-emit problem; predates modules |
| Parameter properties (`constructor(private x: T)`) | explicit fields | TS-only runtime syntax |
| `Function`, `Object`, `{}` as types | precise signatures, `Record<string, unknown>`, `object` | they accept almost everything |
| Overload lists where a union works | one signature with a union parameter | overloads are unchecked against each other |
| `any[]` casts to satisfy a library | a typed adapter at the boundary | contains the damage |

Legacy code using these is not a finding by itself — flag it only where it
causes a real defect or blocks a runtime change.

## Audit checklist

- [ ] Strictness disabled: `rg -n '"strict"\s*:\s*false|@ts-nocheck' --glob '*.json' --glob '**/*.ts'`
      → HIGH (whole files unchecked).
- [ ] `any` at trust boundaries: `rg -n ': any\b|<any>|as any' --glob '**/*.ts'`,
      then check which sit on request/response/env paths → MEDIUM, HIGH on a
      request handler.
- [ ] Assertion-as-validation: `rg -n 'await .*\.json\(\)\s*as |JSON\.parse\([^)]*\)\s*as '`
      → HIGH (untrusted data typed by fiat).
- [ ] Suppressions: `rg -n '@ts-ignore'` → MEDIUM each (`@ts-expect-error` at
      least fails when the error disappears); `rg -n '@ts-expect-error'` without
      an explanatory comment → LOW.
- [ ] Non-null assertions in ordinary code: `rg -n '\w!\.' --glob '**/*.ts'`
      → LOW–MEDIUM; HIGH where the value is genuinely optional at runtime.
- [ ] `noUncheckedIndexedAccess` off while the code indexes arrays/records
      freely → MEDIUM.
- [ ] Optional-field soup instead of a discriminated union: types with several
      mutually exclusive optional fields → MEDIUM (illegal states representable).
- [ ] Non-exhaustive switches over union types: `rg -n 'switch \(' -A2` and
      check for a `default: assertNever` → MEDIUM on domain unions.
- [ ] Unvalidated boundaries: for each HTTP handler / queue consumer / env read,
      is there a schema parse? `rg -n 'process\.env\.' src/` outside a single
      config module → MEDIUM; unvalidated request bodies → HIGH.
- [ ] Parallel type and schema declarations for the same payload (an
      `interface User` next to a `UserSchema`) → MEDIUM (guaranteed drift).
- [ ] Schemas accepting unknown keys on write endpoints → HIGH (mass
      assignment, `rules/05`).
- [ ] Single-use type parameters: `rg -n 'function \w+<[A-Z]\w*>\([^)]*\): (void|boolean|string|number)'`
      → LOW (disguised `any`).
- [ ] Runtime-emitting TS syntax in a type-stripping runtime:
      `rg -n '^\s*(export )?(const )?enum |^\s*namespace ' --glob '**/*.ts'` → MEDIUM.
- [ ] Blanket module declarations: `rg -n 'declare module .*\{\s*$' -A2 | rg 'any'`
      → MEDIUM.
