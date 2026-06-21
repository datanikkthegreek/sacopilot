# SA Copilot (APX) — Meetings + Use-Cases tabs (design)

Date: 2026-06-21
Status: approved
App: `~/Repos/sacopilot-apx` (the APX app).

Two new tabs, built as two sub-projects: **Meetings** (calendar), then
**Use-Cases** (Salesforce UCOs).

---

## Sub-project A — Meetings tab (Google-style week calendar)

### Backend
- Extend `tools/google.calendar_list` to also return `color_id`, `all_day`,
  `end`, `attendees`, `hangout`, `summary`.
- `GET /api/meetings/week?start=YYYY-MM-DD` → events for that Mon–Fri work week
  (server computes Monday..Friday from `start`; defaults to current week).

### Frontend (Meetings tab, replaces the stub)
Two panes:
- **Left — list view**: events grouped by weekday, chronological, colored dot per
  event, time + title + attendees.
- **Right — week grid**: 5 columns (Mon–Fri), hour rows ~7:00–20:00, timed events
  absolutely positioned by start/end and **color-coded by `color_id`** using
  Google's exact event palette (the colors the user already chose per category):

  | id | name | hex | id | name | hex |
  |----|------|-----|----|------|-----|
  | 1 | Lavender | #7986CB | 7 | Peacock | #039BE5 |
  | 2 | Sage | #33B679 | 8 | Graphite | #616161 |
  | 3 | Grape | #8E24AA | 9 | Blueberry | #3F51B5 |
  | 4 | Flamingo | #E67C73 | 10 | Basil | #0B8043 |
  | 5 | Banana | #F6BF26 | 11 | Tomato | #D50000 |
  | 6 | Tangerine | #F4511E | — | default (null) | #039BE5 |

  All-day events render in a top strip above the grid.
- **Week nav**: ‹ Prev · Today · Next ›, with the week range shown.

### Notes
- The old agent-driven Prep/Notes/Follow-up actions are out of scope for this
  pass (calendar view is the goal); can be re-added later.

---

## Sub-project B — Use-Cases tab (Salesforce UCOs)

### Backend
- `salesforce.py` — `sf` CLI wrapper (local, same model as dbexec):
  - resolve target org once (`sf org display` → username; fallback `sf org list`).
  - `list_ucos(account, prefix)` → SOQL:
    `SELECT Id, Name, Stages__c, Account__r.Name, Owner.Name FROM UseCase__c
     WHERE Account__r.Name LIKE '%<account>%' AND Name LIKE '<prefix>%'
     AND Stages__c IN ('U1','U2','U3','U4','U5') ORDER BY Name`.
  - `get_uco(id)` → current `Demand_Plan_Next_Steps__c`, `Implementation_Notes__c`,
    `Stages__c`, description, dates, owner.
  - `update_uco(id, fields)` → `sf data update record`.
  - Strip sf's leading `Warning:` line before `jq`/parse; clear error if not
    authed (surface "run /salesforce-authentication").
- `usecase_gen.py` — ports the use-case skill's **strict templates + authoring
  rules** for Onboarding Plan (`Implementation_Notes__c`) and Next Steps
  (`Demand_Plan_Next_Steps__c`). Generates via Claude (gateway) from: current
  field content + UCO context (name/account/stage/description/dates) + the user's
  prompt. Refresh date to today (Europe/Berlin); preserve-history rules for
  update. **Stage gating**: Onboarding only for `Stages__c` ≥ U3.

### Routes
- `GET /api/usecases?account=Bosch Global&prefix=[NS]` → list (Name, Stage, …).
- `GET /api/usecases/{id}` → detail incl current Next Steps / Onboarding / stage.
- `POST /api/usecases/{id}/generate` `{artifact: "next_steps"|"onboarding", prompt}`
  → `{text}` generated.
- `PUT /api/usecases/{id}` `{next_steps?, onboarding?}` → `sf` writeback.

### Frontend (Use-Cases tab)
- **Filter bar**: Account (default **Bosch Global**) + Name prefix (default
  **[NS]**) → **table** of UCOs (Name, Stage, Account, Owner).
- Select a UCO → **two columns**, one block per artifact:
  - **Left**: current **Next Steps**, current **Onboarding Notes** (from SFDC).
  - **Right**: **prompt** field + **Generate** → generated text (editable), per
    artifact.
  - Pre-U3 → Onboarding block disabled with a note.
- **Update** button → **confirm dialog** ("Update <UCO> in Salesforce?") → writes
  the edited generated values via `sf`.

---

## Shared / cross-cutting
- Both are new TanStack routes/tabs in the apx app (`routes/meetings.tsx`,
  `routes/usecases.tsx`) + nav entries, styled with the existing shadcn/dark-mode
  treatment.
- Hand-written fetch client lives in `lib/cockpit-api.ts` (apx regenerates
  `lib/api.ts` from OpenAPI; keep ours separate).
- Salesforce + Google both use local CLIs (sf, dbexec) — local-only, like the
  rest of the app.

## Error handling
- Calendar/MCP down → 503 with a clear message.
- Salesforce not authed or query error → 502/503 with the auth hint.
- Generation failure → surfaced inline; Update disabled until something is
  generated/edited.

## Testing
- Backend unit (monkeypatched): week-range computation; SOQL builder
  (account/prefix/active-stage filter); usecase_gen template fill + stage gating.
- Live: render a week with colors + nav; list UCOs for Bosch Global/[NS], pick
  one, generate Next Steps, confirm + update writeback.

## Out of scope
- Calendar event create/edit/drag; UCO create; batch UC update; the meeting
  agent actions.
