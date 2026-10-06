---
name: whatsapp
description: "Send and read WhatsApp messages through the local bridge."
version: 0.2.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
required_environment_variables:
  - name: WHATSAPP_HOME_CHANNEL
    prompt: "Your WhatsApp number (self-chat JID or digits)"
    help: "Default recipient when --phone/--chat are omitted"
    optional: true
metadata:
  tags: [whatsapp, messaging, bridge, self-chat]
  related_skills: []
---

# WhatsApp — Send and Read via the Local Bridge

`whatsapp` delivers outbound messages and reads inbound traffic through the local
Her message bridge (`@whiskeysockets/baileys`), not an exposed MCP tool. Use it to
send text, edit sent messages, send media/location/polls, or read new inbound
messages. This skill covers *sending and reading*; it does not set up or pair a
session.

Scripts live in `scripts/` and share `_bridge_lib.py`, which auto-detects the
bridge port, probes `/health` (fail-fast if not `connected`), enforces the
mandatory Host header, and normalizes chat IDs — so the helpers below need no
port plumbing or JID math on your part.

## When to Use

- User asks to send a WhatsApp message (text, media, location pin) or a poll.
- User asks to read or reply to WhatsApp chats.

Don't use it for: X/Twitter (see `xurl`), SMS, Telegram, or signal.

## Prerequisites

- A WhatsApp bridge process running on loopback (see Setup below). Confirm it is
  `connected` before attempting any send — a `disconnected` health check means the
  socket has logged out and the send will fail.
- Optionally set `WHATSAPP_HOME_CHANNEL` (digits or a full JID) so sends to
  yourself need no `--phone` on the command line.

## How to Run

Send text:

```bash
python3 <skills>/<whatsapp>/scripts/send_text.py --phone <digits> --text "<message>"
# or, with WHATSAPP_HOME_CHANNEL set:
python3 <skills>/<whatsapp>/scripts/send_text.py --text "<message>"
```

Other helpers (all share `_bridge_lib.py`):

```bash
# Read new inbound events (drains the queue, long-polls the bridge)
python3 <skills>/<whatsapp>/scripts/read_messages.py --pretty

# Edit a previously sent message
python3 <skills>/<whatsapp>/scripts/...  # see bridge_protocol.md for the endpoint
```

`send_text.py` auto-detects the bridge port, probes `/health` (fail-fast if not
`connected`), normalizes the phone number to a JID, and hits `POST /send` with
the correct Host header. It prints the bridge JSON on success:
`{"success":true,"messageId":"...","messageIds":[...]}`.

## Core Procedure

### Sending text
1. **Confirm the bridge is reachable.** `send_text.py` does this for you
   (it probes `/health` and raises `BridgeError` if not `connected`). To do it
   by hand: `curl -s -H 'Host: 127.0.0.1' http://127.0.0.1:3000/health`.
2. **Pick the recipient.** Pass `--phone <digits>` (normalized to
   `<digits>@s.whatsapp.net` automatically) or `--chat` with a full JID
   (group `@g.us`, linked-device `@lid`). Omit both to send to
   `WHATSAPP_HOME_CHANNEL` (your own number in self-chat mode).
3. **Send.** A `success:true` response with a non-null `messageId` is the only
   proof a message left the machine. `/send` is synchronous — the call returns
   after Baileys resolves, so treat any non-200 or `error` field as "not sent."
4. **Report only from the response.** Return the `messageId`; never claim
   delivery from a curl exit code or a summary.

### Reading inbound messages

`GET /messages` long-polls and then DRAINS the in-memory queue, so each run
reports only events no earlier run saw (nothing is ever reported twice). Use
`read_messages.py --pretty` to inspect them; events carry `messageId`, `chatId`,
`senderId`, `senderName`, `body`, `hasMedia`, `mediaType`, `quotedMessageId`,
`readReceiptKey` (for `POST /read`), and `timestamp`.

## Pitfalls

- **Host header is mandatory.** The bridge validates every request's `Host` header
  against loopback values and returns HTTP 400 ("Invalid Host header") otherwise.
  Send `-H "Host: 127.0.0.1"` — it is not optional.
- **Body-as-file, not inline.** When using `terminal`, write the JSON to a file
  and pass it via `--data @file`. Inlining a JSON string after `-d` double-escapes
  the quotes and yields a `JSON.parse` SyntaxError (bad input, not a bridge bug).
- **JID format.** Sending to a bare number without the `@s.whatsapp.net`
  suffix fails to route. Always normalize to the full JID first.
- **Self-chat mode by default.** A bridge running in `self-chat` mode processes
  only messages addressed to your own number. Any other recipient must be listed
  in `WHATASAPP_ALLOWED_USERS`, or sends to it are rejected. Check `bridge.js`
  (`--mode`) to know which mode is active; in `bot` mode the number in `WHATSAPP_
  DM_POLICY=pairing` gets paired on demand.
- **`/send` is synchronous.** The HTTP call returns only after Baileys resolves
  the send (up to the configured send timeout). Treat a non-200 response or an
  `error` field as the send not happening; a `200` with `success:true` means it
  was accepted by the bridge (not proof of final delivery).
- **Allowing another WhatsApp user grants them the full agent, not a limited
  account.** Gateway slash gating (`allow_admin_from` /
  `user_allowed_commands`) trims slash commands only — plain-chat turns run
  with the same toolset for every allowed user, and dangerous-command approval
  prompts arrive in the requester's own chat, so they self-approve. Treat a
  second allowed user as handing over the agent; real isolation needs a
  separate profile with a trimmed toolset on a separate number.

## Bridge Endpoints

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/health` | GET | Connection state, queue length. Always probe first. |
| `/send` | POST | Send text `{chatId, message}`. |
| `/edit` | POST | Edit a sent message `{chatId, messageId, message}`. |
| `/send-media` | POST | Send image/video/audio/document `{chatId, filePath, caption?}`. |
| `/send-poll` | POST | Create a poll `{chatId, question, options, selectableCount}`. |
| `/send-location` | POST | Drop a pin `{chatId, latitude, longitude, name?}`. |
| `/typing` | POST | Send a composing indicator. |
| `/read` | POST | Mark a message read. |
| `/chat/:id` | GET | Resolve a chat's name/participants. |
| `/messages` | GET | Long-poll for new inbound messages. |

The bridge defaults to port 3000 on `127.0.0.1` only. If it was launched on a
different port, read the running process (`ps aux | grep bridge.js`) to find the
`--port` value and pass it explicitly (see the helper script).

## References

- `references/bridge_protocol.md` — exact request/response schemas and the
  inbound event shape for every bridge endpoint (grounded in `bridge.js`).
- `scripts/` — reusable helpers that share `_bridge_lib.py`:
  - `_bridge_lib.py` — port auto-detection, `/health` probing, JID
    normalization, request/response plumbing (stdlib only, no deps).
  - `send_text.py` — send text (with `--reply-to` / `--mentions`); probes
    health, normalizes `--phone`, calls `POST /send`.
  - `read_messages.py` — GET `/messages`, drains and prints the inbound queue.
