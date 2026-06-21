# SA Copilot — Classification Flow v2 (design)

Date: 2026-06-20
Status: approved-pending-review
Supersedes the email-triage portion of `2026-06-19-sa-copilot-design.md`.

## Motivation

After first hands-on use, the per-tool "approve all" agent flow felt wrong for
triage. Feedback:

1. Show a progress bar (how many mails classified, e.g. 3/10).
2. Labels visible on rows, but the user wants to **adjust** them.
3. Filter the inbox by label category.
4. Classify from subject + sender + snippet only — full bodies are 100k+ chars.
5. Drop approve-per-tool. Auto-apply classifications; the user just corrects.
6. Show and classify all (unclassified) mail, not a subset.

## Decisions

- **Auto-apply, no approval gate.** Classification moves out of the chat agent
  into its own button-driven flow. "Classify new" classifies every
  *unclassified* inbox message and writes straight to Lakebase. The chat agent
  keeps drafting + meeting capture (still approval-gated); `classify_email` and
  `save_classification` are removed from the agent toolset (one code path).
- **Scope = unclassified only.** A message already in Lakebase is skipped by the
  batch. No per-email re-run for now; the only way to change a stored
  classification is a manual facet edit.
- **Correction = facet dropdowns**, constrained to the taxonomy. Labels are
  always derived from facets.
- **Auto vs. adjusted stored separately.** The model's original output is frozen
  alongside the effective (possibly edited) values.
- **Adjusted rows teach.** Recent adjusted rows become the classifier's few-shot
  examples (replaces `corrections.json`).
- **All chips shown** on each row, color-coded per facet category.

## Data model (Lakebase `email_classifications`)

Existing flat columns hold the **effective** values:
`type, org, prio, dbx, bosch, bu[], labels[], confidence, rationale,
needs_review, classified_at`.

Add:
- `auto_facets JSONB` — the model's original facet object (frozen).
- `auto_labels TEXT[]` — labels derived from `auto_facets` (frozen).
- `adjusted BOOLEAN NOT NULL DEFAULT FALSE`.
- `adjusted_at TIMESTAMPTZ`.

On first classify: `auto_* == effective`, `adjusted=false`. On manual edit: only
the effective columns + `adjusted/adjusted_at` change; `auto_*` is preserved.

## Components

### `server/classifier.py` (new)
- `unclassified_inbox(max_results)` → inbox messages whose `id` is not yet in
  Lakebase (uses `gmail_list_messages` + `lakebase` membership check).
- `classify_message(msg)` → calls the classifier with **subject + sender +
  snippet only** (hard rule; never fetches the full body), then
  `lakebase.save_classification(...)` with `auto == effective`.
- Few-shot examples come from `lakebase.recent_adjusted(limit)`.

### `server/lakebase.py` (extend)
- `save_classification(...)` writes both effective + `auto_facets/auto_labels`.
- `update_classification(message_id, facets)` → recompute labels, update
  effective columns, set `adjusted=true, adjusted_at=now()`; leave `auto_*`.
- `recent_adjusted(limit)` → `{subject, sender, facets}` for adjusted rows
  (few-shot).
- `labels_for` / `facets_for(message_ids)` for the cockpit join (facets so the
  detail panel can populate dropdowns; includes `adjusted` flag).

### `server/routes/mail.py` (extend)
- `GET /mail/list` — inbox rows + joined effective facets, labels, `classified`,
  `adjusted`.
- `POST /mail/classify` — SSE. Streams `{type:'progress', done, total,
  message_id, labels}` per email and a final `{type:'done'}`. Auto-saves each.
- `PUT /mail/classify/{message_id}` — body = edited facets; calls
  `update_classification`; returns regenerated labels.

### `server/agent.py` / `registry.py` / `approval.py`
- Remove `classify_email` + `save_classification` tools and dispatch.
- Remove `save_classification` from `EFFECTING_TOOLS` and `summarize`.
- Update SYSTEM prompt: agent handles drafting + meetings only.

### Frontend (`frontend/src`)
- **Progress bar**: "Classify new" opens the `/mail/classify` SSE; show
  `done / total` filling as rows light up.
- **Rows**: all assigned chips, color-coded by category (Type/Org/Prio/DBX/
  Bosch/BU/Needs).
- **Detail panel**: 6 facet dropdowns bound to the taxonomy; on change → `PUT`,
  chips refresh, row marked adjusted.
- **Filter bar**: grouped multi-select by facet category; filters visible rows
  client-side (rows already carry their facets).

## Data flow

```
Classify new ─▶ POST /mail/classify (SSE)
  server: unclassified_inbox() ─▶ for each: classify (subj+sender+snippet)
          ─▶ save_classification (auto==effective) ─▶ stream progress
  UI: progress bar fills; chips appear per row

Adjust ─▶ select row ─▶ change facet dropdown
  ─▶ PUT /mail/classify/{id} {facets}
  server: update_classification (effective+adjusted, auto frozen)
  UI: chips refresh; next classify run uses adjusted rows as few-shot
```

## Error handling

- Lakebase down: `/mail/list` still lists inbox (no chips, no crash, as today);
  `/mail/classify` surfaces a clear error event; `PUT` returns 503.
- A single email failing to classify streams an `{type:'error', message_id}` and
  the batch continues (one bad email doesn't abort the run).
- Token expiry handled by the existing 45-min credential cache.

## Testing

- Unit: `unclassified_inbox` filters out stored ids; `update_classification`
  freezes `auto_*` and flips `adjusted`; label regeneration from facets.
- Smoke: classify a fixture message end-to-end (subj+sender+snippet → row in
  Lakebase with auto==effective); adjust it (effective changes, auto frozen);
  `recent_adjusted` returns it.

## Out of scope (YAGNI)

- Per-email model re-run.
- Bulk multi-select edits.
- Pagination / "load more" beyond a sensible cap (classify what's shown).
