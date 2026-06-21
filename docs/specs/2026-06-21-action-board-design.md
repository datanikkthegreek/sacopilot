# Action Board / Kanban (design)

Date: 2026-06-21
Status: approved
App: `apx/` — new `/board` tab. Sub-project #2 of the SA-automation program.

The hub for prioritised todos. v1 = board core + manual add. Email→board and
calendar auto-scheduling are explicit later phases.

## Data model (Lakebase `todos`)
- `id` TEXT PK (uuid), `title` TEXT, `description` TEXT
- `status` TEXT — one of: **Open, This week, Next week, In progress, Completed**
- `priority` TEXT — **0 | 1 | 2** (P0 urgent / P1 this week / P2 whenever)
- `estimate_hours` DOUBLE (time estimate, nullable)
- Structured fields: `type` TEXT (**Bosch | Internal | Enablement**),
  `use_case_id` TEXT + `use_case_name` TEXT (link to a SFDC UCO, nullable),
  `bu` TEXT (taxonomy BU enum, nullable), `project` TEXT (free text)
- `tags` TEXT[] (free-form)
- `created_at`, `updated_at` TIMESTAMPTZ

Ordering within a column: by priority (P0 first) then `updated_at`. Manual
drag-reorder within a column is out of scope (phase 2).

## Backend
- `lakebase.py` DAO: `list_todos()`, `create_todo(fields)`,
  `update_todo(id, fields)` (covers edits AND moving columns via `status`),
  `delete_todo(id)`.
- `routes/board.py`:
  - `GET /api/board/todos` → all todos.
  - `POST /api/board/todos` → create (server stamps id/created/updated).
  - `PUT /api/board/todos/{id}` → update (any subset of fields, incl. status).
  - `DELETE /api/board/todos/{id}`.
  - `GET /api/board/meta` → `{statuses, types, priorities, bu[], use_cases:[{id,name}]}`.
    `bu` from `taxonomy.BU`; `use_cases` best-effort from `salesforce.list_ucos`
    (empty list if SFDC unavailable — board still works).

## Frontend (`/board` tab)
- Nav link in `__root` (Mail · Meetings · Use-Cases · Board).
- `components/board-view.tsx`: 5 columns; each card shows title, **P0/P1/P2**
  badge, estimate (`~2h`), and chips (type, use-case, BU, project, tags).
- **Drag-and-drop between columns** to change status (native HTML5 DnD, no new
  deps): card `draggable`, column `onDragOver`/`onDrop` → `PUT status`.
- **+ Add** opens a card editor (modal): title, description, status, priority,
  estimate, type, use-case (dropdown from `/board/meta`), BU (dropdown), project,
  tags. Clicking a card opens the same editor; editor has **Delete**.
- Optimistic update on move; refetch on create/edit/delete.
- `lib/cockpit-api.ts`: `Todo` type, `listTodos`, `createTodo`, `updateTodo`,
  `deleteTodo`, `boardMeta`.

## Error handling
- Lakebase down → 503 (board list shows the error). SFDC down → use-case dropdown
  just empty; board unaffected.

## Testing
- Unit: DAO create/list/update(status move)/delete round-trip (live Lakebase);
  ordering (priority then updated_at). Route smoke (routes mount).
- Live: create a card, drag across columns, edit, delete; verify persistence.

## Out of scope (later phases)
- Email→board (button on Action emails), Slack/meeting→board, auto-scheduling
  cards into 9–18 calendar slots, manual drag-reorder within a column,
  weekly-planning view.
