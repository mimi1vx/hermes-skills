#!/usr/bin/env python3
"""Send a photo, document, or video over the Telegram Bot API.

Usage:
  send_media.py --chat <chatId> --photo /path/to/image.png
  send_media.py --chat <chatId> --photo 987654321 --caption "see attached"
  send_media.py --chat <chatId> --video /path/to/file.mp4
  send_media.py --video 987654321            # chat defaults to $TELEGRAM_HOME_CHANNEL

A ``--photo`` / ``--video`` / ``--document`` value may be:
  - a local file path (upload is sent with its real filename), or
  - a Telegram ``file_id`` returned from a previous upload.

On success prints the Telegram result object; exit code 0 on success,
1 on any error. The token is loaded from the environment (or .env) and
never stored in this skill.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _api_lib import TelegramError, load_token, send_media  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Send a photo, video, or document via the Telegram Bot API."
    )
    ap.add_argument(
        "--chat",
        default=None,
        help="Recipient chatId. Defaults to $TELEGRAM_HOME_CHANNEL.",
    )
    ap.add_argument("--photo", help="Local path or file_id for a photo.")
    ap.add_argument("--video", help="Local path or file_id for a video.")
    ap.add_argument("--document", help="Local path or file_id for a document.")
    ap.add_argument("--caption", default=None, help="Optional caption.")
    args = ap.parse_args()

    field_file = {"photo": args.photo, "video": args.video, "document": args.document}
    field = next((k for k, v in field_file.items() if v), None)
    file_value = field_file.get(field)
    if not field:
        print("error: provide --photo, --video, or --document", file=sys.stderr)
        return 1
    if not file_value:
        print(f"error: --{field} requires a value", file=sys.stderr)
        return 1

    chat = args.chat or os.environ.get("TELEGRAM_HOME_CHANNEL") or ""
    if not chat:
        print(
            "error: no recipient — pass --chat <chatId> or set TELEGRAM_HOME_CHANNEL",
            file=sys.stderr,
        )
        return 1

    token = load_token()
    try:
        result = send_media(token, str(chat), file_value, field=field,
                            caption=args.caption)
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
