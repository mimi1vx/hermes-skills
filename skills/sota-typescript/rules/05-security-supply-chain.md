# 05 — Security & Supply Chain

TypeScript-specific security mechanics and the npm dependency graph.
Cross-language security architecture — threat modeling, authn/authz design,
crypto selection, trust-boundary theory — belongs to `sota-code-security`;
load it for anything beyond the language-level patterns here.

The single highest-value rule: **types do not validate anything at runtime**.
Every input below is `unknown` until a schema parses it (`rules/02` §2.7).

## 5.1 Injection: never build a command, path, query, or URL by concatenation

**Subprocesses.** Pass an argument array; never build a shell string.

```ts
// BAD — shell metacharacters in `name` are code
exec(`convert ${name} out.png`);

// GOOD — no shell, arguments stay data
await Bun.spawn(["convert", name, "out.png"]).exited;   // or execFile / spawn
```

If a shell is genuinely required, the argument is still not safe to interpolate
— validate it against an allowlist first. Prefix user operands with `--` so a
value starting with `-` cannot become a flag, and use absolute executable paths
where `PATH` is not trusted.

**SQL.** Parameterize values, always. Identifiers (table/column names) cannot
be parameterized — resolve them through an allowlist map, never string
interpolation. Tagged-template SQL clients and query builders parameterize by
default; a template literal handed to a raw `query()` does not.

**Filesystem paths.** Resolve, then verify containment:

```ts
const full = path.resolve(baseDir, userPath);
if (full !== baseDir && !full.startsWith(baseDir + path.sep)) {
  throw new ForbiddenError("path escapes base directory");
}
```

Checking for `".."` in the input is not sufficient — encodings, absolute paths,
and symlinks all bypass it. Reject NUL bytes explicitly.

**Outbound URLs (SSRF).** A user-supplied URL is a request your server makes
with your network position. Parse with `new URL()`, allowlist the scheme
(`https:` only) and the host, resolve the hostname and reject loopback,
link-local (including cloud metadata endpoints), private, CGNAT, and multicast
ranges — and **re-validate after every redirect**, or set `redirect: "manual"`
and handle them yourself.

## 5.2 Dynamic code execution

`eval`, `new Function`, `vm` without isolation, and `import()` with a
runtime-computed specifier all execute data as code.

- Never pass request, config-file, or database content into any of them.
- Template engines that compile strings, and expression evaluators for
  user-supplied rules, are the same hazard wearing a library. If users must
  supply logic, use a sandboxed evaluator with no host access and a step limit
  — see `sota-sandboxing`.
- `JSON.parse` is safe; **`JSON.parse` with a reviver that assigns into an
  object is not** (§5.4).

## 5.3 Untrusted output: XSS and the DOM

- **Never assign untrusted data to `innerHTML`, `outerHTML`,
  `insertAdjacentHTML`, or `document.write`.** Use `textContent`, or sanitize
  with a maintained sanitizer if HTML is genuinely required.
- In React, `dangerouslySetInnerHTML` is the same sink with a warning in the
  name. In every framework, the "raw"/"unescaped" directive is the sink.
- **URLs are a sink too**: `href`/`src` accepting `javascript:` or `data:` from
  user input is XSS. Allowlist the scheme.
- Server-rendered JSON embedded in a `<script>` must escape `<` — otherwise a
  string containing `</script>` breaks out.
- Set a Content-Security-Policy; it is the backstop for the sink you missed.
- `postMessage` handlers must verify `event.origin` against an allowlist before
  trusting the payload.

## 5.4 Prototype pollution

Assigning attacker-controlled keys into an object can reach `Object.prototype`
and change behavior program-wide.

```ts
// BAD — key comes from a request body; "__proto__" poisons every object
for (const [k, v] of Object.entries(input)) target[k] = v;

// GOOD — Map has no prototype chain to pollute
const target = new Map(Object.entries(input));

// or, if an object is required
const target = Object.create(null);
if (k === "__proto__" || k === "constructor" || k === "prototype") continue;
```

- Deep-merge, `set`-by-path, and query-string parsing utilities are the classic
  vectors — prefer maintained libraries with explicit prototype guards.
- Validate with a schema that rejects unknown keys (`rules/02` §2.7) before any
  merge; that closes both this and mass assignment.
- `Object.freeze(Object.prototype)` at startup is a cheap defense in depth.

## 5.5 Secrets, config, and data exposure

- **Never commit secrets**; load from the environment or a secret manager and
  validate at startup (`rules/02` §2.7).
- **Client bundles are public.** Anything reaching browser code — including
  every `NEXT_PUBLIC_`/`VITE_`-prefixed variable — is published. Server-only
  secrets must be unreachable from client entry points.
- Sourcemaps published to production expose source; ship them to your error
  tracker instead.
- **Do not log secrets, tokens, or full request bodies.** Redact at the logger,
  not at each call site — see `sota-observability`.
- Errors returned to clients carry stack traces and SQL fragments if you let
  them. Return a code and a correlation id; log the detail server-side.
- Compare secrets with a constant-time function, never `===`.

## 5.6 Dependency and supply-chain hygiene

npm is the largest attack surface most TypeScript projects have.

- **Commit the lockfile and install frozen in CI** (`rules/01` §1.7). Without
  it, a compromised or substituted version installs silently.
- **Install scripts execute arbitrary code at install time**, on developer
  laptops and CI runners with credentials. Audit them; run with install scripts
  disabled where the toolchain supports it, and allowlist the few packages that
  genuinely need them.
- **Vet before adding.** Check download trend, maintenance, maintainer count,
  and transitive weight. A one-function dependency that pulls twelve packages
  is a bad trade — see `rules/03` §3.9 for the platform APIs that replace most
  of them.
- **Pin exactly for applications** (the lockfile does this); publish ranges for
  libraries. Review dependency-bump diffs rather than auto-merging them.
- **Run `audit`/SCA in CI**, triaged by reachability rather than raw CVE count.
  A vulnerability in a build-only dependency is not the same finding as one in
  a request path.
- Prefer packages that publish **provenance/attestations**, and be suspicious
  of a package whose repository does not match its published contents.
- Typosquatting and slopsquatting are live: verify the exact package name
  before adding, especially for a name suggested by a model rather than found
  in documentation.

## 5.7 Denial of service

- **Regex**: nested quantifiers over user input backtrack catastrophically.
  Avoid `(a+)+`-shaped patterns, prefer explicit parsing, and **escape any
  user-supplied substring** before embedding it in a pattern.
- **Body and upload limits** are enforced while streaming, not after buffering
  (`rules/04` §4.6). Also limit JSON nesting depth and array lengths in the
  schema.
- **Decompression bombs**: cap the decompressed size and abort past the limit.
- **Rate limit per account and per object**, not only per IP — see
  `sota-code-security`.
- Bound every fan-out and every queue (`rules/04` §4.2); unbounded concurrency
  is a self-inflicted DoS.

## 5.8 Runtime hardening

- Run as a non-root user in the container; drop capabilities. `sota-sandboxing`
  owns the isolation model.
- Use the runtime's permission flags (Deno's, Bun's, Node's permission model)
  where available to deny filesystem and network access the process does not
  need.
- Never set `NODE_TLS_REJECT_UNAUTHORIZED=0`, including "temporarily" in a
  development script that will be copied into a Dockerfile.
- Keep the runtime patched; a pinned base image that never moves accumulates
  known CVEs.

## Audit checklist

- [ ] Shell interpolation:
      `rg -n 'exec\(|execSync\(|\$\{.*\}.*\bshell\b|spawn\(.*shell:\s*true' --glob '**/*.ts'`
      with template literals → CRITICAL when reachable from input.
- [ ] Dynamic code: `rg -n '\beval\(|new Function\(|vm\.runIn' --glob '**/*.ts'`
      → CRITICAL if data flows in.
- [ ] SQL by concatenation:
      `rg -n '(query|execute)\(\s*[\x60\x27"].*\$\{' --glob '**/*.ts'` → CRITICAL.
- [ ] Path traversal: `rg -n 'path\.join\([^)]*\b(req|request|params|query|body)\b'`
      → HIGH unless followed by a containment check.
- [ ] SSRF: `rg -n 'fetch\((?!["\x27]https?://)' --pcre2 --glob '**/*.ts'` where
      the URL derives from input, with no host allowlist → HIGH.
- [ ] XSS sinks: `rg -n 'innerHTML|outerHTML|insertAdjacentHTML|dangerouslySetInnerHTML|document\.write'`
      → HIGH each unless the value is provably static or sanitized.
- [ ] Unchecked `postMessage`: `rg -n "addEventListener\('message'" -A5` without
      an `origin` check → HIGH.
- [ ] Prototype pollution: `rg -n '\[\s*(key|k|prop|name)\s*\]\s*=' --glob '**/*.ts'`
      in merge/assign helpers over request data → HIGH; also
      `rg -n 'merge\(|deepMerge\(|set\(.*path'`.
- [ ] Mass assignment: object spread of a request body into a persisted entity
      (`rg -n '\.\.\.(req\.body|body|input|payload)'`) → HIGH.
- [ ] Secrets in the repo:
      `rg -in '(api[_-]?key|secret|token|password)\s*[:=]\s*[\x27"][^\x27"]{12,}'`
      → CRITICAL; also check for committed `.env`.
- [ ] Client-exposed secrets: `rg -n 'NEXT_PUBLIC_|VITE_|PUBLIC_'` naming
      anything secret-like → CRITICAL.
- [ ] Secret comparison with `===`: `rg -n '(token|secret|signature|hmac)\s*===' `
      → HIGH (timing oracle).
- [ ] Error detail returned to clients: `rg -n 'res\.(json|send)\(.*\berr(or)?\b'`
      → MEDIUM (stack/SQL leakage).
- [ ] TLS disabled: `rg -n 'NODE_TLS_REJECT_UNAUTHORIZED|rejectUnauthorized:\s*false'`
      → CRITICAL in anything shipped.
- [ ] Lockfile absent, or CI installing unfrozen (`rules/01` checklist) → HIGH.
- [ ] Install scripts in the dependency tree unaudited, or CI running installs
      with scripts enabled and no allowlist → MEDIUM.
- [ ] No SCA/audit step in CI → MEDIUM; audit present but never triaged → LOW.
- [ ] ReDoS shapes: `rg -n '\(\[?[^)]*[+*]\)[+*]' --glob '**/*.ts'` and any regex
      built from user input without escaping → HIGH.
- [ ] Missing body/upload size limits on request parsing → MEDIUM.
