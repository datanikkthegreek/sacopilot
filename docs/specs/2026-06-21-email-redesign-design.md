# SA Copilot — Email Redesign (design)

Date: 2026-06-21
Status: approved-pending-review
Builds on `2026-06-20-classification-flow-v2-design.md`.

## Motivation

After using the conversation-triage view, the email experience needs work:

1. Show date + time per email; sort the list by date.
2. A view of all unread emails.
3. Move the look toward `app1-gmail-agent` (shadcn/ui + Tailwind).
4. List loading is very slow — cache processed mail in Lakebase.
5. Opening one email is very slow — make it fast.
6. Emails render as plain text — show HTML, images, links.
7. A `Status` field (default Open; In Progress; Completed) with a keyboard
   shortcut. Completed archives the mail in Gmail.
8. Generate replies on emails; needs full-thread context; pull context from
   Glean (via MCP, OAuth — API tokens aren't permitted).

## Root cause

The Gmail MCP list responses contain only id/threadId/subject/from/snippet —
**no date, no unread, no body**. So every list and open hits the MCP live, and
date/unread aren't even available without per-thread fetches. The fix is a
**Lakebase-backed email cache**; almost every requirement depends on it.

## Decomposition (sequenced; each its own spec → build)

1. **Email store & sync (foundation)** — cache the inbox in Lakebase; serve
   list/open from cache. Fixes 4 & 5; unblocks the rest. *(Detailed below.)*
2. **List & reading UX** — date+time and date-sort (1), unread filter (2), HTML
   rendering with images/links (6).
3. **Status workflow** — Status Open/In Progress/Completed (7), keyboard
   shortcut, archive-on-Completed (Gmail write: remove the `INBOX` label).
4. **Reply generation + Glean** — full-thread context + Glean MCP (OAuth, via
   the dbexec bridge) + voice profile → Gmail draft (8).
5. **Design refresh** — migrate the frontend to Tailwind + shadcn/ui (3).

Decisions: build in order; first sync covers the full inbox (one-time, with a
progress bar); classification stays a separate action from sync; Glean goes
through an OAuth MCP (no API token); design refresh is a full Tailwind/shadcn
adoption.

---

## Sub-project #1 — Email store & sync (full detail)

### Data model (Lakebase)

Replace the empty `thread_classifications` with a single **`threads`** cache
table (its superset) holding ALL inbox threads, classified or not:

- Gmail metadata: `thread_id` PK, `subject`, `sender`, `snippet`,
  `message_count`, `last_internal_date` BIGINT (epoch ms; sort key),
  `unread` BOOL, `in_inbox` BOOL DEFAULT TRUE, `synced_at` TIMESTAMPTZ.
- Workflow: `status` TEXT NOT NULL DEFAULT 'Open' (column now; UI in #3).
- Classification (nullable until classified): `type, org, prio, dbx, bosch,
  bu[], labels[], confidence, rationale, needs_review, auto_facets,
  auto_labels, adjusted, adjusted_at, classified_at`.

New **`messages`** table (bodies; lazily filled): `message_id` PK, `thread_id`,
`ordinal` INT, `from_addr`, `to_addr`, `date_str`, `internal_date` BIGINT,
`subject`, `snippet`, `body_html`, `body_text`, `synced_at`.

### Sync — `POST /api/mail/sync` (SSE progress)

1. Page `gmail_thread_list("in:inbox")` by date window (cursor =
   `thread_latest_epoch` of the page's oldest thread) → the current inbox
   thread-id set `A`.
2. Cached threads with `in_inbox=true` not in `A` → set `in_inbox=false`
   (archived/removed elsewhere).
3. New ids (`A` minus cached) → `gmail_get_thread(metadata)` each → upsert the
   `threads` row (subject/sender/snippet/message_count/last_internal_date/
   unread) and the per-message metadata rows in `messages` (no bodies yet).
   Stream `{done,total,thread_id}` per thread.
4. Unread refresh (cheap, no per-thread calls): `gmail_thread_list(
   "in:inbox is:unread")` → set `unread=true` for those ids, `false` for the
   rest in the inbox.

First sync processes the whole inbox (~190 `thread_get` calls, one-time, with a
progress bar). Subsequent syncs only `thread_get` genuinely new threads.

### Serve from cache

- `GET /api/mail/threads?limit&offset&unread&status&label` — pure SQL over
  `threads`: `WHERE in_inbox [filters] ORDER BY last_internal_date DESC`. Real
  pagination. No MCP calls. Returns date (from `last_internal_date`), unread,
  status, labels, facets per row.
- `GET /api/mail/thread/{id}` — read `messages` from cache. **Cache-through**:
  any message missing `body_html` is fetched once via `gmail_message_get(full)`
  (inline), decoded to HTML + text, stored, then returned. Repeat opens are
  pure DB reads.

### Google tool additions

- `gmail_get_message` already returns a decoded body; extend it to return BOTH
  `body_html` (raw, for rendering) and `body_text` (stripped, for context).
- Reuse `gmail_thread_list` / `gmail_get_thread` / `thread_latest_epoch`.

### Backend modules

- `server/lakebase.py` — new `threads`/`messages` DAO: `upsert_thread`,
  `upsert_messages`, `mark_not_in_inbox`, `set_unread`, `list_threads`
  (filters+paging), `get_thread_messages`, `store_bodies`, plus the existing
  classification fns retargeted to `threads`.
- `server/sync.py` (new) — the sync orchestration (diff + fetch + stream).
- `server/routes/mail.py` — `POST /mail/sync` (SSE), retarget
  `GET /mail/threads` and `GET /mail/thread/{id}` to the cache.

### Error handling

- Lakebase unavailable → 503 with a clear message (never a silent empty list).
- MCP error on a thread mid-sync → stream a per-thread error, continue.
- Body fetch failure on open → fall back to that message's snippet.

### Testing

- Unit (monkeypatched): sync diff (new vs archived detection), unread bulk
  flag, cache-through body fill, list filter/sort SQL shape.
- Live: run sync; confirm `threads` rows carry dates/unread; `GET /mail/threads`
  returns date-sorted from cache with no MCP calls; open caches bodies and the
  second open is a pure DB read.

### Out of scope for #1 (later sub-projects)

- Rendering HTML in the UI (#2), unread/status UI (#2/#3), reply-gen (#4),
  Tailwind/shadcn refresh (#5). #1 is data + endpoints only; the current UI
  keeps working against the retargeted endpoints.
