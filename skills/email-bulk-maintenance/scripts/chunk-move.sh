#!/bin/bash
# Chunked IMAP move for one email-bulk-maintenance batch.
# Moves every message from each exact sender address out of the source mailbox
# into the trash mailbox, in UID chunks (default 100), then verifies each
# sender re-searches to Found 0. Fresh UID fetch per sender; nothing is
# deleted, only moved to trash (recoverable).
#
# Usage: chunk-move.sh [-m SRC] [-t DST] [-n CHUNK] sender@exact.address ...
#   HIMALAYA env overrides the binary path. Resolution order:
#     $HIMALAYA -> $HOME/.local/bin/himalaya (or the profile-local
#     $HERMES_HOME/.local/bin/himalaya) -> whatever is on $PATH.
set -u
if [ -z "${HIMALAYA:-}" ]; then
  if [ -x "${HERMES_HOME:-$HOME}/.local/bin/himalaya" ]; then
    H="${HERMES_HOME:-$HOME}/.local/bin/himalaya"
  else
    H="${HOME}/.local/bin/himalaya"
  fi
else
  H="$HIMALAYA"
fi
command -v "$H" >/dev/null 2>&1 || H="$(command -v himalaya || echo himalaya)"
SRC="Inbox"
DST="[Gmail]/Bin"
CHUNK=100
while getopts "m:t:n:" o; do
  case "$o" in
    m) SRC="$OPTARG" ;; t) DST="$OPTARG" ;; n) CHUNK="$OPTARG" ;;
  esac
done
shift $((OPTIND - 1))
[ "$#" -ge 1 ] || { echo "usage: $0 [-m SRC] [-t DST] [-n CHUNK] sender..." >&2; exit 1; }
FAIL=0
for sender in "$@"; do
  echo "=== $sender ==="
  UIDS=$("$H" imap search -m "$SRC" --from "$sender" 2>/dev/null | grep -E '^\u2502 [0-9]+' | grep -oE '[0-9]+' | sort -n -u)
  TOTAL=$(printf '%s' "$UIDS" | grep -c . || true)
  echo "found: $TOTAL"
  [ "$TOTAL" -eq 0 ] && continue
  printf '%s\n' "$UIDS" | xargs -n "$CHUNK" | tr ' ' ',' | while read -r seq; do
    [ -z "$seq" ] && continue
    "$H" imap move -m "$SRC" "$seq" "$DST" || echo "CHUNK FAILED: $seq"
  done
  REMAIN=$("$H" imap search -m "$SRC" --from "$sender" 2>/dev/null | tail -n 1)
  echo "verify: $REMAIN"
  case "$REMAIN" in *"Found 0 message(s)"*) ;; *) FAIL=1 ;; esac
done
echo "=== trash ==="
"$H" mailbox list --counts 2>/dev/null | grep -E "Bin|Trash" || true
exit "$FAIL"
