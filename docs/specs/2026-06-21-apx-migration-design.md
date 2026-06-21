# SA Copilot — Migration to an APX app (design)

Date: 2026-06-21
Status: approved-pending-review
Builds on the email redesign specs (2026-06-20, 2026-06-21).

## Motivation

Move SA Copilot onto **APX** (`github.com/databricks-solutions/apx`), the
toolkit `app1-gmail-agent` is built on. This delivers, in one move:

- The APX / shadcn look and **dark mode** (apx theme-provider) — requested.
- A **status filter**, **newest message on top** in the reading pane, and
  **hh:mm** timestamps in the list — requested.
- A **Send** action (send the drafted reply), gated by a confirm — requested.
- `databricks bundle deploy` to ship as a **Databricks App** (not possible with
  the current Vite/FastAPI setup).

## Approach

Scaffold a fresh APX app (`apx init`) and port SA Copilot into it, rather than
retrofitting apx into the current Vite repo — apx owns the root layout, build,
and TanStack route codegen, so porting is cleaner than fighting the scaffold.
The current app keeps running as the reference until the APX app reaches parity,
then becomes the app. `docs/specs` and git history are preserved.

## Backend port (low risk — framework-agnostic Python moves in as-is)

- Move `server/` modules unchanged: `lakebase.py`, `sync.py`, `classifier.py`,
  `reply.py`, `taxonomy.py`, `config.py`, `mcp_google.py`, `mcp_glean.py`,
  `tools/` (`google.py`, `classify.py`, `gmail_write.py`, `vault.py`).
- Re-register routes via apx's `create_router()` + `create_app(routers=[…])`:
  the `mail`, `agent`, `meetings` routers.
- Wrap the persistent MCP bridges (Google, Glean) as a `LifespanDependency` so
  they start/stop with the app.
- Env carries over via `app.yml` + `.env`: `ANTHROPIC_AUTH_TOKEN`,
  `ANTHROPIC_BASE_URL`, `SACOPILOT_LAKEBASE_*`, vault/voice paths.
- Keep the pytest suite (modules unchanged).

## Frontend rebuild (the bulk — port onto apx's stack)

Port `App.tsx` behavior onto Vite + React + TanStack Router/Query + shadcn/ui:

- A TanStack route for the cockpit; shadcn primitives (button, card, select,
  badge, dialog, textarea) replace hand-rolled components.
- API + SSE calls into `lib/api.ts` (sync/classify SSE, threads, thread,
  status, reply, send, taxonomy).
- **Dark mode** from the apx theme-provider + a mode-toggle in the navbar.
- Preserve all behavior: Sync, Classify, facet editor, category filters,
  keyboard triage (j/k, s, c, 1/2/3, d, ?), HTML reading pane, status, reply.

### Feature deltas folded in

- **Status filter**: a Status group in the filter bar (Open / In Progress /
  Completed). Backend `list_threads` already accepts `status`.
- **Hide Open label**: Open renders no chip; it's the implicit default. Only
  In Progress / Completed show a status chip.
- **Newest on top (reading pane)**: render thread messages latest-first.
- **hh:mm in list**: rows show `DD.MM · HH:MM` (date + time), always including
  the time.
- **Send button**: see below.

## Send action (changes the drafts-only rule — deliberately)

Until now SA Copilot never sends mail (drafts only). Adding a **Send** button:

- New backend endpoint `POST /api/mail/send/{thread_id}` with the (possibly
  edited) reply text, recipient, subject, and the latest message id for
  threading. Implemented via the MCP `gmail_message_send` tool, sent in-thread
  (reply headers) — never to a new thread.
- The UI shows **Send** next to the draft; clicking it opens a **confirm
  dialog** ("Send this reply to <recipient>?") because sending is irreversible
  and outward-facing. Only on confirm does the send fire.
- The Gmail **draft** created by reply-gen is deleted after a successful send so
  it doesn't linger.
- `gmail_create_draft` (draft, never sends) remains the default path; Send is an
  explicit, confirmed extra step.

## Deploy

`apx build` produces the bundle; the apx-generated `databricks.yml` + `app.yml`
enable `databricks bundle deploy` to a Databricks App. (Stretch — wiring the
deploy target is part of this sub-project only if time allows; local `apx dev`
parity is the must-have.)

## Testing & parity

- Backend pytest suite ports over (unchanged modules).
- Parity checklist verified under `apx dev`: sync → classify → filter (category
  + status + unread) → open (HTML, latest-first, hh:mm) → status/archive →
  reply → **send (with confirm)**. Plus a dark-mode toggle smoke check and an
  `apx build`.

## Risks

- Frontend rebuild on shadcn/TanStack is where regressions hide — port
  feature-by-feature and verify each against the current app.
- `apx init` may scaffold addons/structure that need trimming; keep
  backend-only addons and add the single cockpit route.
- Send is the one irreversible action — the confirm dialog and in-thread-only
  send are the guardrails.

## Out of scope

- Multi-account, label management in Gmail, eager body sync (still lazy),
  meeting-flow changes beyond porting the existing tab.
