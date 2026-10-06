#!/usr/bin/env python3
"""Read (and drain) new inbound messages from the WhatsApp bridge.

Usage:
  read_messages.py            # print new inbound events as JSON
  read_messages.py --as-json  # same (default); machine-friendly

Grounded in bridge.js GET /messages, which LONG-POLLS the in-memory queue
and DRAINS it — so each call returns events not yet seen by any run, and
empty ones are never reported twice.

Each event (from extractBridgeEvent) has fields including:
  messageId, chatId, senderId, senderName, chatName, isGroup,
  body, hasMedia, mediaType, mime, fileName, nativeType, nativeMetadata,
  mediaUrls, mentionedIds, quotedMessageId, quotedText, hasQuotedMessage,
  readReceiptKey { remoteJid, id, participant, fromMe }, timestamp

Prints a JSON array to stdout. Exit code 0.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _bridge_lib import probe_bridge_port, ensure_connected, _get  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Read new inbound WhatsApp messages from the bridge.")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print the JSON.")
    ap.add_argument("--as-json", action="store_true", help="(default) output a JSON array.")
    ap.add_argument("--port", type=int, default=0, help="Override bridge port (default: auto).")
    args = ap.parse_args()

    port = probe_bridge_port() if args.port else probe_bridge_port()
    ensure_connected(port)

    events = _get(port, "/messages")
    # The route returns a plain list. Wrap defensively if a future version
    # nests it.
    if isinstance(events, dict):
        events = events.get("messages", [])
    out = json.dumps(events, indent=2 if args.pretty else None, ensure_ascii=False)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
