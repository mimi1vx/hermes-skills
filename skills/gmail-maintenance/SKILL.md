---
name: gmail-maintenance
description: "Bulk Gmail cleanup via himalaya v2, keeping protected mail."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [Email, Gmail, IMAP, Maintenance, Cleanup, Himalaya]
---

# Gmail Bulk Maintenance (himalaya v2)

## When to Use

Use when the user asks to clean, purge, or maintain a Gmail mailbox in bulk
(promos, newsletters, automated notifications, CI/build mail) through the
himalaya v2 CLI. Trigger: any delete/archive/move request scoped by sender,
subject, or age rather than by individual message.

Remove promo and automated mail in bulk while provably keeping protected
mail (orders, payments, password/security). Default to read + scope, never
delete without an explicit approved set — presenting counts first is the job.

## Procedure

### 1. Scope with counts, one sender or rule at a time

`himalaya imap search` ANDs every flag; the footer `Found N` is the count.
Save each result to a file for later set arithmetic:

```bash
himalaya imap search -m Inbox --from "sender" --before <YYYY-MM-DD> > set.txt 2>&1
```

Useful axes: `--from`, `--subject`, `--before/--since`. `--subject` is
ASCII-only (see pitfalls). For multi-word or negated envelope queries use
`himalaya envelope search -m MBOX --json "from X and not subject Y"`.
Purging a whole label mailbox: `imap search -m LABEL` with no criteria
returns every UID in it. For whole-account totals use `mailbox list
--counts` (one STATUS per mailbox, slow on many labels) and split its
columns on `┆`, not `│`; `[Gmail]/All Mail` is the closest to a
unique-message count because labels duplicate.

### 2. Split mixed senders into keep-set and delete-set

Never bulk-delete a sender that mixes promo with protected mail. Extract
UIDs from each saved search and subtract the keep-set:

```bash
grep -o '│ [0-9]*' set.txt | grep -o '[0-9]*' | sort -n -u > set.uids
cat keep1.uids keep2.uids | sort -n -u > keep.uids
comm -23 all.uids keep.uids > del.uids
```

Typical keep-set: order/receipt/invoice/payment subjects, password/
verification/security subjects, the user's own-domain subjects, security
and dependency-update senders. Verify each keep-set returns its expected
count before subtracting.

### 3. Present the approval batch, then move in chunks

Report per rule: mailbox, selector, count to delete, what is kept, and
that the move is Trash-first (recoverable; Gmail auto-purges Trash after
30 days). Move with IMAP UIDs as a comma SEQUENCE, ~400 per call, in a
background job with a log when there are more than ~10 chunks:

```bash
himalaya imap move -m Inbox "$(paste -sd, chunk.csv)" "[Gmail]/Bin"
```

(`message delete` takes envelope IDs, `imap move` takes IMAP UIDs — for
search results always use `imap move` with UIDs. Confirm the real trash
name with `mailbox list` first: `[Gmail]/Bin` vs `[Gmail]/Trash`.)

### 4. Retry failures by splitting, then verify by exact deltas

On `NO System Error (Failure)`, retry once, then split the chunk (100s,
then 25s) and re-run — transient Gmail errors clear on smaller batches.
A chunk can half-succeed despite the error, so verify state, not exit
codes: the delete-set searches must return 0, keep-sets unchanged, and
`mailbox list --counts` must show Inbox −N / Trash +N exactly. Re-collect UID lists from fresh searches before any retry pass — moved UIDs vanish from the source mailbox, so stale lists mislead both retries and verification.

### 5. Make recurrence a script + cron, not a memory

Encode approved rules in a script (dynamic `--before $(date -d '14 days
ago' +%F)` cutoff, same keep-set subtraction, skip empty sets) and
register it as a `no_agent` script cron with local delivery. The cron `script` field takes a bare filename from the scripts dir (absolute paths are rejected). In `no_agent` mode empty stdout sends nothing, so exit quietly when there is nothing to move. A rule sweeping an active list subscription only bails water — check liveness with `envelope list -m LABEL -s 3` (newest-first dates) and unsubscribe at the source: `message read --raw` on a recent sample, take the `List-Unsubscribe` header (mailto or web link), and complete its confirmation round-trip.

## Pitfalls

- Trusting a move's exit code over mailbox state — a failed MOVE can still
deliver (Gmail Spam moves report failure after succeeding); always
re-search source and target to confirm where the mail is.
- Trusting a delegated scoping count — re-run the searches yourself before
presenting the approval batch, because a report's count can understate
reality by orders of magnitude; if your count differs from the approved
scope, stop and re-confirm with the user instead of deleting. When the
scope is an explicit ID range from a monitor report, re-list the live
inbox window first and act only on IDs confirmed present — IDs shift and
gaps appear; on any mismatch stop and ask for explicit IDs instead of
guessing.
- Sampling arbitrary UIDs to verify a set — IMAP UIDs are mailbox-wide, so
a guessed UID shows unrelated mail and misleads scoping; always read back
UIDs taken from the saved search-result UID files.
- Using IMAP `--subject` with non-ASCII text — diacritics silently match
nothing; use ASCII stems or `envelope search` for those.
- Piping himalaya output into an interpreter — blocked by the security
scanner; redirect to files and parse with grep/cut/sort, or write a
script file and run it by path.
- Precomputing UID sets across several label mailboxes, then moving in
one pass — trashing from one label trashes the whole message globally,
so every later set is stale and the moves warn on missing UIDs; search
and move one mailbox at a time, inside the loop.
- Deleting a whole sender that also sends receipts or security mail —
check order/payment/password/security/token subjects per sender first;
the keep-set is what makes bulk deletion safe.
