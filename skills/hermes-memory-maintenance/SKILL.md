---
name: hermes-memory-maintenance
description: "Use when a memory entry is wrong, stale, or duplicated."
---

Hermes persistent memory is files on disk, not only what the memory tool shows. There are three separate stores — identify which one the complaint is about before acting.

## The three stores

- Live memory: `$HERMES_HOME/memories/MEMORY.md` (agent notes) and `$HERMES_HOME/memories/USER.md` (user profile). This is what gets injected into sessions.
- Pending approvals: `$HERMES_HOME/pending/memory/<id>.json` — one file per queued add/replace/remove op, each with `summary`, `payload.old_text`, `payload.content`, and `payload.matched_entry`. A short hex id the user quotes is a pending-file name — look for it here first.
- MCP knowledge graph: entities with observations, queried via search_nodes/read_graph. It holds project/person/task knowledge, NOT pending ops — a pending id will never match anything there, so do not go hunting in the graph for it.

## Procedure

1. Grep the live files and the pending dir for the disputed text (match exact bytes, diacritics included): `grep -rn '<text>' $HERMES_HOME/memories $HERMES_HOME/pending/memory`. This single step usually locates every occurrence.
2. Read the matching pending JSON in full (`id`, `action`, `payload.old_text` vs `payload.content`) and the live file it targets. If the user quotes an id with no exact file match, try near-matches (single-character substitutions) before asking — quoted ids are often mistyped.
3. When the pending op asserts a fact about the environment (a tool missing from PATH, a path wrong, a service down), verify it live first — run the binary, check PATH, list the directory. A claim that was true when queued goes stale like any other text; withdraw the op when the claim no longer holds instead of applying a workaround for a problem that is gone.
4. Decide:
   - Live file already correct and pending op's `old_text` no longer matches anything live → the op is stale. Withdraw it by deleting its pending JSON; approving a stale replace would fail or reintroduce drift, and its stale text keeps surfacing in pending listings.
   - Live file still wrong and no pending op covers it → fix via the memory tool (replace with an `old_text` substring that matches live bytes exactly).
   - Pending op is current (old_text still matches live) but its new content is wrong → fix the live file via the memory tool and withdraw the pending op, rather than stacking a second op on top.
5. Re-grep both locations to verify the wrong text is gone everywhere.

## Pitfalls

- Never re-apply a correction that is already live — check the live files before writing any op; a duplicate replace against already-fixed text creates the next stale entry.
- Other pending files in the queue are unrelated until proven otherwise — read them before touching; withdraw only the stale one.
