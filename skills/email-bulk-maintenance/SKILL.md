---
name: email-bulk-maintenance
description: "Bulk-delete promos, keep orders and security mail."
version: 1.0.0
author: curator
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Email, Maintenance, Promos, Newsletters, Safety]
---

# Email Bulk Maintenance

Delete promo/newsletter batches without destroying orders, payments, password resets, or security alerts.

## When to Use

- "Delete promos / newsletters / ads, keep orders and security mail."
- Gmail maintenance passes over large inboxes or dedicated promo folders.
- Any bulk `noise` deletion where one brand sends both marketing and transactional mail.

## Procedure

### 1. Scope and count first

List mailboxes with counts. Treat dedicated promo folders as the cheapest batch. For inbox leaks,
identify promo-only senders by exact address, never by domain. Done when every batch has an exact count.

```bash
himalaya mailbox list --counts
himalaya envelope list -m <BOX> -s 25 -p 1 --json
himalaya envelope search -m <BOX> -s 10 --json "from <exact-sender>"
himalaya imap search -m <BOX> --from "<exact-sender>"        # ANDed keys, footer reports Found N
himalaya imap search -m <BOX> --from "<exact-sender>" --subject "sale"
```

Global flags go BEFORE the quoted query: the search query is greedy, so a `--json`
placed after it is swallowed into the filter and fails with a query-parse error.
The safe shape is `himalaya --json envelope search -m <BOX> -s 500 "from X"`.

Count exactly: the `imap search` footer `Found N` is authoritative; UID rows match `^\u2502 [0-9]`.
Do not estimate from truncated table output. Redirect large results to a file and count rows.

### 2. Prove promo-only before proposing deletion

For each candidate sender, search the same mailbox for protected subjects: order, receipt, invoice,
payment, billing, password, reset, verification, verify, security, alert (plus local-language
equivalents when the mailbox is non-English). In inflected languages screen stem fragments, not
whole words: Czech noun/verb inflections evade whole-word screens (hesla missed heslo,
objednavky/objednavce missed objednavka), so add stem variants (objednavk*, faktur*, platb*,
 overov*/overeni, hesla/heslem) and expect diacritic forms to fail over IMAP — pair the
IMAP screen with a full subject listing scan before clearing a sender.

- Keep: order confirmations ("Your order #... is complete", "Your store order is ready"),
  account-link notices, anything with a password/security subject.
- Promo: pre-order marketing ("Pre-order X today"), sales, discounts, bundles, newsletters.
- Confirm one sample with `himalaya message read <id> -m <BOX> --raw`: promo normally carries
  `List-Unsubscribe`; use it as supporting evidence, never as the sole criterion.
- Inspect the subject line of every protected-subject hit before clearing it: keywords
  false-positive inside promo content (job titles containing Security, headlines containing
  alert, payment-feature marketing), so a hit count alone proves nothing — only subjects
  showing real orders, receipts, or account notices are protected.

### 3. Propose, then delete

Present per-sender counts (mailbox, exact sender, count, action) and delete only after explicit
approval, individually or as a defined batch. `message delete` is trash-first, so name the trash
mailbox in the proposal for recoverability. Mixed senders stay untouched or get a subject-filtered
second pass, never a bulk delete.

```bash
himalaya message read <id> -m <BOX> --raw | head -n 80
himalaya message delete <id>... -m <BOX>
```

Large batches (100+): move by IMAP UID in chunks of ~100 through the trash mailbox
named in `mailbox list --counts` (`[Gmail]/Bin` vs `[Gmail]/Trash` varies per account):

```bash
himalaya imap search -m <BOX> --from "<sender>" > batch.txt  # re-fetch AFTER any test move
# extract UIDs, join ~100 per line into comma sequences, then per chunk:
himalaya imap move -m <BOX> "uid1,uid2,..." "[Gmail]/Bin"
```

`message delete` takes envelope `id` values; `imap move` takes IMAP `UID` values from
`imap search`. The two numbers for one message differ — match the command to the ID type.
Keep `message delete` invocations modest (~10 IDs per call) to stay clear of command-line
limits on long ID lists.
Re-fetch UID lists after every test move; a stale list replays an already-moved UID.
A ready-made loop implementing the chunking plus per-sender verification lives in
`scripts/chunk-move.sh` — prefer invoking it over hand-typing chunks.

### Fanning out large cleanups

When dozens of senders need triage, dispatch read-only triage workers (one task per
sender cluster) through a kanban board instead of doing every sender inline. Each task
body carries the candidate senders, the protected-subject rules, and an explicit NO-deletes
constraint — workers post a sender/count/verdict/proposal table as a task comment and
never delete. The human then approves batch by batch and executes the moves directly,
so no background process ever holds delete authority.

## Pitfalls

- Bulk-deleting by domain: one brand can send promos from a mailer/newsletter subdomain and orders
  plus account notices from sibling senders — split by exact sender address and verify with a subject search.
- Treating "pre-order" marketing as an order: search for receipt, payment, invoice, and password subjects
  separately; only order-ready confirmations and account notices are protected.
- Estimating counts from a truncated page: page through or use the `Found N` footer, one number per batch.
- Deleting mixed senders in one shot: sale notices and security alerts can share one address;
  leave mixed senders for a subject-filtered pass.
- Replaying a UID list captured before a test move: re-fetch after any single test move/delete,
  or the first bulk chunk fails on the already-moved item.
- Executing from triage counts: never move from numbers gathered during triage — mail arrives
  constantly and the mailbox shifts underneath you, so run a fresh `imap search` per sender
  at execution time and move exactly what it returns.
- Parsing UIDs with a bare digit grep over full search output: once a count reaches 4 digits the
  `Found N` footer line itself matches and one innocent message rides along into the move list —
  extract UIDs only from table body rows (`^│ [0-9]`), never from the footer.
- Assuming the trash name: read it from `mailbox list` per account instead of guessing `Trash`.

## Verification

- [ ] Every batch has an exact count traceable to a search footer.
- [ ] Every deleted sender was proven promo-only via protected-subject searches.
- [ ] Orders, payments, password resets, and security alerts have a named home that was excluded.
- [ ] Deletion happened only inside the approved batch and names the trash mailbox.
- [ ] Trash delta equals the total moved; each promo sender re-searches to `Found 0 message(s)`.
