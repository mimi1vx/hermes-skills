---
name: opencode-v2
description: "Use OpenCode V2 via --server and background service."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Coding-Agent, OpenCode, Autonomous, Server]
    related_skills: [opencode]
---

# OpenCode V2 (server mode)

V2 variant of the `opencode` skill. V2 runs one shared background server per
user account; every local client connects to it. Source: upstream docs at
https://opencode.ai/v2/docs (CLI intro + commands reference).

## When to Use

- User asks for OpenCode V2, server mode, or `--server`.
- Delegating coding to a shared/long-lived opencode server.
- Managing the background service, plugins, or V2 sessions.

## Server model (the V2 change)

- Default: commands use the shared background service (owns sessions, config,
  permissions, tool execution).
- `opencode run --server http://localhost:4096 "..."` targets a specific server.
- `opencode run --standalone` (documented as `--standalone`) runs a private server.
- Manage the service: `opencode service {start|stop|restart|status}`,
  `opencode service {get|set|unset} <key>` (e.g. `service set disabled true`
  makes private servers the default).
- `opencode serve [--hostname 0.0.0.0 --port 4096]` starts a standalone
  API/web server; `opencode reload` applies config without restart.
- Auth for a server: `-u/--username` (default `opencode`, else
  `OPENCODE_SERVER_USERNAME`), `-p/--password` (else
  `OPENCODE_SERVER_PASSWORD`).

## One-shot runs (preferred for automation)

```
opencode run --server http://127.0.0.1:4096 --model provider/model 'Do X' --format json
opencode run --server http://127.0.0.1:4096 -f file.ts 'Review for bugs'
```

`--dir` sets the run directory (remote path when targeting a server).
`--agent build|plan`, `--title`, `--share`, `--thinking`, `--variant`,
`--auto` (dangerous: auto-approves) work as in V1.

## Sessions, auth, plugins

- `opencode session list --max-count 20 --format json`; `session delete`,
  `session export [--sanitize]`, `session import [--directory]`.
- `opencode auth list|login|logout|switch` (login supports `--method key`).
- `opencode plugin list|add|check|update|remove` — how the ocskillz set
  (skills/agents/commands) is installed and updated.
- `opencode stats [--days 7] [--models] [--cost] [--json]`.
- `opencode api GET /api/session` (raw server API), `opencode pair` (one-time
  browser/app links), `opencode mini` (minimal UI), `opencode acp` (editor
  integrations), `opencode debug paths|config|agents`.

## Hermes procedure (verified against a live V2 server)

1. Binary: `~/.bun/bin/opencode` (v2.0.22) — NOT on default PATH, so
   `export PATH="$HOME/.bun/bin:$PATH"` first. Auth: `OPENCODE_SERVER_PASSWORD`
   env (username defaults to `opencode`). List via the raw API because bare
   `session list` 500s when local cwd isn't a server project:
   `opencode api --server <url> GET /api/session`.
   A bare `run` without a session 500s — always create the session first,
   with a server-local directory AND explicit model (exact keys — the server
   silently ignores wrong ones):
   `opencode api --server <url> session.create --data '{"title":"t","location":{"directory":"/tmp"},"model":{"providerID":"opencode-go","id":"space-bunny-free","variant":"max"}}'`
   Verify the reply (projectID, location.directory, model echoed back).
2. Run inside it with an explicit model. Default model order on
   provider `opencode-go`: 1) `space-bunny-free`,
   2) `muse-spark-1.3-contributor`:
   `opencode run --server <url> --session <id> --model provider/model '...' [--format json]`
   Both are the user's private projects/toys. Employer work goes to Claude
   on `google-vertex` (company-paid endpoints) — keep the two apart.
3. Scope each task to one repo/workdir (server-local paths).
4. Delete scratch sessions when done: `opencode session delete <id> --server <url>`.
5. Summarize file changes, test results, next steps back to the user.

## Notes

- Requires a V2 binary (`opencode upgrade X.Y.Z --method bun`); 1.x has
  `serve`/`--attach` but no `--server`/`service` model.
- Needs model auth (`opencode auth login`) or a custom provider with a key;
  without it runs fail at model load.
- Binary + REST recipe live-verified against the Mac V2 server 2026-10-04.

## Raw REST curl — FALLBACK ONLY (live-verified 2026-10-04)

Primary path is always the `opencode` binary (`run --server`, `session`,
`api`, ...). Use raw REST below ONLY when the binary is absent on the
machine you're working from. Do not reach for curl while a binary path exists.

```
URL=http://192.168.66.1:49374   # Mac server; password in $HERMES_HOME/.env
# create — exact key shapes matter, server ignores wrong ones with 200:
# model.* is {"id", "providerID", "variant"} (NOT "modelID");
# directory lives under "location" (top-level "directory" is ignored ->
# session lands in the parent project with the server-default model).
curl -u "opencode:$PW" -X POST $URL/api/session \
  -d '{"title":"t","location":{"directory":"/path/to/repo"},"model":{"providerID":"opencode-go","id":"space-bunny-free","variant":"max"}}'
# verify the reply: projectID == repo canonical id, location.directory exact,
# model echoed back. Mismatch -> delete and retry, don't prompt into it.
# prompt (body needs "text"; "agent":"build"|"planner")
curl -u "opencode:$PW" -X POST $URL/api/session/<sid>/prompt -d '{"agent":"build","text":"..."}'
# poll: GET .../session/<sid>/message -> ids; detail per message:
# GET .../session/<sid>/message/<mid> -> model/finish/error/content[].text
# (list payloads are empty — always fetch detail per id)
# switch model mid-session: POST .../session/<sid>/model
# -d '{"model":{"providerID":"opencode-go","id":"...","variant":"max"}}'
# cleanup: DELETE .../api/session/<sid>
```

Gotchas: model `fledge-alpha-free` / provider `opencode` with 403
"not available in your country" means the override was lost (wrong keys)
and the geo-blocked server default ran instead — fix the shape, don't retry
the prompt. API reference: https://opencode.ai/v2/docs/api/ (prompt =
`v2.session.prompt`, model switch = `v2.session.switchmodel`).
