# 06 — Performance

Measure, then change one thing, then measure again. `deep-performance-audit`
owns the baseline/profile/equivalence methodology; this file owns the
TypeScript-specific measurements and the failure modes worth looking for.

## 6.1 No claim without a number

- **Never optimize from intuition.** JIT behavior, allocation costs, and I/O
  latency routinely invert what "obviously faster" code does.
- Establish a baseline on **representative** work: production-shaped input
  sizes and distributions. A benchmark over a 10-element array predicts nothing
  about the 100,000-element case that is actually slow.
- Change one thing per measurement, and keep behavior identical — a faster
  function that returns different results is a bug, not an optimization. Tests
  must pass before and after.
- State the win as a number in the PR. "Feels faster" is not a result.

## 6.2 Where the time actually goes

In descending order of how often it is the real answer:

1. **Waiting on I/O you issued serially** (§6.3) — usually the whole problem.
2. **Doing the work more times than necessary**: N+1 queries, re-fetching in a
   loop, re-parsing config, recomputing per request what could be computed once.
3. **Algorithmic shape**: a `.find`/`.includes` inside a loop over the same
   data is quadratic; build a `Map`/`Set` once (`rules/03` §3.6).
4. **Blocking the event loop** (`rules/04` §4.5) — this shows up as *every*
   request being slow, not one.
5. **Allocation and copying**: large intermediate arrays, whole-file buffering,
   deep clones of objects you only read.
6. **Startup cost**: module graph size, top-level work, cold starts.

Only then micro-optimization. Engine-level tuning (hidden classes, inline
caches) matters in genuinely hot loops and almost nowhere else.

## 6.3 Concurrency is the usual win

```ts
// BAD — two independent round trips, serialized: t = a + b
const user = await getUser(id);
const prefs = await getPrefs(id);

// GOOD — overlapped: t = max(a, b)
const [user, prefs] = await Promise.all([getUser(id), getPrefs(id)]);
```

- Sequential awaits over independent work are pure added latency.
- Batch instead of looping: one `WHERE id IN (...)` beats N queries, and most
  APIs offer a bulk endpoint. The N+1 query is the most common real performance
  defect in server TypeScript.
- **Bound the concurrency** (`rules/04` §4.2). Parallelism that overwhelms the
  database is slower end-to-end than a bounded queue, and it hurts every other
  caller too.
- Cache deliberately, with an eviction policy and an invalidation story. An
  unbounded `Map` used as a cache is a memory leak with good intentions.

## 6.4 Measuring in TypeScript

```ts
// Microbenchmark: use a library that handles warmup, GC noise, and statistics
import { bench, run } from "mitata";
bench("parse", () => parseConfig(sample));
await run();
```

- **Wall-clock `Date.now()` diffs are not a benchmark.** They ignore JIT warmup
  and variance. Use `mitata`, `tinybench`, or the platform's high-resolution
  timer with proper statistics.
- **Profile before micro-benchmarking**: `--inspect` plus a CPU profile in
  DevTools tells you *which* function to benchmark. Optimizing the wrong
  function perfectly is the most common wasted effort.
- **Heap snapshots** find leaks: take one, exercise the workload, take another,
  compare retained sizes. Steady growth across snapshots at steady load is a
  leak — usually an unbounded cache, an array that only appends, or listeners
  never removed.
- For servers, measure **end-to-end latency percentiles under load** (p50/p95/
  p99), not the mean and not a single request. Instrumentation belongs to
  `sota-observability`.
- Benchmark in the runtime you deploy. Bun and Node have different performance
  characteristics; a win in one is not automatically a win in the other.

## 6.5 Memory and allocation

- **Stream, don't buffer** large payloads (`rules/04` §4.6). Whole-file reads
  and full-response buffering set your memory ceiling to your largest input.
- Chained `map/filter/reduce` allocates an array per stage. Fine for hundreds
  of items; measurable for millions — fuse into a single pass only after
  proving it matters.
- Avoid deep-cloning objects you only read. `structuredClone` is correct but
  not free.
- Watch closures capturing large objects, and event listeners/intervals never
  cleaned up — both keep entire graphs alive.
- Reuse buffers in hot paths; allocate `Uint8Array`s once where the size is
  known.

## 6.6 Startup and bundle size

- **Bundle size is a latency budget** for browsers and a cold-start budget for
  serverless. Measure it in CI and fail on regressions past a threshold.
- **Enable tree-shaking honestly**: ESM-only source and an accurate
  `sideEffects` field (`rules/01` §1.2). A false `sideEffects: false` deletes
  needed code; a missing one keeps everything.
- **Import narrowly.** A default import of a large utility library pulls the
  whole thing if the package is not tree-shakeable.
- **Defer expensive work out of module scope.** Top-level `await`, config
  parsing, and client construction at import time are paid on every cold start,
  including for requests that never use them — build lazily.
- Analyze what is actually in the bundle before cutting; the biggest entry is
  frequently a transitive dependency nobody chose (`rules/05` §5.6).

## 6.7 When TypeScript itself is slow

Slow `tsc` is a productivity cost worth treating as a performance problem:

- **Project references + incremental builds** in monorepos (`rules/01` §1.8);
  without them every check redoes all the work.
- `skipLibCheck: true` avoids checking dependency declarations.
- The usual culprit for a pathological check is a deeply recursive conditional
  or mapped type (`rules/02` §2.8). Simplify it; clever types are not free.
- Use the compiler's diagnostics (`--extendedDiagnostics`, trace flags) to find
  the expensive file rather than guessing.

## Audit checklist

- [ ] Performance claims in comments or PRs with no benchmark → LOW (unverified)
      and MEDIUM if the code was made less readable for it.
- [ ] Serial awaits on independent operations:
      `rg -n -A2 'const \w+ = await ' --glob '**/*.ts'` where consecutive awaits
      share no data → MEDIUM.
- [ ] N+1 queries: `rg -n -A5 'for (const|await) ' --glob '**/*.ts' | rg 'await (db|prisma|repo|query)'`
      → HIGH in a request path.
- [ ] Quadratic lookups: `.find(`/`.includes(`/`.indexOf(` inside a loop over a
      second collection → MEDIUM (build a `Map`/`Set` once).
- [ ] Unbounded caches: `rg -n 'new Map\(\)|\{\}' --glob '**/*.ts'` used as a
      module-level cache with no eviction → MEDIUM (leak).
- [ ] Whole-file/whole-response buffering:
      `rg -n 'readFile\(|\.arrayBuffer\(\)|\.text\(\)' --glob '**/*.ts'` on
      inputs whose size is not bounded → MEDIUM.
- [ ] Event loop blocking in handlers (`rules/04` checklist) → HIGH.
- [ ] Timing "benchmarks" with `Date.now()`:
      `rg -n 'Date\.now\(\).*-.*Date\.now\(\)|performance\.now\(\).*-' --glob '**/*.ts'`
      used to justify a change → LOW (no warmup or statistics).
- [ ] Expensive module-scope work: `rg -n '^await |^const \w+ = (readFileSync|new \w+Client)\(' src/`
      at top level → MEDIUM for serverless, LOW otherwise.
- [ ] Bundle budget: is bundle size measured in CI? Absent for a browser or
      serverless target → MEDIUM.
- [ ] `sideEffects` unset in a published package → LOW (consumers cannot
      tree-shake); set to `false` while import-time mutations exist → MEDIUM.
- [ ] Listeners/intervals without cleanup:
      `rg -n 'addEventListener\(|setInterval\(' --glob '**/*.ts'` with no matching
      `remove`/`clear` → MEDIUM (leak).
- [ ] Monorepo type-check with no `composite`/`references` and a slow CI type
      step → LOW–MEDIUM.
