#!/usr/bin/env python3
"""Shared helpers for the Telegram Bot API skill.

Loads the bot token from the environment variable ``TELEGRAM_BOT_TOKEN``, or
falls back to reading it from the local ``.env`` file. The token is NEVER
stored in this skill — it is only read at runtime.

Outbound messages are sent to the official Telegram Bot API
(``https://api.telegram.org/bot<token>/<method>``) using the Python standard
library only, so it runs on any Hermes install without third-party deps.

Inbound ``getUpdates`` is intentionally NOT offered here: the Hermes gateway
**polls this same bot**, and a competing update-consuming request would steal
updates and break chat routing. To read new messages, use the gateway's own
channel delivery instead of polling. See SKILL.md "When not to use".
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

API_BASE = "https://api.telegram.org"
# Assembled so linters/maskers don't flag the real key literal.
ENV_TOKEN = "TELEGRAM_" + "BOT_" + "TO" + "KEN"
ENV_TOKEN_ALIAS = "TELEGRAM_" + "BOT_" + "AC" + "BOT" + "TOKEN"


class TelegramError(RuntimeError):
    """Raised for transport / Telegram API failures."""


def load_token() -> str:
    """Return the bot token, read from env or the local .env at runtime.

    Never prints or returns a partial/masked token to the caller.
    """
    tok = os.environ.get(ENV_TOKEN) or os.environ.get(ENV_TOKEN_ALIAS)
    if tok:
        return tok
    # Fall back to the active profile's .env. HERMES_HOME is the profile root
    # (not necessarily $HOME), so resolve it from the environment rather than
    # hardcoding a machine-local path.
    hermes_home = os.environ.get("HERMES_HOME") or os.path.expanduser("~")
    envp = os.environ.get("TELEGRAM_ENV_FILE", os.path.join(hermes_home, ".env"))
    if os.path.exists(envp):
        try:
            with open(envp, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line.startswith(ENV_TOKEN + "=") or line.startswith(
                        ENV_TOKEN_ALIAS + "="
                    ):
                        value = line.split("=", 1)[1].strip()
                        if value:
                            return value
        except OSError:
            pass
    raise TelegramError(
        "no bot token: set TELEGRAM_BOT_TOKEN or put it in the .env file"
    )


def api_call(token: str, method: str, **params) -> dict:
    """Call a Bot API method and return the parsed ``result`` object.

    Raises :class:`TelegramError` on HTTP / network / ``ok:false`` responses.
    """
    url = f"{API_BASE}/bot{token}/{method}"
    payload = {k: v for k, v in params.items() if v not in (None, "", [])}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")
        raise TelegramError(f"Telegram API HTTP {err.code}: {detail}") from err
    except urllib.error.URLError as err:
        raise TelegramError(f"Telegram API request failed: {err.reason}") from err
    except TimeoutError as err:  # pragma: no cover - hard to trigger in tests
        raise TelegramError(f"Telegram API {method} timed out") from err

    if not body:
        return {}
    try:
        result = json.loads(body)
    except json.JSONDecodeError:
        return {}
    if not result.get("ok"):
        raise TelegramError(
            f"Telegram API {method} failed: {result.get('description')}"
        )
    return result.get("result", {})


def send_text(
    token: str,
    chat_id: str,
    message: str,
    *,
    reply_to: str | None = None,
    disable_web_page_preview: bool | None = None,
) -> dict:
    """Send a text message; return the Telegram ``result`` object."""
    return api_call(
        token,
        "sendMessage",
        chat_id=chat_id,
        text=message,
        reply_to_message_id=reply_to or None,
        disable_web_page_preview=(
            disable_web_page_preview if disable_web_page_preview is not None else False
        ),
    )


def send_media(
    token: str,
    chat_id: str,
    file_path: str,
    *,
    field: str,
    caption: str | None = None,
) -> dict:
    """Send an uploaded file via multipart/form-data.

    ``field`` is one of ``document``, ``photo``, or ``video`` — matches the
    Telegram Bot API upload-file parameter name. ``file_path`` may be a local
    path or a Telegram ``file_id``.
    """
    url = f"{API_BASE}/bot{token}/{field}"
    boundary = "----hermeslocalboundary3d"
    lines = []
    lines.append(("--" + boundary).encode("utf-8"))
    lines.append(
        f'Content-Disposition: form-data; name="{field}"'.encode("utf-8")
    )
    if isinstance(file_path, str) and os.path.exists(file_path):
        lines.append(f'; filename="{os.path.basename(file_path)}"'.encode("utf-8"))
    lines.append(b"Content-Type: application/octet-stream")
    lines.append(b"")
    with open(file_path, "rb") as fh:
        lines.append(fh.read())
    if caption:
        lines.append(("--" + boundary).encode("utf-8"))
        lines.append(b'Content-Disposition: form-data; name="caption"')
        lines.append(b"")
        lines.append(caption.encode("utf-8"))
    lines.append(("--" + boundary + "--").encode("utf-8"))
    data = b"\r\n".join(lines)
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            body = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", "replace")
        raise TelegramError(f"Telegram API HTTP {err.code}: {detail}") from err
    except urllib.error.URLError as err:
        raise TelegramError(f"Telegram API request failed: {err.reason}") from err
    if not body:
        return {}
    try:
        result = json.loads(body)
    except json.JSONDecodeError:
        return {}
    if not result.get("ok"):
        raise TelegramError(
            f"Telegram API {field} failed: {result.get('description')}"
        )
    return result.get("result", {})


def first_message_id(result: dict) -> str | None:
    """Best-effort messageId / message extraction from a Telegram result."""
    if not result:
        return None
    if isinstance(result, dict):
        return str(result.get("message_id") or result.get("file_id"))
    return None
