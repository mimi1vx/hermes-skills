---
name: self-hosted-title-400
description: "Resolve title-call 400 messages could not be rendered."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [title, response_format, 400, self-hosted]
    related_skills: [hermes-agent]
---

# Self-hosted title-call 400 'messages could not be rendered'

## Root cause
Title generation always sends `response_format: json_schema` (see `agent/title_generator.py::_TITLE_RESPONSE_FORMAT`). Some self-hosted OpenAI-compatible engines reject that field with HTTP 400 "messages could not be rendered", yet complete (200) without it. It is a `response_format` rejection, not a config bug.

## Fix: pin the title to the other endpoint (do not add a 2nd model to the single-slot server)
Self-hosted single-slot servers (LLM Studio, Ollama) run one model at a time. Pin title generation to the OTHER endpoint. Config reads fresh per call (`load_config_readonly()`), so no gateway restart is required.

1. Confirm the current endpoint rejects `response_format` and the fallback accepts it (test with `terminal` + curl; load the model first — Ollama/LLM Studio idle-eject: hit `/api/pull`, `/api/load`, or just chat before testing).
2. Pin via the sanctioned CLI (config.yaml is write-guarded — edit it directly through `hermes config set`):
   `hermes config set --force auxiliary.title_generation '{"provider":"custom:suse-ollama-gpu","model":"default:latest","timeout":30}'`
   Back up first: `cp "$HERMES_HOME/config.yaml" "$HERMES_HOME/config.yaml.bak"`.
3. Verify resolution: `hermes config get auxiliary.title_generation`.
4. Prove the route takes the real payload (not an empty request): run `call_llm(task="title_generation", ...)` through running Python — expect 200 with a parsed `title`.

## Source-side fix (needs root)
`agent/auxiliary_client.py::_is_structured_output_rejection` (line ~3331) has vendor branches (vLLM `guided_grammar`, Gemini `response mime type`, DeepSeek `unavailable`) but not 'messages could not be rendered'. Add one guarded by `status in {400,422}` so the retry ladder strips `response_format`. Edit `agent/auxiliary_client.py` directly (root-owned; no sudo).

## Pitfalls
- Ollama models idle-eject; an empty/503 response right after load is often 'still loading' — load first, test second.
- A `max_tokens=64` title can truncate mid-JSON: that is truncation, not a rejection — check the HTTP code, not whether the JSON is complete.
- The gateway reads config per call, so a pin takes effect on the next new session without a restart.
