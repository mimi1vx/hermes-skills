#!/usr/bin/env python3
"""Send a text message over the Telegram Bot API.

Usage:
  send_text.py --chat <chatId> --text "hello"
  send_text.py --chat <chatId> --text "hi" --thread 12345
  send_text.py --chat <chatId> --text "hi" --reply-to 90
  TELEGRAM_HOME_CHANNEL=123456789 send_text.py --text "hi"   # default recipient

Loads the bot token from the environment (``TELEGRAM_BOT_TOKEN``) or the local
``.env`` file automatically — the token is never stored in this skill.

On success prints the Telegram ``result`` object:
  {"ok":true,"message_id":123,...}
Exit code 0 on success, 1 on any error.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _api_lib import TelegramError, load_token, send_text  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Send a text message via the Telegram Bot API."
    )
    ap.add_argument(
        "--chat",
        default=None,
        help="Recipient chatId (number/thread). Defaults to $TELEGRAM_HOME_CHANNEL.",
    )
    ap.add_argument("--text", required=True, help="Text message body.")
    ap.add_argument(
        "--thread",
        type=int,
        default=None,
        help="Forum topic thread_id (channel/forum topics only).",
    )
    ap.add_argument(
        "--reply-to",
        default=None,
        help="messageId to reply to (for channel posts, message_id).",
    )
    args = ap.parse_args()

    if not args.text:
        print("error: --text is required", file=sys.stderr)
        return 1

    chat = args.chat or os.environ.get("TELEGRAM_HOME_CHANNEL") or ""
    if not chat:
        print(
            "error: no recipient — pass --chat <chatId> or set TELEGRAM_HOME_CHANNEL",
            file=sys.stderr,
        )
        return 1

    token = load_token()
    params = {}
    if args.thread:
        params["message_thread_id"] = str(args.thread)
    elif args.reply_to:
        params["reply_to_message_id"] = str(args.reply_to)

    try:
        result = send_text(token, str(chat), args.text, **params)
    except TelegramError as err:
        print(
            json.dumps({"ok": False, "error": str(err)}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
