---
name: kanban-dispatch
description: "Dispatch background work via kanban workers."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [kanban, delegation, background-workers]
---

# Kanban Dispatch

Run durable background work through Hermes kanban boards: file a
self-contained task, assign a profile, dispatch, monitor heartbeats, and
collect findings from the task itself.

## When to Use

- Research or implementation work that should survive the session.
- User wants to watch progress (`show`) rather than wait on a live call.
- Fanning out independent workstreams onto one board.

## Procedure

1. Board: `hermes kanban boards create <slug>` (once; `boards list` to see
   existing). Pass `--board <slug>` immediately after `kanban` on every call.
2. File the task with a SELF-CONTAINED body — the worker sees only the
   title and body, not your conversation. Include goal, prior findings with
   numbers, constraints/policy, and what the deliverable looks like:
   `hermes kanban --board <slug> create "<title>" --body "..."`.
3. Assign: `hermes kanban --board <slug> assign <id> <profile>`.
   Pin the model first when the worker must avoid the profile default:
   `set-model <id> <model> --provider <provider>` — takes effect on the
   NEXT dispatch, not the running one.
4. Dry-run first: `hermes kanban --board <slug> dispatch --dry-run` —
   confirms the task would spawn before spending a worker run.
5. Dispatch for real in the background (it returns immediately; the worker
   runs async): `terminal(command="hermes kanban --board <slug> dispatch",
   background=true)` with notify on.
6. Monitor: `hermes kanban --board <slug> show <id>` — status, run number,
   per-minute heartbeats, comments. `list` for the board overview.
7. Harvest: read findings from the task (comments/completion text),
   then `complete <id> --result "..."` — bare `complete` with no result
   text is refused, so always pass the summary of what was done.

## Failure handling

- Consecutive nonzero-exit crashes trip `failure_limit` (default 2) and park the task as `blocked` — `dispatch --dry-run` then spawns 0 and the fix is `unblock <id>`, not another dispatch. Rate-limited exits (rc=75, quota wall) requeue without counting a failure no matter how many in a row, so only nonzero crashes arm the limiter. Pull the cause first from `runs <id> --json` (full error metadata, worker last-output is truncated there) plus the board log file `logs/<id>.log` sitting next to the board's kanban.db.
- After `gave_up` the task is parked: `unblock <id>` before it can be
  redispatched.
- A task that burns all retries on the same failure: `archive` it and file
  a FRESH task carrying the findings-so-far in its body, instead of
  unblock/dispatch loops on the dead one.
- When `runs --json` shows only truncated status chatter with no error, read the worker session transcript from state.db (`messages` table by `session_id`, last rows) and check the final assistant message's `finish_reason` — `length` plus repeated short phrases means the model is looping at its token limit, so fix with a stronger model or primary-quota recovery, never more retries on the same weak fallback.
- When the worker dies with "every provider in the fallback chain kept failing over", get the per-provider breakdown before acting: grep the worker `session_id` in the errors and agent logs for one line per provider/model attempt — the single failover message hides which entries are durably dead (repeated HTTP 400 model-unavailable on every path) versus transiently down (connection errors), and the fix differs per case (drop dead entries from the chain via `hermes config set fallback_providers` versus retry once the endpoint is back). A 400 on the worker path alone is not proof the model is dead — the same model string can succeed interactively while the gateway worker path gets a protocol/unavailable 400, so confirm the entry fails off the worker path too before dropping it.
- Triage crashes with full `show`/`runs` output, never the trimmed
  one-line `worker_output` — identical prefixes across runs are a
  truncation artifact, not proof the runs died at the same point.
- Retries spawn FRESH sessions (no `--resume` in dispatcher argv): runs
  dying in ~1min with identical text died at startup, not mid-work.
- Contributor-tier (`-contributor`) models are refused for non-interactive
  workers unless the user explicitly opts in (config flag
  `security.allow_data_training_tiers_noninteractive`) — the refusal
  names the flag. Never set it silently: the suffix means the provider
  trains on prompts/completions, so ask the user first.
- Edit kanban/fallback config only via `hermes config set` — direct
  edits to config.yaml are refused as security-sensitive. Allow a profile
  with `hermes config set kanban.dispatch_profiles '["default"]'`; drop a
  duplicated primary from the chain with `hermes config set
  fallback_providers '[...]'` carrying only surviving entries (`fallback
  remove` is an interactive picker, unusable headless).

## Pitfalls

- Scratch workspaces are wiped when the task completes — state the
deliverable as task comments/completion text in the body, OR give an
explicit absolute output path outside the workspace for artifacts;
without one, any file the worker writes disappears with the workspace.
- A crashed run is not necessarily terminal — the dispatcher auto-retries
(visible as run #2 in `show`), so check the runs list before intervening
on a `crashed` run.
- Dispatch is fire-and-forget at the CLI level: a clean `Spawned: 1` only
  means the worker process started, so confirm life with `show` (claimed +
  heartbeat events) before reporting progress to the user.
- Fan out destructive work as read-only triage — write the approval gate
  into the task body (NO deletes/moves in the worker; the deliverable is
  counts plus verdict plus proposed command) and let the parent execute
  after user approval — a worker with delete rights and no gate acts on
  its own schedule.
- Check `show` before `complete` — runs that finish normally may already
  terminal-close the task, and `complete` then refuses with
  unknown-id-or-terminal-state — harvest the comments and move on.
- Harvested file artifacts (UID lists, ID sets) carry no shape guarantee —
  head the file before building commands from it: a single comma-joined
  line holds hundreds of IDs that `wc -l` reports as 1, so count from
  content (separators), never from lines.
- A dry-run that Skips every task (`non-spawnable assignee — terminal lane`,
  or `unassigned` with no worker profile present) means nothing on this box
  will spawn — report the task as queued, not running, and stop; re-running
  dispatch loops on the same verdict instead of starting work. Triage in order: `assignees` (profile on disk?), then `diagnostics --json` (a `task_id: null` entry reports the `kanban.dispatch_profiles` fail-closed state), then `hermes config path` plus the `kanban:` / `dispatch_profiles:` block — a present-but-empty list names no valid profile so everything is refused, while omitting the key allows any profile.
- A fallback entry duplicating the primary adds no quota resilience — the
  same wall kills both, so keep only genuinely alternate provider/model entries.
- When workers die with "custom didn't respond", curl every custom
  base_url in BOTH `fallback_providers` and `custom_providers` — the two
  lists diverge (stale LAN IPs after DHCP moves) and the worker tries the stale one. A 200 plus a full model list is not proof of health — probe with a real minimal chat completion too, since a model listing endpoint can report downloaded-but-unloaded models while inference itself fails.
- Manual `dispatch` reporting `Spawned: 0` right after a reclaim usually
  means the rate-limit cooldown guard, not a stuck board — the gateway
  dispatcher (every `dispatch_interval_seconds`) picks the task up within a
  minute, so confirm with `show` for a new running run before re-dispatching.
- `reclaim` kills a heartbeat-healthy run — use it only to force an
  immediate retry on explicit user ask, always with `--reason` recorded.
