---
name: telegram
description: "Send Telegram messages through the official Bot API."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
required_environment_variables:
  - name: TELEGRAM_BOT_TOKEN
    prompt: "Telegram bot token"
    help: "Bot token from @BotFather; the skill also reads it from the profile .env"
    required_for: sending any message
  - name: TELEGRAM_HOME_CHANNEL
    prompt: "Default Telegram chatId"
    help: "Used when --chat is omitted; keeps personal ids out of shell history"
    optional: true
metadata:
  tags: [telegram, messaging, bot-api]
  related_skills: [whatsapp]
---

# Telegram — Send via the Official Bot API

`telegram` sends outbound text and media through the official Telegram Bot
API (`https://api.telegram.org/bot<token>/<method>`), not the local bridge the
`whatsapp` skill uses. Use it to push a message to a specific chatId — for
example from a cron job or a script — without depending on the running
gateway. It reads the bot token at runtime and never stores it.

This skill covers **sending** only. Inbound `getUpdates` is deliberately absent:
the Hermes gateway **polls this same bot**, and a competing update-consuming
request would steal updates and break this channel's routing (see Pitfalls).
To *read* new messages, use the gateway's own channel delivery, not this skill.

## When to Use

- A user (or a cron job) asks to push a Telegram message to a particular chatId.
- You need to send text, a photo, a video, or a document.

Don't use it for: WhatsApp (use `whatsapp`), reading inbound messages (use the
gateway), or direct messaging via the running gateway session.

## Prerequisites

- A Telegram bot token in the environment variable `TELEGRAM_BOT_TOKEN`, or
  set in the profile `.env` file (`$HERMES_HOME/.env`). The token is read from
  there at runtime — nothing about it is stored in this skill. Verify once with
  a masked probe:
  ```bash
  python3 <skill_dir>/scripts/send_text.py --help
  ```
- Optionally set `TELEGRAM_HOME_CHANNEL` to your own chat id; both scripts then
  default to it when `--chat` is omitted, so no personal id needs to appear in
  a command line.

## How to Run

Send text:

```bash
python3 <skill_dir>/scripts/send_text.py --chat <chatId> --text "<message>"
# or, with TELEGRAM_HOME_CHANNEL set:
python3 <skill_dir>/scripts/send_text.py --text "<message>"
```

Send a photo, video, or document (path or a `file_id` from a prior upload):

```bash
python3 <skill_dir>/scripts/send_media.py --chat <chatId> --photo <path-or-file_id> --caption "optional"
python3 <skill_dir>/scripts/send_media.py --chat <chatId> --video <path>
python3 <skill_dir>/scripts/send_media.py --chat <chatId> --document <path>
```

## Quick Reference

- Send text: `scripts/send_text.py --chat <id> --text "<msg>" [--thread <id>] [--reply-to <id>]`
- Send media: `scripts/send_media.py --chat <id> --photo|--video|--document <path-or-file_id> [--caption "<text>"]`
- `--chat` may be omitted when `TELEGRAM_HOME_CHANNEL` is set.

## Procedure

1. **Confirm the token resolves.** Run either script with `--help`; if it
   prints usage instead of raising, the token is found in the environment or
   `.env`.
2. **Pick the chatId.** Read the target from `TELEGRAM_HOME_CHANNEL` when
   sending to yourself; pass `--chat` explicitly for any other chat (a forum
   topic also needs `--thread <id>`).
3. **Send.** A JSON response with `"ok":true` and a non-null `message_id`
   proves the message left the machine; a non-200 or `{"ok":false,...}` body
   means the send did not happen.
4. **Report only from the response.** Print the returned `message_id` as proof;
   never claim delivery from an exit code alone.

## Pitfalls

- **Token stays out of the skill.** `send_text.py` / `send_media.py` read
  `TELEGRAM_BOT_TOKEN` (falling back to the local `.env`) at runtime. Never
  paste a token into a committed file.
- **Do not call `getUpdates`.** The Hermes gateway polls this same bot, so any
  competing `getUpdates` updates the offset and silently breaks chat routing.
  Reading inbound is a gateway concern, not a skill concern.
- **chatId shape.** Pass a bare number (`123456789`) or a forum thread with
  `--thread <id>`; a JID form is not needed here. Prefer reading the recipient
  from `TELEGRAM_HOME_CHANNEL` (the skill's own default) rather than pasting a
  chat id into a command line, where it ends up in shell history and logs.
- **Multipart uploads.** `send_media.py` sends the file with its real filename;
  a `file_id` sent back by one call can be reused in a later call.
- **Mute / reply control.** Optional `--thread`, `--reply-to`, and `--caption`
  map to the Bot API `message_thread_id`, `reply_to_message_id`, and `caption`
  parameters.

## Verification

After a send, check the target chat for the message (or reply) you just sent.
The printed `"message_id"` from the response is the proof that was accepted.
For a dry smoke test, send a short message to the home chat and confirm it
arrives.
