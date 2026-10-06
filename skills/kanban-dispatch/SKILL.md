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

- After `gave_up` the task is parked: `unblock <id>` before it can be
  redispatched.
- A task that burns all retries on the same failure: `archive` it and file
  a FRESH task carrying the findings-so-far in its body, instead of
  unblock/dispatch loops on the dead one.
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
