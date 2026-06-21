# Calendar Auto-Categorisation (design)

Date: 2026-06-21
Status: approved
App: `apx/` (Meetings tab).

First sub-project of the SA-automation program. AI labels uncategorised Google
Calendar meetings into the user's existing categories and writes the matching
color back to Google, on a button.

## Categories → Google colors
| Category | Google color | colorId |
|---|---|---|
| Customer External | Tangerine | 6 |
| Customer Internal | Blueberry | 9 |
| Databricks Internal | Basil | 10 |
| Preps | Grape | 3 |
| Private | Banana | 5 |

## Behaviour
- Button **Auto-categorise** in the Meetings week toolbar.
- **Auto-applies** (no review step) but **only to uncategorised events** (no
  `colorId`). Manually-coloured events are never touched.
- Writes use `send_updates="none"` so recolouring does **not** notify attendees.

## Classification logic
- **External detection by inversion** (robust to all Bosch sub-domains):
  any attendee whose domain is not `databricks.com` is an external/customer
  participant. `has_external = True` → strong signal for **Customer External**.
  Known Bosch domains (bosch.com, de.bosch.com, bshg.com, boschrexroth.com, …)
  are passed as *hints* only, not a gate.
- Label definitions the model applies:
  - **Customer External** — external (customer) attendees present / customer-facing.
  - **Customer Internal** — Databricks-only attendees, meeting is *about* a customer.
  - **Databricks Internal** — internal team / enablement / ops, no customer focus.
  - **Preps** — prep / focus-work blocks (often solo, no guests).
  - **Private** — personal (lunch, gym, travel, errands).
- **Few-shot learning**: the week's already-coloured events become examples
  (title + attendee domains → the user's category) so the model matches the
  user's judgment. One Claude call (gateway, JSON-prompt) classifies all
  uncoloured events at once; output validated against the 5 categories.

## Backend
- `tools/google.py`
  - `calendar_set_color(event_id, color_id)` → `calendar_event_update(event_id,
    color_id, send_updates="none")`.
  - `calendar_list` already returns `color_id` + `attendees` (domains derivable).
- `meeting_categorize.py` (new)
  - `CATEGORIES`, `CAT_TO_COLOR`, `COLOR_TO_CAT` (inverse, for examples).
  - `INTERNAL_DOMAINS = {"databricks.com"}`; `_domain(email)` helper;
    `has_external(attendees)`.
  - `classify(uncoloured, examples)` → `{event_id: category}` via one Claude call.
- Route `POST /api/meetings/categorize?start=YYYY-MM-DD` (SSE):
  load the Mon–Fri week → split coloured (examples) / uncoloured → classify →
  for each uncoloured event write `color_id`, streaming
  `{type:progress, done, total, event_id, category}`; final `{type:done, total}`.
  No uncoloured events → `{type:done, total:0}`.

## Frontend (Meetings tab)
- "Auto-categorise" button next to the week nav. On click → SSE; show
  `categorising… done/total`; on completion `getWeek()` refresh so the new
  colours render. Manual colours stay.
- `lib/cockpit-api.ts`: `categorizeWeek(start, onEvent)` SSE reader +
  `CategorizeEvent` type.

## Error handling
- MCP unavailable → 503. A single event failing to classify/write streams an
  `item_error` and the run continues. Model returns an unknown label → skip that
  event (leave uncoloured).

## Testing
- Unit (monkeypatched): `has_external` across databricks vs bosch sub-domains;
  category→colorId mapping; classify parsing (JSON array → validated map);
  skip-already-coloured logic.
- Live: run on a week, confirm only uncoloured events get coloured, manual
  colours untouched, attendees not notified.

## Out of scope (v1)
- Re-categorising coloured events; example window beyond the current week;
  a review/approve step (auto-apply chosen); non-primary calendars.
