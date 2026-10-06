# Data-Training Tiers (Vendor Quirks)

Discounted inference tiers that are cheap because the vendor trains on your
traffic. Hermes matches them by model id: any id ending in `-contributor`
(see `hermes_cli/model_data_policy_guard.py`, the single source of the rule).

## Meta contributor tier

- Commercial difference is data use, not documented capability: prompts and
  completions may train future vendor models. Standard variant (same id
  without the suffix) does not.
- Discount is steep (order-of-magnitude token pricing); never quote remembered
  numbers — verify the vendor's current pricing page per session.
- Gateway access (e.g. opencode) additionally requires the user's own
  dashboard opt-in, typically labelled "allow models that train on request
  data". It cannot be set via Hermes tools or config; the user clicks it.
- The vendor geo-restricts the tier in some regions; a correctly consented
  setup that still fails is a region block until proven otherwise.
- Routing rule: training tiers only for material the user has the right to
  contribute — public, synthetic, or explicitly approved code. Client, employer,
  secret, personal, or regulated content stays on non-training routes.
