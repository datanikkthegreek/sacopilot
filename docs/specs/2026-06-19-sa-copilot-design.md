# SA Copilot — Design Spec

**Date:** 2026-06-19
**Status:** Approved design — ready for implementation planning
**Repo:** `~/Repos/sacopilot/`

## Context

Nikolaos is a Databricks Solutions Architect managing the Bosch account. He already has a rich local toolchain: an Obsidian vault (`~/Repos/obsidian/NikkTheGreek/`) with structured BU/contact/project/meeting notes, a sync pipeline (`~/Repos/obsidian/.sync/*.py`) that pulls meeting notes from Google Docs, a writing-voice profile (`~/.vibe/voice_profile.yaml`), and MCP connections to Google/Slack/Salesforce **inside Claude Code**.

The gap: those integrations only exist *inside Claude Code*. There is no standalone surface that (a) triages his email with consistent classification, or (b) turns meetings into drafts and filed notes on its own. He wants a personal **Copilot app** for the two jobs he'd start with:

- **C — Drafting & comms** in his voice (emails, recaps, prep).
- **D — Knowledge capture** (meeting → filed note, updated contacts/projects), reusing the proven `.sync` flow.

…with **email triage** as the primary day-one surface: incoming mail auto-classified and **labelled in Gmail**, filterable by a 6-facet taxonomy, with full email context in-app.

A key constraint drove the architecture: **live Google Calendar/Gmail access cannot come from the local `.sync` scripts** — those only transform already-exported local files and have zero network/Google reach (verified). Live reach must be wired into the app itself.

## Goals (v1)

1. **Email copilot** — incremental, button-driven classification of new mail; apply nested **Gmail labels** (written back live, visible in Gmail everywhere); in-app mail view with full context and 6-facet filtering.
2. **Meeting copilot** — calendar-driven cockpit: prep a meeting, capture its notes into the vault, draft follow-ups in voice.
3. **Voice-aware drafting** — every generated email/recap uses the voice profile.
4. **Review before write** — nothing mutates Gmail labels, the vault, or sends mail without explicit approval. Emails only ever become **Gmail drafts**, never auto-sent.

## Non-goals (v1)

- **No email → Obsidian sync.** The vault is **read-only context** for the mail view (so drafts can reference prior decisions); there is no write path from email into the vault. Email→vault capture is a deliberate **future discussion**, not v1.
- **No Slack / Salesforce** live integration (deferred; the design leaves a clean seam).
- **No remote hosting.** Local-only on the Mac.
- **No auto-send.** Outbound mail is always a draft.

## Architecture

Local web app in `~/Repos/sacopilot/`. One repo, two processes:

- **Backend — Python / FastAPI.** Hosts a Claude **agent loop** (`claude-opus-4-8`, adaptive thinking, streaming) built on the Anthropic SDK manual tool-use loop (manual, not the auto-runner, so effecting tools can pause for approval). Owns all tools; exposes an HTTP + SSE API.
- **Frontend — React.** Two cockpit views (Mail, Meetings) over HTTP + SSE.

```
┌─ React cockpit (localhost:5173) ──────────────┐
│  Mail view   │  Meetings view  │  chat / diff  │
└──────────────────────┬──────────────────────── ┘
              HTTP + SSE
┌──────────────────────▼─ FastAPI (localhost:8000) ─┐
│  Agent loop (claude-opus-4-8, streaming)           │
│   tools:                                           │
│    • gmail_* / calendar_* / docs_* ← Google (MCP)  │
│    • classify_email           ← structured output  │
│    • vault_*  (read) + propose_*/commit_writes     │
│       └ wrap ~/Repos/obsidian/.sync/*.py           │
│    • load_voice_profile       ← voice_profile.yaml │
│  approval gate: effecting tools pause for OK       │
│  local state: email-state.json (classify watermark)│
└────────────────────────────────────────────────────┘
        ▲                              ▲
   Google OAuth              ~/Repos/obsidian vault
                            (read-only from Mail; Meetings writes via approved commit_writes)
```

Only outbound calls: Anthropic API + Google APIs. Everything else stays local.

## The agent & tools

One tool-use loop. Tools are small, typed, independently testable Python functions, split into **read** (run freely) and **effecting** (pause for approval).

**Google — live, via MCP (Calendar / Docs / Drive / Gmail), one OAuth:**
- `gmail_list_messages` — new / since-watermark messages (read)
- `gmail_get_message` — full body + current labels (read)
- `gmail_ensure_labels` — create the nested label tree once (effecting, idempotent)
- `gmail_apply_labels` — **write labels back to Gmail** (effecting)
- `gmail_create_draft` — draft only, **never sends** (effecting)
- `calendar_list` — meetings for today / a range (read)
- `drive_find_meeting_doc` — locate the Gemini notes/transcript by name+time (read)
- `docs_export` — pull a doc/tab as markdown (read)

**Classification:**
- `classify_email` — returns the structured 6-facet set + confidence, constrained via `output_config.format` so output is always schema-valid. Confidence below threshold → auto-adds `Needs/Review`.

**Vault — local, read-only context (wraps `.sync/`):**
- `vault_search`, `vault_read`, `vault_recent_meetings` (read)
- `propose_meeting_note`, `propose_contact_update`, `propose_project_update` — return a **diff**, do not write (read-only proposal; reuse `sync_engine.py`, `gen_contacts.py`, etc.)
- `commit_writes` — the only vault-mutating tool; applies approved diffs (effecting). **Used by the Meetings view only — never invoked from the Mail view in v1.**

**Voice:**
- `load_voice_profile` — reads `~/.vibe/voice_profile.yaml` into drafting context.

**Approval gate.** Enforced in the loop, not via prompting: when the agent calls an effecting tool, the loop pauses and surfaces the proposal (a Gmail label set, a draft email, or a vault diff) to the frontend; execution waits for explicit OK.

## Email classification taxonomy

Labels are **nested Gmail labels** (`prefix/value`, render as a tree), mirroring the vault tag taxonomy so both systems share a language. **Gmail is the source of truth** — labels are written back live and visible in Gmail on every device; the app reflects them.

| # | Facet (Gmail prefix) | Values | Notes |
|---|---|---|---|
| 1 | `Type/` | Informative · Action · **Waiting** | Waiting = delegated / awaiting reply (blocked-on-others) |
| 2 | `Org/` | Customer · Partner · Internal | **Gate** — facets 4–6 apply conditionally on this |
| 3 | `Prio/` | 0 · 1 · 2 | P0 = today/urgent · P1 = this week · P2 = FYI/whenever |
| 4 | `DBX/` *(Internal)* | Marketing · Announcement · Alerts · Other · **People** | People = 1:1s, hiring, mentoring, team/org (mirrors `02_Internal`) |
| 5 | `Bosch/` *(Customer)* | Operation · Use-Case · **Commercial** · **Escalation** | Commercial = contracts/pricing/renewals; Escalation = incidents/blockers |
| 6 | `BU/` *(Customer)* | PT, HC, PS, MA, … (vault BU codes) · **Account** | **Multiple allowed**; Account = cross-BU/account-level, no single BU |
| — | `Needs/Review` | flag | Auto-added on low-confidence classification |

**Learning loop.** When you re-label in the Mail view, the correction is stored locally and appended as a few-shot example to the classifier's context, so later runs reflect your judgment. (Corrections also write back to Gmail via `gmail_apply_labels`.)

## Data flow & state

**Classify-new** (incremental, button-driven; same watermark philosophy as `/obsidian sync`):
1. Click **Classify new** → `gmail_list_messages` since the stored watermark.
2. Per message: `gmail_get_message` → `classify_email` → (approve) → `gmail_apply_labels`.
3. Record message id + assigned facets + watermark in `email-state.json` so re-runs never reclassify.

**Mail view** — list (sender / subject / snippet / date) + label chips; **client-side filtering across all 6 facets** (e.g. `Org/Customer + BU/PT + Type/Action + Prio/0`); full email body on selection; per-email chat to draft a reply in voice (→ `gmail_create_draft`).

**Meetings view** — `calendar_list` home; select a meeting → **Prep** (draft agenda/brief from vault + `vault_recent_meetings`), **Notes** (`drive_find_meeting_doc` → `docs_export` → `propose_meeting_note`/`propose_contact_update` → review diff → `commit_writes`), **Follow-up** (voice draft → `gmail_create_draft`).

**Correction state** and **email-state.json** are local JSON, git-ignorable, mirroring the `.sync-state.json` pattern.

## Auth, runtime, testing

- **Auth.** One Google OAuth covering Calendar / Drive / Docs / Gmail scopes; token stored locally (e.g. `~/.sacopilot/google-token.json`, git-ignored). Anthropic API key from env. No secrets in code.
- **Runtime.** `uv`-managed Python backend (`uv run uvicorn …`) + React frontend (`npm run dev`); one launch script; browser at localhost. Backend imports/shells the existing `~/Repos/obsidian/.sync/*.py` as vault tools.
- **Testing.**
  - Classifier regression: a fixture set of representative emails with expected facets, asserted against `classify_email`, to catch taxonomy drift.
  - Tool unit tests against a mock Gmail + a throwaway temp vault.
  - UI smoke-checked with Chrome DevTools before reliance.
- **Error handling.** Per-email Gmail/label failures surface in the Mail view (never silent); the approval gate prevents destructive surprises; vault writes are git-backed and diff-reviewed.

## Open items / future

- **Email → Obsidian capture** (the deferred "File-worthy" bridge) — revisit as a separate design.
- **Slack / Salesforce** live tools.
- **Auto-classify on arrival** (vs. button) — could move to a background poll once the button flow is trusted.

## Verification (how we'll know it works)

1. **Labels round-trip:** click *Classify new* on a handful of real emails → approve → confirm the nested labels appear in **Gmail web/mobile**, not just the app.
2. **Filtering:** apply a multi-facet filter in the Mail view and confirm the result set matches the Gmail label search.
3. **Learning loop:** correct a misclassification, reclassify a similar email, confirm the correction influenced the result.
4. **Meetings:** pick a past meeting with a Gemini doc → capture → review the proposed vault diff → commit → confirm the note lands correctly in the vault (git diff).
5. **Voice:** generate a follow-up draft → confirm it lands as a **Gmail draft** in voice and is never sent.
6. **Safety:** confirm no effecting tool executes without an approval step.
