---
name: himalaya-v2
description: "Himalaya v2 CLI email: IMAP/JMAP/Gmail, config renames."
version: 2.0.0
author: community
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Email, IMAP, SMTP, JMAP, Gmail, Graph, CLI, himalaya-v2]
    homepage: https://github.com/pimalaya/himalaya
prerequisites:
  commands: [himalaya]
---

## When to Use

Use when operating Gmail/IMAP/JMAP/Graph email through the external `himalaya`
CLI **v2 (>= 2.0.0)**. Trigger: reading, listing, searching, flagging, moving,
deleting, or sending mail via himalaya, or writing a v2 `config.toml`. Check
`himalaya --version` first; if it's v1 or absent, don't use this skill — see the
v1 skill `himalaya` (different config schema, don't mix them).

## Himalaya v2 — Email CLI (v2 only)

Himalaya is a Rust CLI that reads/writes email over IMAP, JMAP, Gmail REST, or
Graph backends. **This skill is for v2 (>= 2.0.0) only.** The old himalaya v1
config format (`[accounts.x].backend.type = "imap"`) is silently ignored by v2 —
TOML parses but no backend is ever selected — so never use those docs here.

This skill is separate from the Hermes Email gateway adapter. The gateway
adapter lets people email the agent via Hermes' built-in IMAP/SMTP adapter;
this skill operates a mailbox from terminal tools and requires the external
`himalaya` CLI (v2+).

## References

- `references/configuration.md` — v2 config schema (imap / jmap / gmail / graph / smtp), mailboxes, maildir.

## Identify the version first

```bash
himalaya --version   # must print >= 2.0.0
```

If it's v1 or not installed, don't guess — check `--version`. The v1 docs
(`skills/email/himalaya`) do not apply. v2 is roughly 3x smaller than v1.

## Install (Linux/macOS)

```bash
curl -sSL https://raw.githubusercontent.com/pimalaya/himalaya/master/install.sh | PREFIX=~/.local sh
# or: cargo install himalaya --locked
```

## Configuration file

Loaded from the first valid path among:
`$XDG_CONFIG_HOME/himalaya/config.toml` → `$HOME/.config/himalaya/config.toml` → `$HOME/.himalayarc`.
Override with `himalaya -c <PATH>`. Multiple `:`-separated paths are deep-merged (first is base).

**Key change:** there is no per-account `backend.type`. Each backend is a top-level
section (`imap.server`, `jmap.server`, `gmail.auth`, `smtp.server`, `maildir.root`).
An account section (`[accounts.NAME]`) with any backend key selects that backend.
Full schema: see `references/configuration.md` and the upstream
`config.sample.toml`.

Minimal IMAP (Gmail with App Password):

```toml
[accounts.gmail]
default = true
email = "you@gmail.com"

# IMAP is chosen by having an `imap.server` key — there is NO `backend.type`.
imap.server = "imaps://imap.gmail.com:993"
imap.sasl.plain.username = "you@gmail.com"
imap.sasl.plain.password.raw = "APP_PASSWORD"   # or { command = ["pass", "show", "google/app-password"] }

# Aliases map canonical roles (inbox/sent/drafts/trash) to server names.
mailbox.alias.inbox = "INBOX"
mailbox.alias.sent = "[Gmail]/Sent Mail"
mailbox.alias.drafts = "[Gmail]/Drafts"
mailbox.alias.trash = "[Gmail]/Trash"
```

Other backends — see `references/configuration.md`:

- **JMAP** (e.g. Fastmail): `jmap.server = "https://api.fastmail.com/jmap/session"`.
- **Gmail REST**: `gmail.auth.token.raw = "…"` or `{ command = ["ortie", "token", "show", "-a", "gmail"] }`.
- **Microsoft Graph**: `msgraph.auth.token.raw = "…"`.
- **Maildir**: `maildir.root = "~/Mail/example"` (read-only, local).

`gmail.user-id` defaults to `me`. Gmail/Graph file sent messages themselves (no
`smtp` block needed). IMAP/JMAP need an `smtp`/`jmap` send path if sending.

## CLI renames (v1 → v2)

| v1 | v2 |
|---|---|
| `-o/--output {plain,json}` | `--json` only |
| `--quiet`/`--debug`/`--trace` | `--log-level {off,error,warn,info,debug,trace}` (alias `--log`) |
| `-f/--folder` | `-m/--mailbox` (optional; defaults to inbox) |
| `folders list` | `mailboxes list [--counts]` |
| `folders add/delete` | protocol-specific (`himalaya imap create/delete`) |
| `thread` | protocol-specific APIs only |
| `folder INBOX` (envelope search) | `search` command (before<date> clause dropped) |
| `--folder` (copy/move/delete) | `--from`/`--to <mailbox-id>` |
| `save` / `save --folder` | `add` / `add --mailbox <id>` (mandatory) |
| `save --file PATH` | `add <file>` (single MessageArg) |
| `write/reply/forward` (interactive) | non-interactive flags via `pimalaya/mml` |
| `template` command | removed (moved to `pimalaya/mml`) |
| `read` (rendered text) | `read --raw` + pipe to an interpreter |
| `export/edit` | removed |
| `download --folder` | `-m/--mailbox` |
| `--downloads-dir` | `--dir <PATH>` (per-account `downloads-dir` only) |

Global: add `-b/--backend <NAME>` to force a backend, `--log-file <PATH>` to log.

## Common operations (v2)

```bash
himalaya mailbox list --counts
himalaya envelope list --json                  # INBOX, newest first
himalaya envelope list -m "INBOX" --max 20 --json
himalaya search --mailbox INBOX "from:boss newer_than:1d" --json
himalaya message read 42                         # prints message-level info
himalaya message read 42 --raw | <interpreter>     # custom rendering
himalaya message add 42 --flag seen
himalaya message copy 42 --from "INBOX" --to "Archive"
himalaya message delete 42                        # or flags add + expunge
himalaya attachment list 42
himalaya attachment download 42 --dir ~/mail-att
himalaya account list
himalaya account check   # validate a connection
```

Read a message into a draft then send (chain `pimalaya/mml`):

```bash
mml compose 42 --output /tmp/draft.eml           # or: himalaya compose --from x --to y --subject z
himalaya messages send /tmp/draft.eml
```

## Secrets

Every `*passwd`/`*password`/`*token` field accepts `{ raw = "…" }` or a shell
command: `{ command = ["pass", "show", "foo"] }` (also `secret-tool`, `gopass`,
`security`). Native keyring was removed. OAuth tokens come from an external broker
such as `pimalaya/ortie`, consumed the same way: `{ command = ["ortie", "token", "show", "-a", "gmail"] }`.

## Pitfalls

These cost real time to rediscover; each one silently produces wrong results rather
than an error.

- **Positional queries are greedy — options come BEFORE the query.** The trailing
  argument is swallowed as part of the query string, so
  `himalaya envelope search "after 2026-09-01"` treats `after 2026-09-01` as search
  text and matches nothing (or everything). Correct shape:
  `himalaya envelope search -s 500 "after 2026-09-01 and flag seen"`.
- **There is no `before` filter.** v2 dropped it; use `before:` in a query clause
  or filter on the returned date field.
- **Join filters with `and`** — the query language is not implicit.
- **The table's FLAGS column means STARRED, not seen.** A message can read as
  unread in the list while being starred, and vice versa. To find genuinely
  unread mail, search `subject X and flag seen` and subtract; never trust the
  column.
- **Never run a bare `flag seen` search.** It has no date bound and scans the
  whole mailbox. Always combine with `after <date>` (or another narrowing clause)
  so a mark-as-read sweep cannot touch historical mail.
- **`message delete` is trash-first**, not a hard delete: the message moves to the
  trash mailbox and is recoverable. `flags add + expunge` is the destructive path.
- **Trash folder name is not stable** — see the Bin/Trash note above.

## Setup checklist (for the agent)

1. `himalaya --version` — must be >= 2.0.0; otherwise don't use this skill.
2. Validate the connection for each backend: `himalaya account check`.
3. Write the config to a side-by-side path first (e.g. `~/.config/himalaya/config.v2.toml`), test with `himalaya -c <path> account check`, then switch to it once it passes.
4. For keyring/OAuth, wire a password-manager CLI (`pass`, `secret-tool`, `ortie`).
5. For interactive compose/reply, install `pimalaya/mml` and chain it into `messages send`/`add`.

> **Gmail note:** an App Password (16 chars, from Gmail → Security → App Passwords)
> is required when 2FA is on. Without the correct `mailbox.alias.sent` mapping,
> save-to-Sent fails *after* SMTP delivery — but the shared backends file sent
> themselves, so this only matters for IMAP/JMAP send paths. Always set aliases.

> **Trash folder name is not reliably localized.** On some accounts Google names
> trash `Trash`, on others `Bin` (the English word, not a localization). If
> `message delete` fails with `NO folder <name>`, list `himalaya mailbox list`
> and set `mailbox.alias.trash` to whatever appears (often `[Gmail]/Bin` or
> `[Gmail]/Trash`).
