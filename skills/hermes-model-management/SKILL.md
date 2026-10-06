---
name: hermes-model-management
description: "Use when Hermes inference needs changing or diagnosis."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, models, providers, fallback, consent]
---

# Hermes Model Management

Manage this Hermes install's inference: which model/provider serves turns,
the fallback chain, and consent for data-training tiers. Home is `$HERMES_HOME`
(exported in the environment; not necessarily `$HOME`) — never hardcode
`~/.hermes` or any absolute path; resolve it live.

## When to Use

Model or provider changes, fallback-chain edits, rate-limit / 502 / timeout
diagnosis on Hermes inference, and any request involving contributor or
other data-training model tiers.

## Procedure

1. Inspect before touching. Read the live state, in this order:
   `grep -A8 '^model:' $HERMES_HOME/config.yaml`, then `fallback_providers`,
   then `security`. Check departure from the session header (Model/Provider
   lines) — a mismatch means a fallback or override is currently serving.
2. Diagnose provider errors in `$HERMES_HOME/logs/errors.log` and `gateway.log`:
   HTTP 429 on the primary is transient upstream rate limiting — wait, do not
   reconfigure; the fallback chain covers the gap. HTTP 502 / DNS failures on
   `custom` LAN-box URLs mean that box or its upstream is unreachable from here
   (VPN-gated domains never resolve in this container). Stream TTFB timeouts
   with an accepted connection means the backend stalled, not a config break.
   Before reordering fallbacks over custom endpoints, probe each one live
   (`curl -m 8 <base_url>/models`): logs show past failures, only a probe shows
   current reachability and the exact model ids to put in the chain — order
   healthy-first.
   A gateway warning that OPENAI_BASE_URL is set while model.provider differs
   means auxiliary calls (titles, summaries) may route to the wrong endpoint —
   fix with `hermes model` or by removing that env var from $HERMES_HOME/.env.
3. Change via commands, never by hand-editing config.yaml (a stray indent
   corrupts the live gateway). Interactive pick: `hermes model` / `hermes setup`.
   Single key: `hermes config set <dotted.key> <value>`.
   Fallback chain: `hermes fallback add|remove|list`. Any programmatic edit
   must go through `hermes_cli.config.atomic_config_write` (the same
   comment-preserving writer `config set` uses) — never a raw YAML dump.
   After a fallback edit, verify the normalized chain order
   (`get_fallback_chain`) — no gateway restart needed, the runner re-reads
   `fallback_providers` per turn.
4. Contributor / data-training consent has TWO independent halves — set the
   Hermes half with tools, direct the user through the provider half:
   Hermes half: any model id matching `*-contributor` trips the data-training
   guard (`hermes_cli/model_data_policy_guard.py`) on every selection surface.
   Interactive confirms (`hermes model`, startup override, gateway /model)
   ask [y/N] every time by design — no persistent bypass exists for them.
   The only standing acknowledgment is unattended runs:
   `hermes config set security.allow_data_training_tiers_noninteractive true`.
   Provider half: the vendor dashboard opt-in (e.g. opencode's "allow models
   that train on request data") can only be clicked by the user — never
   settable from here. If calls still fail after both halves, suspect a vendor
   region block before re-diagnosing config. Detail: `references/data-training-tiers.md`.

## Standing rules

- Consent first, command second: state what a data-training tier permits
  (vendor trains on prompts and completions) before enabling it, and keep
  employer, client, secret, or personal material off training tiers.
- Never present a silent interactive prompt as broken — the per-selection
  confirm is intentional even with the noninteractive flag set.
- Price and region facts rot fast; verify against the vendor's current terms
  instead of quoting remembered numbers.
