# Monitoring an Account (PRs, Issues, Projects)

Watch *many* repositories for changes across runs and surface only what
changed — the class of work behind "keep me informed about my PRs, issues,
and projects". Distinct from the single PR lifecycle workflows in the other
references; it combines a whole-account sweep with a diff + notify loop
(typically driven by cron `--no-agent`).

## Sweep every repository, then read PRs + issues per repo

`gh repo list` takes the owner as a positional argument (no `--owner` flag):
```bash
gh repo list <owner> --no-archived --json name,isFork --jq '.[] | .name'
```
Skip forks unless the user wants them: filter `select(.isFork==false)` in the
`--jq` expression.

PRs and issues are per-repo porcelain (`gh pr list --repo` /
`gh issue list --repo`); there is no account-wide flag. Iterate every repo:
```bash
for r in <repos>; do
  gh pr list --repo owner/$r --state open --json number,title,url,author,
    createdAt,updatedAt,closedAt,mergedAt,isDraft,state,statusCheckRollup,\
    reviewRequests,labels,assignees --jq '.[] | {number,title,url,
    author: .author.login, state, isDraft, updated: .updatedAt}'
done
```
Collect into one JSON stream (append to a file) so a future session can
diff it. Parse JSON with the same `--jq` projection every run — output must be
byte-stable so a change-diff hashes to "unchanged" on a quiet tick.

## Never trust `state` in the output label — parse it

`gh pr list --state open` does not always filter to only OPEN; the JSON can
carry `MERGED`/`CLOSED` rows. Decide per item from `state`, `mergedAt`,
`closedAt` rather than trusting the CLI flag, or closed PRs leak into the
report.

## `statusCheckRollup` is a list, not an object

In `gh pr list --json ...statusCheckRollup`, the field is a **list of check
runs**, each `{name, conclusion, status: "COMPLETED"|"RUNNING"}` — not a
`{ statuses: [...] }` object. Treat a run as passing only when `conclusion` is
`success`/`passing`; failing = terminal run whose conclusion is anything else.
Reading it as an object raises `AttributeError: 'list' object has no attribute
'get'`.

## Diff, then emit only on change

Compare the current sweep to a saved snapshot. Emit nothing when the set of
keys (repo+number) is identical — cron with `--no-agent` delivers nothing, so
a quiet tick stays silent. Emit a full baseline once on the first run (no
previous snapshot), then only additions, merges/closes, and state/label shifts.
Keep a `.json` snapshot next to the script so future runs can compare.

## Delivery: make the sweep cron-runnable

A monitor that emits on change pairs naturally with a cron `--no-agent` job:
the script *is* the job and its stdout is delivered verbatim (empty = silent).
Two hard constraints for this pattern:

- Cron joins `--script` to `~/.hermes/scripts/`; pass the **bare filename**
  (`--script github_monitor.sh`), never an absolute path.
- Per-run arguments do not survive to the script: everything after the cron
  `schedule` string goes into the agent prompt, not the script. To pass args to
  the script, wrap them in a thin shell entry (`script.sh`) that execs the
  script with its flags, and set `--script script.sh`.

## Projects (V2) — two scope and format gotchas

- `gh project list` supports **only `--format {json}`** (the literal is the
  entire output). It does not accept `--json` for field selection, and it does
  not take `--repo` — pass `--owner <owner>` (user) or the org.
- Project *contents* need GraphQL (`gh api graphql -f query='...'`) and the
  token must hold the `read:project` scope, otherwise the query returns
  `INSUFFICIENT_SCOPES`. Without that scope, monitor projects as "unavailable"
  rather than fail.
