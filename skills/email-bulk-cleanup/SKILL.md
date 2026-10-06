---
name: email-bulk-cleanup
description: "Bulk-delete mailbox messages by sender, subject, or age."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Email, IMAP, Gmail, Bulk, Cleanup, Maintenance]
    related_skills: [himalaya-v2, email-inbox-triage]
---

# Email Bulk Cleanup

Delete thousands of messages by sender/subject/age while keeping protected
categories. Procedure below assumes himalaya v2 over IMAP/Gmail; the
scoping and verification discipline applies to any backend.

Pairs with email-inbox-triage: that skill owns the approval batch — never
execute a destructive scope without explicit user approval of the delete set.

## When to Use

- "Delete all newsletters / promos / bot mails older than X"
- "Clean out this sender / label, keeping receipts and security mail"
- Any delete set over ~50 messages where sender alone may mix noise with
  records worth keeping.

## Procedure

### 1. Scope the delete set

- Start from `himalaya mailbox list --counts` to find heavy mailboxes.
- Count candidates per sender: `himalaya imap search -m BOX --from "addr"`
  (tails print `Found N message(s)`).
- `imap search` flags AND together: combine `--from`, `--subject`, `--before
  YYYY-MM-DD` (internal/received date). `--subject` matches a substring;
  non-ASCII subjects may not match — verify counts are non-zero before
  relying on a keyword.
- Sample with `himalaya envelope search -m BOX -s N --json "from X and
  subject Y"` (note the `and`; bare juxtaposition is a parse error) and read
  subjects before committing to a rule.

### 2. Prove the keeps are outside the delete set

- Never bulk-delete a mixed sender (one From that sends both promos and
  receipts/security mail) — a subject filter or UID subtraction is mandatory,
  because sender alone cannot separate them.
- For every protected category (orders, receipts, payments, passwords,
  security alerts, account notices), run a subject search inside the candidate
  set and require zero hits before deleting.
- Build the delete set as UID files and subtract keep sets with
  `comm -23 delete.uids keep.uids` — keeps stay enumerable and auditable.

### 3. Move in chunks, then verify exactly

- `himalaya imap move -m SRC "uid1,uid2,..." "TARGET"` takes IMAP UIDs.
  `himalaya message delete/move` takes envelope IDs instead — the two ID
  spaces look alike but are NOT interchangeable; pick one and stay in it.
  Build comma sequences with `paste -sd,` and move ~400 UIDs per call.
- On transient `NO System Error` failures, retry the chunk, then halve it
  (100, then 25) — partial moves happen, so re-derive leftovers from a fresh
  search rather than assuming all-or-nothing.
- Gmail Trash is `[Gmail]/Bin` on some accounts, `[Gmail]/Trash` on others —
  confirm via `mailbox list`. Trash auto-purges after 30 days, so moves stay
  recoverable short-term.
- Do NOT move to `[Gmail]/Spam` over IMAP: Gmail rejects it (the move may
  half-apply and still report failure). Route to Trash instead.
- Verify with exact arithmetic: source-mailbox delta must equal Trash delta
  must equal the UID count. Re-run delete-set searches (expect 0) and
  keep-set searches (expect unchanged). A mismatch means leftovers —
  re-search and finish them.
- Redirect search output to files and extract UIDs with grep/sort; avoid
  piping CLI output straight into an interpreter.
