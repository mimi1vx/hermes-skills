#!/usr/bin/env python3
"""Shared helpers for the WhatsApp bridge helper scripts.

Grounded in the bridge implementation (bridge.js, loopback port 3000 by
default). Uses only the Python standard library (urllib) so it runs on any
Hermes install without third-party deps.

Bridge contract (from bridge.js routes):
  GET  /health       -> {"status":"connected"|"disconnected", "queueLength", ...}
  GET  /messages     -> [ ...inbound event objects... ]  (drains the queue!)
  POST /send         -> {"success":true, "messageId","messageIds":[...]}
  POST /edit         -> {"success":true, "messageIds":[...]}
  POST /send-media   -> {"success":true, "messageId"}
  POST /send-poll    -> {"success":true, "messageId"}
  POST /send-location-> {"success":true, "messageId"}

Every request requires an HTTP Host header of 127.0.0.1 (or loopback).
Sends are synchronous: /send returns only after Baileys resolves the send,
so a 200 with success:true == accepted by the bridge (not proof of final
delivery, but that's the best the bridge exposes).

The bridge resolves chat JIDs itself, so callers may pass a raw number, a
self-chat JID (digits@s.whatsapp.net), a group JID (digits@g.us), or a
@lid JID. Numbers are normalized client-side to <digits>@s.whatsapp.net.
"""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional

BRIDGE_ERROR = None  # set by probe_bridge_port()

PROBABLE_PORTS = (3000, 3001, 3002, 3100, 5000, 8000, 8080)


class BridgeError(RuntimeError):
    """Raised for transport / bridge failures. message carries detail."""


def _default_port() -> int:
    """Return the port the bridge is listening on.

    1) Honour BRIDGE_PORT env if set.
    2) Otherwise probe a few common loopback ports; the first that answers
       /health is used. Falls back to 3000.
    """
    env = os.environ.get("BRIDGE_PORT")
    if env:
        try:
            return int(env)
        except ValueError:
            pass
    for port in PROBABLE_PORTS:
        if _probe_health(port) is not None:
            return port
    return 3000


def _probe_health(port: int, timeout: float = 0.6) -> Optional[dict]:
    url = f"http://127.0.0.1:{port}/health"
    req = urllib.request.Request(url, headers={"Host": "127.0.0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except Exception:
        return None


def probe_bridge_port() -> int:
    """Discover and cache the bridge port once per process."""
    global BRIDGE_ERROR
    if BRIDGE_ERROR is not None:
        return int(BRIDGE_ERROR)  # sentinel: already failed
    port = _default_port()
    health = _probe_health(port)
    if health is None:
        BRIDGE_ERROR = -1
        raise BridgeError(
            f"No WhatsApp bridge answering /health on any expected loopback "
            f"port (tried {', '.join(str(p) for p in PROBABLE_PORTS)}). Is "
            f"bridge.js running?"
        )
    return port


def ensure_connected(port: Optional[int] = None) -> dict:
    """Fail fast with a helpful message if the bridge is down/logged out."""
    port = probe_bridge_port() if port is None else port
    health = _probe_health(port)
    if health is None:
        raise BridgeError("bridge not reachable on port %d" % port)
    if health.get("status") != "connected":
        raise BridgeError(f"bridge status is {health.get('status')!r}, not 'connected'")
    return health


def _check_port(port: Optional[int]) -> int:
    if not port:
        port = probe_bridge_port()
    return port


def _post(port: int, path: str, payload: dict) -> dict:
    """POST JSON to the bridge with the mandatory Host header.

    Returns the parsed JSON body. Raises BridgeError on HTTP errors or a
    non-200 status, and if `success` is False.
    """
    url = f"http://127.0.0.1:{port}{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Host": "127.0.0.1", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise BridgeError(f"bridge returned HTTP {e.code}: {detail}")
    except urllib.error.URLError as e:
        raise BridgeError(f"bridge request failed: {e.reason}")
    if not body:
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {}


def _get(port: int, path: str) -> dict:
    url = f"http://127.0.0.1:{port}{path}"
    req = urllib.request.Request(url, headers={"Host": "127.0.0.1"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        raise BridgeError(f"bridge returned HTTP {e.code}: {e.read().decode('utf-8','replace')}")


def normalize_chat_id(chat: str) -> str:
    """Turn a raw number, partial or full JID into a sendable chatId.

    Accepts: '1234567890', '1234567890@s.whatsapp.net',
             '1234567890@g.us', or a @lid id. Returns it unchanged if it
             already contains a domain suffix.
    """
    chat = (chat or "").strip()
    if not chat:
        raise BridgeError("empty chatId")
    # Already has a WhatsApp domain suffix.
    if re.search(r"@(\.whatsapp\.net)|@g\.us|@lid$", chat):
        return chat
    digits = re.sub(r"\D", "", chat)
    if not digits:
        raise BridgeError(f"cannot normalize chatId {chat!r}: no digits")
    return f"{digits}@s.whatsapp.net"


def require_success(resp: dict, op: str = "send") -> None:
    if not resp.get("success"):
        raise BridgeError(f"bridge {op} failed: {json.dumps(resp)}")


def first_message_id(resp: dict, op: str = "send") -> Optional[str]:
    """Best-effort extraction of a messageId from a bridge response."""
    if isinstance(resp, dict) and not resp.get("success"):
        return None
    ids = resp.get("messageIds") if isinstance(resp, dict) else None
    if isinstance(ids, list) and ids:
        return ids[-1]
    return resp.get("messageId") if isinstance(resp, dict) else None


# Convenience: a tiny dataclass callers can pattern-match on.
@dataclass
class BridgeResult:
    op: str
    ok: bool
    resp: dict
    message_id: Optional[str] = None

    @property
    def message_ids(self):
        ids = self.resp.get("messageIds") if isinstance(self.resp, dict) else None
        return list(ids) if isinstance(ids, list) else None


if __name__ == "__main__":  # quick self-test
    import sys
    try:
        p = probe_bridge_port()
        h = ensure_connected(p)
        print(json.dumps({"port": p, "health": h}))
    except BridgeError as e:
        print("BRIDGE_ERROR:", e)
        sys.exit(1)
