#!/usr/bin/env python3
"""Send a text message over the WhatsApp bridge.

Usage:
  send_text.py --phone <digits> --text "hello"
  send_text.py --chat "<digits>@s.whatsapp.net" --text "hi"
  send_text.py --phone <digits> --text "replying" --reply-to 3EB0ABC...
  send_text.py --phone <digits> --text "a" --mentions <digits> 123456
  send_text.py --text "hi"        # recipient defaults to $WHATSAPP_HOME_CHANNEL

Grounded in bridge.js POST /send: {chatId, message, replyTo?, mentions?}.
The phone number is normalized to <digits>@s.whatsapp.net (the bridge
resolves JIDs for you). Prints JSON on success:
  {"success":true,"messageId":"...","messageIds":[...]}
Exit code is 0 on a successful send, 1 on any bridge/transport error.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _bridge_lib import BridgeError, normalize_chat_id, require_success  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Send a text message via the WhatsApp bridge.")
    ap.add_argument("--phone", help="Recipient phone number (digits).")
    ap.add_argument("--chat", help="Full recipient JID (digits@s.whatsapp.net / @g.us / @lid).")
    ap.add_argument("--text", required=True, help="Text to send.")
    ap.add_argument("--reply-to", help="messageId of the message to reply to (replyTo).")
    ap.add_argument("--mentions", nargs="*", default=[],
                   help="One or more phone numbers (digits) to mention.")
    ap.add_argument("--port", type=int, default=0, help="Override bridge port (default: auto).")
    args = ap.parse_args()

    home = os.environ.get("WHATSAPP_HOME_CHANNEL", "")
    if not args.phone and not args.chat and not home:
        print(
            "error: provide --phone or --chat, or set WHATSAPP_HOME_CHANNEL",
            file=sys.stderr,
        )
        return 1

    from _bridge_lib import _get, _post, _check_port, probe_bridge_port, ensure_connected
    port = _check_port(args.port) if args.port else probe_bridge_port()
    ensure_connected(port)

    chat_id = normalize_chat_id(args.chat or args.phone or home)
    resp = _post(port, "/send", {
        "chatId": chat_id,
        "message": args.text,
        "replyTo": args.reply_to,
        "mentions": args.mentions or None,
    })
    require_success(resp, "send")
    print(json.dumps(resp))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
