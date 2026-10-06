# Himalaya v2 Configuration Reference

Config file path (first valid of these):
`$XDG_CONFIG_HOME/himalaya/config.toml` → `$HOME/.config/himalaya/config.toml` → `$HOME/.himalayarc`
Override with `himalaya -c <PATH>`; multiple `:`-separated paths deep-merge (first = base).

## The one rule: no `backend.type`

In v2 each backend is a **top-level section**, not a per-account table. An
account section (`[accounts.NAME]`) that contains any backend key selects that
backend (IMAP/JMAP/Graph/maildir). There is no `backend.type = "imap"` — using
it (a v1 habit) means no backend is ever matched.

## Account section

```toml
[accounts.gmail]
default = true
email = "you@gmail.com"
# signature, display-name, signature-delim — REMOVED (composition moved to pimalaya/mml)
#message.send.save-copy = "sent"   # role/alias/name, or false
#mailbox.alias.<role>            # per-account override of a global [mailbox.alias.*]
#downloads-dir = "~/downloads"     # per-account override (attachment download target)
#proxy.url / proxy.username / proxy.password.command
```

## IMAP backend (reads + optionally sends)

```toml
# A bare authority (imaps://, implicit TLS) or a full URL.
imap.server = "imap.example.com"
# or: imap.server = "imaps://example.com:993"
# or: imap.server = "imap://example.com:143"   # then imap.starttls = true

imap.tls.provider = "rustls"     # or "native-tls"
imap.tls.rustls.crypto = "ring"  # or "aws"
#imap.tls.cert = "/path/to/cert.pem"   # custom root (PEM)
#imap.starttls = false
#imap.alpn = ["imap"]

# Pick exactly one SASL mechanism. Omit the whole `imap.sasl` table = auth skipped.
# ANONYMOUS
#imap.sasl.anonymous.message = "himalaya"
# PLAIN (Gmail App Password)
imap.sasl.plain.username = "you@gmail.com"
imap.sasl.plain.password.raw = "APP_PASSWORD"
# or sourced from a password manager:
#imap.sasl.plain.password.command = ["pass", "show", "google/app-password"]
# SASL LOGIN / OAUTHBEARER / XOAUTH2 / SCRAM-SHA-256 variants exist too
```

## JMAP backend (e.g. Fastmail)

```toml
# Bare authority discovers the session via GET /.well-known/jmap, or give it directly.
jmap.server = "https://api.fastmail.com/jmap/session"

# Exactly one of header / bearer / basic
#jmap.auth.header.raw = "Bearer eyJ..."
#jmap.auth.header.command = ["pass", "show", "fastmail"]
#jmap.auth.bearer.token.raw = "Bearer ..."
#jmap.auth.bearer.token.command = ["ortie", "token", "show", "-a", "fastmail"]
#jmap.auth.basic.username = "you@fastmail.com"
#jmap.auth.basic.password.raw = "***"

# Optional: pin the drafted identity + drafts mailbox (auto-discovered when unset).
#jmap.identity-id = "I0123abc"
#jmap.drafts-mailbox-id = "M0123abc"
```

## Gmail REST backend

Native Gmail REST backend; labels are mailboxes, system labels are flags. Auth is a
single short-lived OAuth 2.0 bearer token from a broker (e.g. pimalaya/ortie).

```toml
# gmail.user-id = "me"   # default
gmail.auth.token.raw = "***"
# or sourced:
# gmail.auth.token.command = ["ortie", "token", "show", "-a", "gmail"]
```

## Microsoft Graph backend

Same shape as Gmail — a single OAuth 2.0 bearer token; sending goes through Graph,
so no `smtp` block is needed.

```toml
#msgraph.user-id = "me"
msgraph.auth.token.raw = "***"
# msgraph.auth.token.command = ["ortie", "token", "show", "-a", "msgraph"]
```

## SMTP (only needed if an IMAP/JMAP account sends)

```toml
# A bare authority (smtps://) or a full URL (smtp:// with optional STARTTLS).
smtp.server = "smtp.example.com"
# or: smtp.server = "smtps://example.com:465"
# or: smtp.server = "smtp://example.com:587"   # then smtp.starttls = true
#smtp.tls.provider = "rustls"
#smtp.starttls = false
#smtp.sasl.plain.username / .password.raw / .password.command   # same SASL variants as IMAP
```

## Maildir backend (local, read-only)

```toml
maildir.root = "~/Mail/example"
```

## Mailbox aliases

Rename `folders` → `mailboxes`. Aliases are case-insensitive on lookup and storage;
an entry named after a role (`inbox`/`sent`/`trash`/`junk`/`archive`/`flagged`/
`important`) overrides the role the backend reports — the `inbox` role is the default
mailbox shared commands fall back to when `-m/--mailbox` is omitted.

```toml
mailbox.alias.inbox = "INBOX"
mailbox.alias.sent = "[Gmail]/Sent Mail"
mailbox.alias.drafts = "[Gmail]/Drafts"
mailbox.alias.trash = "[Gmail]/Trash"

# per-account override of a same-named global alias
#[accounts.work.mailbox.alias]
#inbox = "INBOX"
```

Without the correct `mailbox.alias.sent`, save-to-Sent fails *after* SMTP delivery —
but Gmail/Graph/Graph file sent themselves, so this only bites the IMAP/JMAP send paths.
