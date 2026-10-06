# Hermes Skills — mimi1vx

Personal collection of [Hermes Agent](https://hermes-agent.nousresearch.com) skills — reusable
procedures for coding review, debugging, testing, messaging, email, and research workflows.

38 skills, all MIT.

## Install

Browse everything:

    hermes skills tap add mimi1vx/hermes-skills
    hermes skills browse --source mimi1vx/hermes-skills

Install one:

    hermes skills install mimi1vx/hermes-skills/<skill-name> --to github

Preview before installing:

    hermes skills inspect mimi1vx/hermes-skills/<skill-name> --to github

## Layout

Flat `skills/<name>/` — one directory per skill, each with a `SKILL.md` plus optional
`references/`, `scripts/`, `templates/`. The flat layout is deliberate: the hub's tap browser
lists directories under `skills/` and reads `<dir>/SKILL.md`, so a nested
`skills/<category>/<name>/` layout would be skipped during browse. Categories are carried by
`skills.sh.json` at the repo root instead, which the hub reads for category labels.

## Skills

### Software development

| Skill | Description |
| --- | --- |
| [change-walkthrough](skills/change-walkthrough) | Conversational explanation of a diff or PR |
| [changelog-generator](skills/changelog-generator) | User-facing changelogs from git history |
| [debug-loop](skills/debug-loop) | Reproduce, isolate, hypothesize, test, fix |
| [deep-performance-audit](skills/deep-performance-audit) | Profile, optimize, prove equivalence |
| [deep-project-primer](skills/deep-project-primer) | Understand an unfamiliar codebase first |
| [git-commit](skills/git-commit) | Storytelling Conventional Commits messages |
| [idea-wizard](skills/idea-wizard) | Generate and rank improvement ideas |
| [karpathy-guidelines](skills/karpathy-guidelines) | Behavioral rules for LLM coding work |
| [pr-review](skills/pr-review) | Pre-PR checklist and reviewer briefing |
| [readme-reviser](skills/readme-reviser) | Sync docs with the current code |
| [spec-to-plan](skills/spec-to-plan) | Feature request to spec to task list |
| [sota-architecture](skills/sota-architecture) | System architecture rules and audits |
| [sota-async-concurrency](skills/sota-async-concurrency) | Async/concurrent code rules and audits |
| [sota-code-security](skills/sota-code-security) | Secure coding and security auditing rules |
| [sota-haskell](skills/sota-haskell) | Haskell engineering (2026) |
| [sota-llm-engineering](skills/sota-llm-engineering) | LLM application engineering rules |
| [sota-ml-engineering](skills/sota-ml-engineering) | ML engineering and MLOps rules |
| [sota-observability](skills/sota-observability) | Observability and reliability rules |
| [sota-perl](skills/sota-perl) | Perl 5 engineering (2026) |
| [sota-python](skills/sota-python) | Python engineering and auditing |
| [sota-rust](skills/sota-rust) | Rust engineering (2026) |
| [sota-testing](skills/sota-testing) | Testing strategy and practice |
| [sota-typescript](skills/sota-typescript) | TypeScript and JavaScript (2026) |

### Autonomous AI agents

| Skill | Description |
| --- | --- |
| [hermes-memory-maintenance](skills/hermes-memory-maintenance) | Fix wrong, stale, or duplicate memories |
| [hermes-model-management](skills/hermes-model-management) | Change or diagnose Hermes inference |
| [kanban-dispatch](skills/kanban-dispatch) | Dispatch background work to kanban workers |
| [opencode-v2](skills/opencode-v2) | Drive OpenCode V2 via its server API |

### Messaging and email

| Skill | Description |
| --- | --- |
| [telegram](skills/telegram) | Send Telegram messages via the Bot API |
| [whatsapp](skills/whatsapp) | Send and read WhatsApp via the local bridge |
| [himalaya-v2](skills/himalaya-v2) | Himalaya v2 CLI email client |
| [email-bulk-cleanup](skills/email-bulk-cleanup) | Bulk-delete mail by sender, subject, age |
| [email-bulk-maintenance](skills/email-bulk-maintenance) | Delete promos, keep orders and security mail |
| [gmail-maintenance](skills/gmail-maintenance) | Bulk Gmail cleanup, keeping protected mail |

### Research and productivity

| Skill | Description |
| --- | --- |
| [webnovel-scrape-pack](skills/webnovel-scrape-pack) | Scrape a novel series into epub/pdf/txt |
| [ste-english](skills/ste-english) | Write in Simplified Technical English |

### DevOps

| Skill | Description |
| --- | --- |
| [apple-container](skills/apple-container) | Apple's `container` CLI, pinned to arm64 |
| [self-hosted-title-400](skills/self-hosted-title-400) | Fix unrenderable title-call 400 errors |
| [github](skills/github) | GitHub via `gh` CLI (vendored — see below) |

## Configuration

Skills that need credentials declare them in `required_environment_variables`, so the agent
prompts for a missing value and tells you which install is missing what. Nothing secret is stored
in this repo. Personal identifiers are read from the environment or the profile `.env`
(`$HERMES_HOME/.env`):

- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_HOME_CHANNEL`
- `WHATSAPP_HOME_CHANNEL`

## Attribution

Most skills here were written for my own use. A few are adapted from the Hermes Agent bundled set
or community contributions, and keep their original authors in the frontmatter `author` field:

- [`github`](skills/github) — Ben Barclay (benbarclay), MIT. Vendored from the Hermes Agent
  bundled set, with an added `references/monitoring.md`. Upstream:
  <https://github.com/NousResearch/hermes-agent>
- [`himalaya-v2`](skills/himalaya-v2) — community contribution, MIT
- Skills marked `author: Hermes Agent` — drafted with Hermes on my machine

Upstream project and full attribution for every bundled skill:
<https://github.com/NousResearch/hermes-agent>

## License

MIT. See [LICENSE](LICENSE).