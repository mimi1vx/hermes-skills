# WhatsApp Bridge — Protocol Reference

Grounded in the live bridge implementation (`bridge.js` and
`bridge_helpers.js`). Prefer these real schemas over inventing request bodies.

## Transport contract (applies to every endpoint)

- **Base:** `http://127.0.0.1:<port>` (default `port` = 3000; find it with
  `ps aux | grep bridge.js`).
- **`Host` header is mandatory** on every request — set `Host: 127.0.0.1`.
  Missing it → HTTP 400 `Invalid Host header` (in older builds); the bridge
  gates on it deliberately, so do not skip it.
- **Synchronous sends.** `/send`, `/edit`, `/send-media`, etc. block until
  Baileys resolves. A non-200 or `error` field means the operation did **not**
  happen; `success:true` means the bridge accepted it (final delivery is not
  guaranteed — it's the best the bridge exposes).
- A bridge in `disconnected` state rejects every write with
  `503 "Not connected to WhatsApp"` — fix/restart first, don't retry.

## `/health` (GET)

Returns `{status, queueLength, uptime, scriptHash, sendReadReceipts,
capabilities}`. `status` is `"connected"` or `"disconnected"`. Probe before
every write.

## `/send` (POST)

Body: `{ chatId, message, replyTo?, mentions? }`.
- `chatId` — full JID (see below). The bridge resolves it; passing a bare
  number is fine, it's normalized to `<digits>@s.whatsapp.net`.
- `replyTo` — messageId of the message to reply to (Baileys `quotedMessageKey`).
- `mentions` — list of phone numbers (digits) to mention.
Response: `{ success:true, messageId, messageIds:[...] }`. Long text is chunked
internally (`CHUNK_DELAY_MS` between chunks); all chunk messageIds are returned.

## `/edit` (POST)

Body: `{ chatId, messageId, message }`. Edits an *outbound* message
(`fromMe:true` key required by the handler). Response:
`{ success:true, messageIds:[...] }`.

## `/send-media` (POST)

Body: `{ chatId, filePath, mediaType?, caption?, fileName?, mentions? }`.
- Requires the file to exist (`404 "File not found: <path>"` otherwise).
- `mediaType` is auto-inferred from the extension if omitted (see
  `inferMediaType`).
- GIFs are converted to an animated MP4 (`gifPlayback`) via ffmpeg when
  available, else sent as a plain image/gif. Audio (mp3/wav/m4a) is converted
  to ogg/opus via ffmpeg so a native voice bubble (`ptt`) always renders; if
  ffmpeg is missing it's sent as a plain file attachment.
Response: `{ success:true, messageId }`.

## `/send-poll` (POST)

Body: `{ chatId, question, options:[...], selectableCount? }`
(`selectableCount` defaults to 1; min 2 options enforced).
Response: `{ success:true, messageId }`.

## `/send-location` (POST)

Body: `{ chatId, latitude, longitude, name?, address? }`.
Response: `{ success:true, messageId }`.

## `/typing` (POST)

Body: `{ chatId }`. Response: `{ success:true }` / `{ success:false }`.

## `/read` (POST)

Body: `{ key: { remoteJid, id, participant, fromMe } }` — the `readReceiptKey`
from an inbound event. Marks the message read. Response:
`{ success:true, marked:false|true }` (marked stays `false` when read receipts
are disabled and/or the key is for an outbound message).

## `/chat/:id` (GET)

`GET /chat/{jid}` → chat info. For groups: `{ name: subject, isGroup:true,
participants:[...] }`; otherwise `{ name, isGroup, participants:[] }`.

## `/messages` (GET) — reading inbound

Long-polls and then **drains** the in-memory queue, so each run reports only
events no earlier run saw (nothing is reported twice). Returns a JSON array of
event objects (one per `extractBridgeEvent`).

### Inbound event fields

```
{
  messageId,              // msg.key.id
  chatId,                 // normalized remoteJid
  senderId,               // normalized sender JID
  senderName,             // pushName or sender number
  chatName,               // group subject, or sender push number
  isGroup,                // bool
  body,                   // text payload (falls back to [type received])
  hasMedia,               // bool
  mediaType,              // image | video | audio | document | sticker | ...
  mime, fileName,         // attachment details (if any)
  nativeType,             // Baileys-specific type
  nativeMetadata,         // decoded native payload (e.g. poll aggregation)
  mediaUrls,              // [] or list of cached local URLs
  mentionedIds,           // [] or list of mentioned JIDs
  quotedMessageId,        // null | message id being quoted
  quotedParticipant,
  quotedRemoteJid,
  quotedText,
  quotedMediaUrls,
  quotedMediaType,
  hasQuotedMessage,       // bool
  botIds,                 // [] or list of bot JIDs in the chat
  readReceiptKey,         // { remoteJid, id, participant, fromMe } -> POST /read
  timestamp,              // msg.messageTimestamp
}
```

Notes from `extractBridgeEvent`:
- Nested quoted messages are peeled (`ephemeralMessage`, `viewOnceMessage`,
  `viewOnceMessageV2`, `documentWithCaptionMessage`) before classification.
- A message whose media download failed surfaces as body
  `"[<type> could not be downloaded]"` rather than a false `[<type> received]`.
- Polls created by this bridge are surfaced with `nativeMetadata.poll`
  (`question`, `options`, `selectableCount`); votes are only decoded/forwarded
  for bridge-created polls (foreign polls are ignored).

### Inbound queue & self-chat mode

`GET /messages` only returns messages **from other senders** — it does not
echo this bridge's own outbound `/send` / `/send-media` results back into the
queue (verified: after `/send` returns `messageId`, a later `/messages` poll
returns `[]`). This is expected in `self-chat` mode: the bridge forwards
inbound messages addressed to your number; it doesn't re-feed its own sends.

To verify a send landed, read the `messageId` the bridge returned (e.g.
`3EB041A9DB7E028E371F40`) — that is the proof. The inbound queue is your tool
for reading what *other* people send you, not for confirming your own sends.

`sendText()` returns `messageIds` (plural) because long messages are split into
multiple chunks sent sequentially; the last id is the last part. Use it, or
`messageId` (the final chunk).

### `inferMediaType` (extension → type)

```
jpg|jpeg|png|webp|gif  -> image
mp4|mov|avi|mkv|3gp    -> video
ogg|opus|mp3|wav|m4a   -> audio
anything else          -> document
```

## JID resolution

The bridge resolves JIDs for callers, but callers may pass:
- a **raw number** → normalized to `<digits>@s.whatsapp.net` (self/chat),
- a **full chat** JID → `<digits>@s.whatsapp.net`,
- a **group** → `<digits>@g.us`,
- a **linked-device** account → `...@lid`.

`/chat/:id` can be used to confirm the correct form before sending.
