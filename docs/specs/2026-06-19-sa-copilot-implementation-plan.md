# SA Copilot — Implementation Plan

**Spec:** `2026-06-19-sa-copilot-design.md` · **Repo:** `~/Repos/sacopilot/`
**Stack:** Python 3.11+ / FastAPI / `uv` backend · React + Vite + TS frontend · Anthropic SDK (`claude-opus-4-8`, adaptive thinking, streaming) · Google APIs (Calendar/Docs/Drive/Gmail).

Phases are ordered so each ends at a runnable, testable checkpoint. Build phase N only after N-1's checkpoint passes.

---

## Phase 0 — Scaffold & config
- `pyproject.toml` (uv): `anthropic`, `fastapi`, `uvicorn`, `google-api-python-client`, `google-auth-oauthlib`, `pydantic`, `pyyaml`, `httpx`.
- Layout: `app.py` (FastAPI entry + SSE), `server/{config,agent,approval,state}.py`, `server/tools/{google,classify,vault,voice}.py`, `server/routes/{mail,meetings,agent}.py`, `frontend/` (Vite React-TS), `dev.sh` (launch both).
- `server/config.py`: load `ANTHROPIC_API_KEY` from env; paths to vault (`~/Repos/obsidian/NikkTheGreek`), `.sync` scripts, voice profile, `~/.sacopilot/` for token + state. No secrets in code.
- **Checkpoint:** `uv run uvicorn app:app` serves `/health`; `npm run dev` serves a stub page.

## Phase 1 — Google auth + read-only Gmail/Calendar
- `server/tools/google.py`: OAuth installed-app flow (Calendar/Docs/Drive/Gmail scopes), token cached at `~/.sacopilot/google-token.json`, auto-refresh. One-time `auth` CLI command to mint it.
- Read tools first: `gmail_list_messages`, `gmail_get_message`, `calendar_list`, `drive_find_meeting_doc`, `docs_export`.
- **Checkpoint:** a script prints today's calendar and the 10 newest unlabeled emails. No writes yet.

## Phase 2 — Classifier (structured output)
- `server/tools/classify.py`: `classify_email(subject, from, body)` → Anthropic call with `output_config.format` JSON schema for the 6 facets + `confidence`. Schema enforces enum values; `Org` gates which of DBX/Bosch/BU are required. `BU` is an array. Confidence < threshold → caller adds `Needs/Review`.
- Facet enums sourced from one `server/taxonomy.py` (single source of truth; BU codes pulled from the vault's `_MOC.md`).
- `tests/fixtures/emails/` + `tests/test_classify.py`: representative emails → expected facets (regression guard).
- **Checkpoint:** classifier passes the fixture set.

## Phase 3 — Gmail label write-back + approval gate
- `gmail_ensure_labels` (create nested `Prefix/Value` tree once, idempotent), `gmail_apply_labels` (effecting), `gmail_create_draft` (effecting, never send).
- `server/approval.py`: effecting tools raise a pause → backend emits an approval request over SSE → frontend OK/edit → resume. Read tools bypass.
- `server/state.py`: `email-state.json` (watermark + per-message facets), correction store for the learning loop.
- **Checkpoint:** classify a real email end-to-end, approve, confirm the nested labels appear in **Gmail web/mobile**.

## Phase 4 — Agent loop
- `server/agent.py`: manual Anthropic tool-use loop (not auto-runner) — register all tools, stream text + tool events over SSE, honor the approval pause, handle `stop_reason` (`tool_use`/`end_turn`/`refusal`/`max_tokens`). `load_voice_profile` injected for drafting.
- `server/routes/agent.py`: `POST /agent/message` (SSE stream), `POST /agent/approve`.
- **Checkpoint:** via curl/stub UI: "classify my new mail" runs the loop, pauses for approval, applies labels.

## Phase 5 — Mail cockpit (React)
- Mail list (sender/subject/snippet/date + label chips), **Classify new** button, full-email pane, **client-side 6-facet filter**, inline re-label (→ correction store + `gmail_apply_labels`), per-email "draft reply" (voice → Gmail draft), approval modal (label set / draft preview).
- **Checkpoint:** full mail triage loop usable in-browser; multi-facet filter matches Gmail search; correction influences a re-run.

## Phase 6 — Meetings cockpit + vault tools
- `server/tools/vault.py`: read tools (`vault_search`, `vault_read`, `vault_recent_meetings`) + `propose_*` (diff-only, wrap `~/Repos/obsidian/.sync/sync_engine.py`, `gen_contacts.py`) + `commit_writes` (effecting; **Meetings only**).
- Meetings view: calendar home → Prep / Notes (find doc → export → propose note diff → review → commit) / Follow-up (voice draft).
- **Checkpoint:** capture a past meeting → review vault diff → commit → `git diff` in the obsidian repo shows the note; a follow-up lands as a Gmail draft.

## Phase 7 — Hardening
- Per-email error surfacing in Mail view; OAuth-expiry re-auth prompt; Chrome DevTools UI smoke pass; README run instructions.

---

## Cross-cutting rules
- **Never auto-send** mail; drafts only. **No email→vault write** in v1 (vault read-only from Mail; `commit_writes` is Meetings-only).
- **Gmail is the source of truth** for labels — always write back; app reflects.
- Effecting tools = `{gmail_apply_labels, gmail_ensure_labels, gmail_create_draft, commit_writes}` — all gated.
- Model `claude-opus-4-8`, adaptive thinking, streaming; classification via structured output.

## Verification (from spec §Verification)
Labels round-trip to Gmail · multi-facet filter == Gmail search · correction learning loop · meeting capture → vault diff → commit · voice draft never sent · no effecting tool runs without approval.
